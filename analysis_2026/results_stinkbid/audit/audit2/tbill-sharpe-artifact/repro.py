"""Independent reproduction of finding tbill-sharpe-artifact (read-only).

Rebuilds B-TBILL and B-TBILL-OWN from the raw T-bill sources (us_market_data.csv 'Risk Free Rate', then FRED DTB3),
on the P1 x U_Q1 day grid, matches them to the committed desc first pass (7949037), recomputes the D7 summary's Sharpe
the way stinkbid_engine._summ does (monthly excess over rf_m = simple monthly sum of daily rates), and decomposes it.
"""
import io
import math
import subprocess

import numpy as np
import pandas as pd

REPO = "/home/user/moneyline-upgrade"
COMMIT = "7949037"
DAY_M = 1440


def git_csv(path):
    b = subprocess.run(["git", "-C", REPO, "show", f"{COMMIT}:{path}"], check=True, capture_output=True).stdout
    return pd.read_csv(io.BytesIO(b))


summ = git_csv("analysis_2026/results_stinkbid/desc/d7_summary.csv")
mon = git_csv("analysis_2026/results_stinkbid/desc/d7_monthly_F1_0.0.csv").set_index("Unnamed: 0")

# ---------------------------------------------------------------- day grid (P1 x U_Q1, as accounts() builds it)
bids = pd.read_parquet(f"{REPO}/data/stinkbid/runs/outcomes/P1__U_Q1/bids.parquet", columns=["t0", "coin"])
d0 = int(bids.t0.min() // DAY_M)
END = pd.Timestamp("2026-11-17")                      # stinkbid_data.END
end_min = int((END + pd.Timedelta("1D")).value // 60_000_000_000) - 1
end_day = end_min // DAY_M
days = np.arange(d0, end_day + 1, dtype=np.int64)
nd = len(days)
dts = pd.to_datetime(days, unit="D")
print(f"day grid: {dts[0].date()} .. {dts[-1].date()}, {nd} days")

# ---------------------------------------------------------------- T-bill, independently rebuilt
m = pd.read_csv(f"{REPO}/data/stinkbid/macro/us_market_data.csv", usecols=["Date", "Risk Free Rate"],
                parse_dates=["Date"]).set_index("Date")["Risk Free Rate"]
base = m[~m.index.duplicated()].sort_index()
x = pd.read_csv(f"{REPO}/data/stinkbid/macro/fred_DTB3.csv")
ext = pd.Series(pd.to_numeric(x["DTB3"], errors="coerce").to_numpy(), index=pd.to_datetime(x.iloc[:, 0])).dropna()
ext = ext.sort_index()
s = pd.concat([base, ext[ext.index > base.index[-1]]])
tb = s.reindex(dts, method="ffill").to_numpy(float).copy()
late = dts > s.index[-1]
tb[late] = s.iloc[-1]                                  # same year as the series' last day (2026)
tb = np.nan_to_num(tb, nan=3.0)
rf_day = tb / 100.0 / 365.0
print(f"rf %: first {tb[0]:.4f} ({dts[0].date()}), last {tb[-1]:.4f}; days after the source's end: {late.sum()}")

# ---------------------------------------------------------------- month grid, as accounts() builds it
mlab = dts.to_period("M")
me_idx = np.r_[np.flatnonzero(mlab[1:] != mlab[:-1]), nd - 1]
me_lab = mlab[me_idx].astype(str)
starts = np.r_[0, me_idx[:-1] + 1]
rf_m_sum = np.add.reduceat(rf_day, starts)                         # what _summ uses
rf_m_cmp = np.multiply.reduceat(1 + rf_day, starts) - 1           # the T-bill's own compounded monthly return


def monthly(V, flows=None):
    Vm = V[me_idx]
    fl = np.zeros(len(me_idx)) if flows is None else np.add.reduceat(flows, starts)
    prev = np.r_[V[0] if flows is None else 0.0, Vm[:-1]]
    return (Vm - prev - fl) / (prev + fl)


def sharpe(ex):
    sd = ex.std(ddof=1)
    return ex.mean() / sd * math.sqrt(12) if sd > 0 else float("nan")


def cagr(r):
    return float(np.prod(1 + r)) ** (12 / len(r)) - 1


rec = summ[(summ.route == "F1") & (summ.r_res == 0.0)].set_index("account")

# ---------------------------------------------------------------- B-TBILL
K = float(rec.loc["D7", "K"])
V = K * np.cumprod(1 + rf_day)                        # ledger(zeros, zeros, zeros, 0, K): c += c * rf_day[i]
r = monthly(V)
r_rec = mon["B-TBILL"].to_numpy(float)
assert list(mon.index) == list(me_lab), "month labels differ"
print("\nB-TBILL")
print(f"  rebuilt end value {V[-1]:.6f} vs record {rec.loc['B-TBILL', 'end_value']:.6f}")
print(f"  max |monthly diff| vs record: {np.abs(r - r_rec).max():.3e}; CAGR {cagr(r):.6%} vs record "
      f"{rec.loc['B-TBILL', 'cagr']:.6%}")
ex = r_rec - rf_m_sum
print(f"  _summ Sharpe on the record's monthly returns (rf_m = simple sum): {sharpe(ex):.7f}   "
      f"record: {rec.loc['B-TBILL', 'sharpe']:.7f}")
print(f"  excess per month: mean {ex.mean():.3e}, SD {ex.std(ddof=1):.3e}, first month ({me_lab[0]}) {ex[0]:.3e}, "
      f"min {ex.min():.3e}, max {ex.max():.3e}")
ex_rest = ex[1:]
print(f"  months 2..{len(ex)}: mean {ex_rest.mean():.3e}, SD {ex_rest.std(ddof=1):.3e}, "
      f"Sharpe {sharpe(ex_rest):.3f}; months with excess > 0: {(ex_rest > 0).sum()} / {len(ex_rest)}")
print(f"  compounding residual check: corr(excess, rf_m_sum^2/2) months 2..: "
      f"{np.corrcoef(ex_rest, rf_m_sum[1:] ** 2 / 2)[0, 1]:.4f}; mean(rf_m^2/2) {np.mean(rf_m_sum[1:] ** 2 / 2):.3e}")
print(f"  first month: account return {r_rec[0]:.6e} (from V[0], excludes day 0), rf_m {rf_m_sum[0]:.6e} "
      f"(includes day 0: rf_day[0] = {rf_day[0]:.3e})")
ex_c = r_rec - rf_m_cmp
print(f"  critic's fix (rf_m = prod(1+rf_day)-1): excess mean {ex_c.mean():.3e}, SD {ex_c.std(ddof=1):.3e}, "
      f"Sharpe {sharpe(ex_c):.4f}; nonzero months (|ex| > 1e-12): {(np.abs(ex_c) > 1e-12).sum()} "
      f"(first month {ex_c[0]:.3e}); -sqrt(12/83) = {-math.sqrt(12 / 83):.4f}")
# with both fixes (compounded rf_m and the first month measured from the day before the grid's first day)
r_fix = r.copy()
r_fix[0] = V[me_idx[0]] / K - 1
ex_cc = r_fix - rf_m_cmp
print(f"  compounded rf_m AND first month from K: max |excess| {np.abs(ex_cc).max():.3e} -> Sharpe undefined (0/0)")

# ---------------------------------------------------------------- B-TBILL-OWN (contributions at each month's first Monday)
u = pd.read_parquet(f"{REPO}/data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
u = u[u.U_Q1.astype(bool)]
coins = sorted(bids.coin.unique())
mon_day = (days.astype("datetime64[D]").astype("datetime64[M]").astype(np.int64))
uni = {c: np.unique(np.array([np.datetime64(mm[:7], "M").astype(np.int64) for mm in g.month])) for c, g in
       u.groupby("coin")}
members = np.zeros((nd, len(coins)), bool)
for j, c in enumerate(coins):
    members[:, j] = np.isin(mon_day, uni.get(c, []))
first_monday = {}
for t0 in sorted(bids.t0.unique()):
    mo = int(np.datetime64(int(t0) // DAY_M, "D").astype("datetime64[M]").astype(np.int64))
    first_monday.setdefault(mo, int(t0))
di = lambda tm: int(np.clip(np.searchsorted(days, np.asarray(tm, np.int64) // DAY_M), 0, nd - 1))
contrib = np.zeros(nd)
for mo, t0 in first_monday.items():
    i = di(t0)
    contrib[i] += 1000.0 * members[i].sum()
Vo = np.zeros(nd)
v = 0.0
for i in range(nd):
    v = v * (1 + rf_day[i]) + contrib[i]
    Vo[i] = v
ro = monthly(Vo, contrib)
ro_rec = mon["B-TBILL-OWN"].to_numpy(float)
print("\nB-TBILL-OWN")
print(f"  contributions {contrib.sum():,.0f}; rebuilt end value {Vo[-1]:.6f} vs record "
      f"{rec.loc['B-TBILL-OWN', 'end_value']:.6f}")
print(f"  max |monthly diff| vs record: {np.abs(ro - ro_rec).max():.3e}; CAGR {cagr(ro):.6%} vs record "
      f"{rec.loc['B-TBILL-OWN', 'cagr']:.6%}")
exo = ro_rec - rf_m_sum
print(f"  _summ Sharpe on the record's monthly returns: {sharpe(exo):.7f}   record: "
      f"{rec.loc['B-TBILL-OWN', 'sharpe']:.7f}")
print(f"  excess per month: mean {exo.mean():.3e}, SD {exo.std(ddof=1):.3e}; months < 0: {(exo < 0).sum()} / {len(exo)}")
exo_c = ro_rec - rf_m_cmp
print(f"  with the critic's fix only (compounded rf_m): mean {exo_c.mean():.3e}, Sharpe {sharpe(exo_c):.4f}")
# source of the remaining gap: contributions arrive at the first Monday, the time-weighted formula credits them from
# the month's first day
cday = np.flatnonzero(contrib > 0)
lag = [int(i - starts[np.searchsorted(starts, i, side='right') - 1]) for i in cday]
print(f"  contribution day within its month (days after the 1st, grid days): min {min(lag)}, max {max(lag)}, "
      f"mean {np.mean(lag):.2f}")
# contributions credited at the start of their month: excess should vanish (except month 1 day 0 as above)
contrib_s = np.zeros(nd)
for i in cday:
    contrib_s[starts[np.searchsorted(starts, i, side='right') - 1]] += contrib[i]
Vs = np.zeros(nd)
v = 0.0
for i in range(nd):
    v = v * (1 + rf_day[i]) + contrib_s[i]
    Vs[i] = v
rs_ = monthly(Vs, contrib_s)
print(f"  if contributions were made on each month's first grid day: compounded-rf excess max |.| months 2..: "
      f"{np.abs((rs_ - rf_m_cmp)[1:]).max():.3e}")

# ---------------------------------------------------------------- the same artefact in every other row: size
print("\nShift in other accounts' Sharpe from rf_m simple sum -> compounded (record's monthly returns, F1, r_res 0):")
for acc in ["D7", "B-ALERT", "B-MIX", "B-DCA", "B-HOLD", "B-ML", "D7-OWN", "D7-OWN-ML", "B-ALERT-DCA", "B-MIX-OWN",
            "B-DCA-OWN", "B-HOLD-OWN", "B-ML-DCA"]:
    rr = mon[acc].to_numpy(float)
    print(f"  {acc:12s} record {rec.loc[acc, 'sharpe']:.6f}  recomputed {sharpe(rr - rf_m_sum):.6f}  "
          f"compounded rf {sharpe(rr - rf_m_cmp):.6f}")
print(f"\nmean |rf_m_cmp - rf_m_sum| per month: {np.mean(np.abs(rf_m_cmp - rf_m_sum)):.3e}")
# rows with the T-bill accounts across all four route x r_res cells
print("\nB-TBILL / B-TBILL-OWN Sharpe in every committed row:")
print(summ[summ.account.isin(["B-TBILL", "B-TBILL-OWN"])][["route", "r_res", "account", "sharpe", "cagr"]]
      .to_string(index=False))
