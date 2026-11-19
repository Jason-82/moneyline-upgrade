"""Independent recomputation of the F1 numbers printed in the answer's sentences and their F3 (s = 1%) versions,
from the cached engine run P1__U_Q1 (read-only). Own cluster code (episodes, month/quarter blocks, G, G*)."""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

BASE = "data/stinkbid/runs/outcomes/P1__U_Q1/"
DAY = 1440


def rd(name, cols):
    return pq.read_table(BASE + name + ".parquet", columns=cols).to_pandas()


fills = rd("fills", ["fill_id", "bid_id", "coin", "rung", "variant", "t_F1", "t_F3_1", "ml_d0", "s24"])
outc = rd("outcomes", ["rule", "exit", "cost", "fill_id", "r", "delta", "complete", "exit_px", "exit_t"])
bench = rd("bench", ["fill_id", "rule", "alert_72h", "alert_M", "knife", "twin_knife"])
bids = rd("bids", ["bid_id", "coin", "rung", "variant", "live_from", "life_end"])
print("rows: fills", len(fills), "outcomes", len(outc), "bench", len(bench), "bids", len(bids))
print("F1 fills", int((fills.t_F1 >= 0).sum()), "F3_1 fills", int((fills.t_F3_1 >= 0).sum()))


# ---------------------------------------------------------------- own clusters
def days_of(tmin):
    return (np.asarray(tmin, np.int64) // DAY)


def episodes(tmin, gap=3):
    d = days_of(tmin)
    u = np.unique(d)
    new = np.r_[True, np.diff(u) > gap]
    epu = np.cumsum(new) - 1
    return epu[np.searchsorted(u, d)]


def months_of(tmin):
    t = pd.to_datetime(np.asarray(tmin, np.int64) * 60_000_000_000)
    return (t.year.to_numpy() - 1970) * 12 + t.month.to_numpy() - 1


def blocks(tmin, period="M"):
    ep = episodes(tmin)
    m = months_of(tmin)
    per = m if period == "M" else m // 3
    parent = {int(p): int(p) for p in np.unique(per)}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e in np.unique(ep):
        ps = np.unique(per[ep == e])
        for a, b in zip(ps[:-1], ps[1:]):
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(int(p)) for p in per])


def g_gstar(lab):
    _, n = np.unique(lab, return_counts=True)
    n = n.astype(float)
    return len(n), (n ** 2).sum() ** 2 / (n ** 4).sum()


def summ(name, y, tmin, period="M"):
    y = np.asarray(y, float)
    ok = np.isfinite(y)
    y, tmin = y[ok], np.asarray(tmin)[ok]
    G, gs = g_gstar(blocks(tmin, period))
    print(f"{name:55s} mean {100 * y.mean():+7.3f}%  n {len(y):5d}  G {G:3d}  G* {gs:5.2f} ({'month' if period == 'M' else 'quarter'}-blocks)")
    return y.mean(), len(y)


def per_fill(rule, exit, cost, value):
    t = "t_" + rule
    f = fills[fills[t] >= 0]
    o = outc[(outc.rule == rule) & (outc.exit == exit) & (outc.cost == cost) & outc.complete.astype(bool)]
    d = f.merge(o.drop(columns=["rule", "exit", "cost"]), on="fill_id", how="inner")
    d = d[np.isfinite(d[value].to_numpy(float))].reset_index(drop=True)
    d["tf"] = d[t].to_numpy(np.int64)
    return d


def per_bench(rule, col):
    t = "t_" + rule
    f = fills[fills[t] >= 0]
    b = bench[bench.rule == rule].drop(columns=["rule"])
    d = f.merge(b, on="fill_id", how="inner")
    d = d[np.isfinite(pd.to_numeric(d[col], errors="coerce").to_numpy(float))].reset_index(drop=True)
    d["tf"] = d[t].to_numpy(np.int64)
    return d


print("\n== H1 recommendation sentence: excess over twins (+6.3%) and mean r_f (+4.8%), X-FLIP")
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    d = per_fill(rule, "FLIP", cost, "delta")
    summ(f"{rule} FLIP {cost} mean Delta_f", d["delta"], d["tf"])
    summ(f"{rule} FLIP {cost} mean r_f (net return of a flip)", d["r"], d["tf"])

print("\n== D-H2: Delta90 against B-TWIN, X-HOLD-90, quarter-block clusters")
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    d = per_fill(rule, "HOLD90", cost, "delta")
    summ(f"{rule} HOLD90 {cost} mean Delta90", d["delta"], d["tf"], "Q")

print("\n== D8 part 1: shared premium (alert buyer's coin-count advantage at 72 h)")
for rule in ("F1", "F3_1"):
    d = per_bench(rule, "alert_72h")
    summ(f"{rule} alert_72h", d["alert_72h"], d["tf"])

print("\n== D-H3 primary: fast (s24>=0.75) vs slow (s24<0.5), episode FE + rung dummies, X-FLIP")
for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
    d = per_fill(rule, "FLIP", cost, "delta")
    s = d["s24"].to_numpy(float)
    g = d[(s >= 0.75) | (s < 0.5)].reset_index(drop=True)
    fast = (g["s24"].to_numpy(float) >= 0.75).astype(float)
    rungs = sorted(g["rung"].unique())
    R = np.column_stack([(g["rung"].to_numpy() == v).astype(float) for v in rungs[1:]])
    X = np.column_stack([fast, R])
    y = g["delta"].to_numpy(float)
    ep = episodes(g["tf"].to_numpy())
    # drop singleton episodes (absorbed FE with one row carries no information)
    cnt = pd.Series(ep).map(pd.Series(ep).value_counts()).to_numpy()
    keep = cnt > 1
    Xk, yk, epk = X[keep], y[keep], ep[keep]
    dfX = pd.DataFrame(Xk)
    Xd = Xk - dfX.groupby(epk).transform("mean").to_numpy()
    yd = yk - pd.Series(yk).groupby(epk).transform("mean").to_numpy()
    b = np.linalg.lstsq(Xd, yd, rcond=None)[0]
    G, gs = g_gstar(blocks(g["tf"].to_numpy()[keep]))
    print(f"{rule} FLIP {cost} fast-slow coef {100 * b[0]:+.3f}%  n {keep.sum()} (of {len(g)}; fast {int(fast.sum())}, "
          f"slow {int((1 - fast).sum())})  G {G}  G* {gs:.2f}")

print("\n== Worst day (share of live P1 bids on U-Q1 filled the same UTC day)")
for rule in ("F1", "F3_1"):
    t = "t_" + rule
    b = bids.merge(fills[["bid_id", t]], on="bid_id", how="left")
    b[t] = b[t].fillna(-1).astype(np.int64)
    a = b["live_from"].to_numpy(np.int64) // DAY
    e = (b["life_end"].to_numpy(np.int64) - 1) // DAY
    fm = b[t].to_numpy(np.int64)
    fd = np.where(fm >= 0, fm // DAY, -1)
    slot = b.groupby(["coin", "rung", "variant"], sort=False, dropna=False).ngroup().to_numpy()
    best = (np.nan, None, 0, 0)
    rows = []
    for dd in np.unique(fd[fd >= 0]):
        resting = (a <= dd) & (e >= dd) & ((fm < 0) | (fm >= dd * DAY))
        live = len(np.unique(slot[resting]))
        filled = len(np.unique(slot[fd == dd]))
        rows.append((dd, filled, live))
        if live and (not np.isfinite(best[0]) or filled / live > best[0]):
            best = (filled / live, str(pd.Timestamp(int(dd) * 86400, unit="s").date()), filled, live)
    print(f"{rule}: worst day {best[1]}: {best[2]} of {best[3]} live = {100 * best[0]:.1f}%")

print("\n== MoneyLine at placement (ml_d0: 1 green, 0 red, -1 undefined)")
for rule in ("F1", "F3_1"):
    f = fills[fills["t_" + rule] >= 0]
    st = f["ml_d0"].to_numpy()
    red, green, und = int((st == 0).sum()), int((st == 1).sum()), int((st == -1).sum())
    print(f"{rule}: {red} red, {green} green, {und} undefined of {len(f)} -> red share of defined {100 * red / (red + green):.1f}%")

print("\n== Knife (TAIL_BOTTOM sentence; T1/D-H5 field): finite values per rule on the bench rows")
for rule in ("F1", "F3_1"):
    bb = bench[bench.rule == rule]
    k = pd.to_numeric(bb["knife"], errors="coerce")
    tk = pd.to_numeric(bb["twin_knife"], errors="coerce")
    print(f"{rule}: bench rows {len(bb)}, finite knife {int(np.isfinite(k).sum())}, finite twin_knife {int(np.isfinite(tk).sum())}")
d = per_bench("F1", "knife")
print(f"F1 knife share (fills, A) {100 * d['knife'].mean():.1f}% over {len(d)}; twins' knife (B) "
      f"{100 * np.nanmean(pd.to_numeric(d['twin_knife'], errors='coerce')):.1f}%")
print("bench rules present:", sorted(bench.rule.unique()))
