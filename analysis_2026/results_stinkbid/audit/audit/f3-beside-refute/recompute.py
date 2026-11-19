"""Independent recomputation (own code, from the prereg definitions) of the F1 numbers the answer prints and their
F3 (s = 1%) counterparts, from the cached P1/U_Q1 run of record. Reads only needed columns."""
import numpy as np, pandas as pd
from scipy import stats

BASE = "data/stinkbid/runs/outcomes/P1__U_Q1/"
DAY = 1440
GAP = 3

F = pd.read_parquet(BASE + "fills.parquet", columns=["fill_id", "bid_id", "coin", "rung", "variant", "t_F1", "t_F3_1",
                                                      "ml_d0", "s24"])
O = pd.read_parquet(BASE + "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "fill_id", "r", "delta",
                                                         "complete"],
                    filters=[("rule", "in", ["F1", "F3_1"]), ("exit", "in", ["FLIP", "HOLD90"])])
print("fills rows", len(F), "F1 fills", (F.t_F1 >= 0).sum(), "F3_1 fills", (F.t_F3_1 >= 0).sum())
print("outcome (rule, exit, lat, cost) combos:\n", O.groupby(["rule", "exit", "lat", "cost"]).size())


def episodes(tmin):
    d = np.asarray(tmin, np.int64) // DAY
    u = np.unique(d)
    new = np.r_[True, np.diff(u) > GAP]
    ep_u = np.cumsum(new) - 1
    return ep_u[np.searchsorted(u, d)]


def blocks(tmin, months_per):
    t = pd.to_datetime(np.asarray(tmin, np.int64) * 60, unit="s", utc=True)
    m = ((t.year - 1970) * 12 + t.month - 1).to_numpy()
    per = m // months_per
    ep = episodes(tmin)
    parent = {int(p): int(p) for p in np.unique(per)}
    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e in np.unique(ep):
        ps = np.unique(per[ep == e])
        for x, y in zip(ps[:-1], ps[1:]):
            a, b = find(int(x)), find(int(y))
            if a != b:
                parent[max(a, b)] = min(a, b)
    return np.array([find(int(p)) for p in per])


def mean_cr1(y, g):
    y = np.asarray(y, float); n = len(y)
    labs, gi = np.unique(g, return_inverse=True)
    G = len(labs)
    sizes = np.bincount(gi)
    gstar = (sizes.astype(float) ** 2).sum() ** 2 / (sizes.astype(float) ** 4).sum()
    m = y.mean()
    s = np.bincount(gi, weights=y - m)
    se = np.sqrt(G / (G - 1) * (s ** 2).sum()) / n
    tq = stats.t.ppf(0.975, gstar - 1)
    return dict(n=n, mean=m, G=G, gstar=gstar, se=se, t_lo=m - tq * se, t_hi=m + tq * se)


def sample(rule, exit, cost, value):
    tcol = "t_" + rule
    o = O[(O.rule == rule) & (O.exit == exit) & (O.cost == cost) & O.complete.astype(bool)]
    f = F[F[tcol] >= 0][["fill_id", tcol]]
    d = f.merge(o[["fill_id", value]], on="fill_id", how="inner")
    d = d[np.isfinite(d[value].to_numpy(float))]
    return d, tcol


def fmt(r):
    return (f"n={r['n']} mean={100*r['mean']:+.3f}% G={r['G']} G*={r['gstar']:.2f} "
            f"CR1 t(G*-1) 95% [{100*r['t_lo']:+.2f}%, {100*r['t_hi']:+.2f}%]")

print("\n== H1 recommendation: R = mean r_f after Robinhood costs (X-FLIP rule M); X = mean Delta")
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    for val in ("r", "delta"):
        d, tcol = sample(rule, "FLIP", cost, val)
        print(f"  {rule:5s} {val:5s}", fmt(mean_cr1(d[val], blocks(d[tcol], 1))))

print("\n== D-H2: Delta90 vs B-TWIN, X-HOLD-90, quarter-block clusters")
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    d, tcol = sample(rule, "HOLD90", cost, "delta")
    print(f"  {rule:5s}", fmt(mean_cr1(d["delta"], blocks(d[tcol], 3))))

Bn = pd.read_parquet(BASE + "bench.parquet", columns=["fill_id", "rule", "alert_72h", "alert_M", "knife", "twin_knife"])
print("\nbench rows by rule:", Bn.groupby("rule").size().to_dict())
print("\n== D8 part 1: the alert buyer's coin-count advantage at 72 h (alert_72h), month-block clusters")
for rule in ("F1", "F3_1"):
    tcol = "t_" + rule
    b = Bn[Bn.rule == rule][["fill_id", "alert_72h"]]
    d = F[F[tcol] >= 0][["fill_id", tcol]].merge(b, on="fill_id")
    d = d[np.isfinite(d.alert_72h.to_numpy(float))]
    print(f"  {rule:5s}", fmt(mean_cr1(d.alert_72h, blocks(d[tcol], 1))))

print("\n== TAIL_BOTTOM: 365-day knife share of fills (A) and of their twins (B)")
for rule in ("F1", "F3_1"):
    tcol = "t_" + rule
    b = Bn[Bn.rule == rule]
    d = F[F[tcol] >= 0][["fill_id"]].merge(b, on="fill_id")
    k = pd.to_numeric(d.knife, errors="coerce").to_numpy(float)
    tk = pd.to_numeric(d.twin_knife, errors="coerce").to_numpy(float)
    ok = np.isfinite(k)
    print(f"  {rule:5s} bench rows {len(d)}, finite knife {ok.sum()}, A={np.nanmean(k[ok]) if ok.any() else float('nan'):.4f}"
          f", B={np.nanmean(tk[ok]) if ok.any() else float('nan'):.4f}")

print("\n== MONEYLINE: state at placement of the fills (ml_d0: 1 green, 0 red, -1 undefined)")
for rule in ("F1", "F3_1"):
    s = F[F["t_" + rule] >= 0].ml_d0.to_numpy()
    red, green, und = (s == 0).sum(), (s == 1).sum(), (s == -1).sum()
    print(f"  {rule:5s} fills {len(s)}: red {red}, green {green}, undefined {und}, red share of defined "
          f"{red / (red + green):.4f}")

print("\n== TAIL_TOGETHER: worst UTC day's share of live P1 order slots (coin, rung, variant) that filled")
Bd = pd.read_parquet(BASE + "bids.parquet", columns=["bid_id", "coin", "rung", "variant", "live_from", "life_end"])
for rule in ("F1", "F3_1"):
    tcol = "t_" + rule
    b = Bd.merge(F[["bid_id", tcol]], on="bid_id", how="left")
    fm = b[tcol].fillna(-1).astype(np.int64).to_numpy()
    a = b.live_from.to_numpy(np.int64) // DAY
    e = (b.life_end.to_numpy(np.int64) - 1) // DAY
    fd = np.where(fm >= 0, fm // DAY, -1)
    slot = b.groupby(["coin", "rung", "variant"], sort=False).ngroup().to_numpy()
    rows = []
    for dd in np.unique(fd[fd >= 0]):
        resting = (a <= dd) & (e >= dd) & ((fm < 0) | (fm >= dd * DAY))
        live = len(np.unique(slot[resting])); filled = len(np.unique(slot[fd == dd]))
        rows.append((dd, filled, live, filled / live if live else np.nan))
    R = pd.DataFrame(rows, columns=["day", "filled", "live", "share"]).sort_values("share", ascending=False)
    R["day"] = pd.to_datetime(R.day * 86400, unit="s").dt.date
    print(f"  {rule:5s} bids {len(b)}, top days:\n", R.head(3).to_string(index=False))

import resource
print("peak RSS MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
