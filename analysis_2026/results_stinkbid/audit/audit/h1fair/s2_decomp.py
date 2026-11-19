"""Step 2: decompose Delta (exit kind, rung, year, coin, half); leave-one-coin-out / leave-one-year-out; rule-M
timing of every exit, recomputed with my own clock."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from common import *

O = pd.read_parquet(f"{OUT}/h1rows.parquet")
O["ts"] = min2ts(O.t_F1)
O["year"] = O.ts.dt.year
N = len(O)
tot = O.delta.sum()
print(f"N={N} total sum delta={tot:.3f}  mean={O.delta.mean():.4%}")


def tab(by, label):
    g = O.groupby(by)
    t = pd.DataFrame({"n": g.size(), "r_f": g.r.mean(), "twin": g.twin_mean.mean(), "delta": g.delta.mean(),
                      "share_of_sum": g.delta.sum() / tot})
    print(f"\n-- by {label}\n" + t.to_string(float_format=lambda x: f"{x:+.4f}"))
    return t


tab("exit_kind", "exit kind")
tab("rung", "rung")
tab("year", "year")
tab("half", "half (engine)")

# ---- coins
g = O.groupby("coin")
ct = pd.DataFrame({"n": g.size(), "r_f": g.r.mean(), "twin": g.twin_mean.mean(), "delta": g.delta.mean(),
                   "sum": g.delta.sum()}).sort_values("sum", ascending=False)
ct["share"] = ct["sum"] / tot
print(f"\ncoins: {len(ct)}; top 10 contributors:\n" + ct.head(10).to_string(float_format=lambda x: f"{x:+.4f}"))
print("bottom 5:\n" + ct.tail(5).to_string(float_format=lambda x: f"{x:+.4f}"))
print("top-10 coins' share of the sum:", ct["share"].head(10).sum())
print("coins with positive mean delta:", (ct.delta > 0).sum(), "of", len(ct))

# ---- leave-one-coin-out
rows = []
for c in ct.index:
    k = O.coin != c
    d = cr1(O.delta[k], O.mb_me[k])
    rows.append((c, d["n"], d["mean"], d["t"], d["p"], d["lo"]))
L = pd.DataFrame(rows, columns=["coin_out", "n", "mean", "t", "p1", "ci_lo"]).sort_values("mean")
print("\nleave-one-coin-out: min mean", L.iloc[0].to_dict(), "\n  max p1", L.sort_values("p1").iloc[-1].to_dict())
print(L.head(5).to_string())
# leave top-k coins out
for k_ in (1, 3, 5, 10):
    k = ~O.coin.isin(ct.index[:k_])
    print(f"without top-{k_} coins by sum:", fmt(cr1(O.delta[k], O.mb_me[k])))

# ---- leave-one-year-out
print()
for y in sorted(O.year.unique()):
    k = O.year != y
    print(f"without {y}:", fmt(cr1(O.delta[k], O.mb_me[k])))
    k = O.year == y
    print(f"   only {y}:", fmt(cr1(O.delta[k], O.mb_me[k])))

# ---- month-blocks / episodes
gb = O.groupby("mb_me")
bt = pd.DataFrame({"n": gb.size(), "start": gb.ts.min(), "sum": gb.delta.sum(), "mean": gb.delta.mean()})
bt["share"] = bt["sum"] / tot
bt = bt.sort_values("sum", ascending=False)
print("\ntop month-blocks by sum of delta:\n" + bt.head(8).to_string())
print("blocks with positive mean delta:", (bt["mean"] > 0).sum(), "of", len(bt))
ge = O.groupby("ep_me")
et = pd.DataFrame({"n": ge.size(), "start": ge.ts.min(), "sum": ge.delta.sum(), "mean": ge.delta.mean()})
et = et.sort_values("sum", ascending=False)
et["share"] = et["sum"] / tot
print("\ntop episodes by sum:\n" + et.head(8).to_string())
print("top-3 episodes by sum share:", et["share"].head(3).sum())
for k_ in (1, 3, 5):
    k = ~O.ep_me.isin(et.index[:k_])
    print(f"without top-{k_} episodes by sum:", fmt(cr1(O.delta[k], O.mb_me[k])))
etn = et.sort_values("n", ascending=False)
print("\nlargest episodes by fills:\n" + etn.head(5).to_string())

# ---- exit kind contributions
print("\ncontribution to the sum by exit kind:", (O.groupby("exit_kind").delta.sum() / tot).to_dict())

# ---- rule M recomputed (own code, zoneinfo)
NY = ZoneInfo("America/New_York")


def rule_m_me(tmin):
    ts = pd.to_datetime(np.asarray(tmin, np.int64) * 60, unit="s", utc=True)
    out = np.empty(len(ts), np.int64)
    for i, t in enumerate(ts):
        loc = t.tz_convert(NY)
        mins = loc.hour * 60 + loc.minute
        if 420 <= mins <= 22 * 60 + 59:
            out[i] = int(t.value // 60_000_000_000) + 60
        else:
            day = loc.normalize() if mins < 420 else (loc.normalize() + pd.Timedelta(days=1))
            tgt = pd.Timestamp(year=day.year, month=day.month, day=day.day, hour=7, tz=NY)
            out[i] = int(tgt.tz_convert("UTC").value // 60_000_000_000)
    return out


g_live = rule_m_me(O.t_F1.to_numpy())
S_stop = rule_m_me(O.t_F1.to_numpy() + 72 * 60)
O["g_me"], O["S_me"] = g_live, S_stop
et_ = O.exit_t.to_numpy()
k = O.exit_kind.to_numpy()
print("\n== rule M timing ==")
print("delay to go-live (min): ", pd.Series(g_live - O.t_F1.to_numpy()).describe().to_dict())
for kind in ("target", "marketable", "stop"):
    s = k == kind
    print(kind, "n", s.sum(), " min(exit_t - g_me)", (et_[s] - g_live[s]).min(),
          " min(exit_t - fill minute)", (et_[s] - O.t_F1.to_numpy()[s]).min(),
          " exit before stop:", (et_[s] < S_stop[s]).sum(), " at/after stop:", (et_[s] >= S_stop[s]).sum())
s = k == "marketable"
print("marketable exit_t == g_me:", (et_[s] == g_live[s]).sum(), "of", s.sum(),
      " lag (min):", np.unique(et_[s] - g_live[s], return_counts=True))
s = k == "stop"
lag = et_[s] - S_stop[s]
print("stop lag after S (min):", pd.Series(lag).describe().to_dict(), " >60 min:", (lag > 60).sum())
s = k == "target"
print("target exit_px == target:", np.allclose(O.exit_px[s], O.target[s], rtol=1e-12),
      " hold_h target: ", O.hold_h[s].describe().to_dict())
O.to_parquet(f"{OUT}/h1rows2.parquet")
