"""Independent recomputation of H1 / H2R inference from primary/samples_*.csv (own code, prereg §10.2 definitions).
Does not import stinkbid_stats."""
import sys
import numpy as np
import pandas as pd
from scipy import stats

RES = "analysis_2026/results_stinkbid/primary/"
OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1lens/"
LEVEL = 1 - 0.05 / 3
WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])


# ----------------------------------------------------------------- clusters (own code)
def my_episodes(days):
    """runs of distinct UTC fill days at most 3 days apart"""
    u = np.unique(days)
    ep_u = np.cumsum(np.r_[True, np.diff(u).astype("timedelta64[D]").astype(int) > 3]) - 1
    m = dict(zip(u, ep_u))
    return np.array([m[d] for d in days])


def my_blocks(periods, ep):
    """merge calendar periods transitively when one episode has fills in more than one period (union-find)"""
    up = sorted(set(periods.tolist()))
    par = {p: p for p in up}

    def f(x):
        while par[x] != x:
            x = par[x]
        return x
    for e in np.unique(ep):
        ps = sorted(set(periods[ep == e].tolist()))
        for a in ps[1:]:
            ra, rb = f(ps[0]), f(a)
            if ra != rb:
                par[max(ra, rb)] = min(ra, rb)
    root = np.array([f(p) for p in periods])
    _, ids = np.unique(root, return_inverse=True)
    return ids


def same_partition(a, b):
    a, b = np.asarray(a), np.asarray(b)
    pa = pd.Series(b).groupby(a).nunique().max()
    pb = pd.Series(a).groupby(b).nunique().max()
    return bool(pa == 1 and pb == 1)


# ----------------------------------------------------------------- inference (own code)
def gstar(n):
    n = np.asarray(n, float)
    n = n[n > 0]
    return (n ** 2).sum() ** 2 / (n ** 4).sum()


def cr1(y, g):
    y = np.asarray(y, float)
    _, gi = np.unique(g, return_inverse=True)
    G = gi.max() + 1
    N = len(y)
    th = y.mean()
    U = np.bincount(gi, weights=y - th, minlength=G)
    se = np.sqrt(G / (G - 1) * (U ** 2).sum()) / N
    n_g = np.bincount(gi, minlength=G)
    gs = gstar(n_g)
    return dict(n=N, G=G, gstar=gs, est=th, se=se, t=th / se, p_gstar=stats.t.sf(th / se, gs - 1),
                U=U, n_g=n_g, gi=gi)


def cr3(y, g):
    """cluster jackknife (CV3) SE of the mean"""
    y = np.asarray(y, float)
    _, gi = np.unique(g, return_inverse=True)
    G = gi.max() + 1
    S = np.bincount(gi, weights=y, minlength=G)
    n = np.bincount(gi, minlength=G)
    th_g = (S.sum() - S) / (n.sum() - n)
    return np.sqrt((G - 1) / G * ((th_g - th_g.mean()) ** 2).sum())


def wild(y, g, B=9999, seed=777, level=LEVEL):
    r = cr1(y, g)
    y = np.asarray(y, float)
    gi, G, N = r["gi"], r["G"], r["n"]
    S = np.bincount(gi, weights=y, minlength=G)
    n_g = r["n_g"].astype(float)
    rng = np.random.default_rng(seed)
    W = WEBB[rng.integers(0, 6, size=(B, G))]
    cG = G / (G - 1)
    # restricted, null 0: y* = w_g y_i
    th = W @ S / N
    res = W * S - th[:, None] * n_g
    se = np.sqrt(cG * (res ** 2).sum(1)) / N
    tr = th / se
    p_wcr = (1 + np.sum(tr >= r["t"] - 1e-10 * max(1, abs(r["t"])))) / (B + 1)
    # unrestricted
    Uh = S - n_g * r["est"]
    d = W @ Uh / N
    res = W * Uh - d[:, None] * n_g
    se = np.sqrt(cG * (res ** 2).sum(1)) / N
    tu = d / se
    tus = np.sort(tu)
    k = int(np.floor((B + 1) * (1 - level))) - 1
    ub_boot = r["est"] - tus[k] * r["se"]
    lo = r["est"] - tus[int(np.floor((B + 1) * 0.975)) - 1] * r["se"]
    hi = r["est"] - tus[int(np.floor((B + 1) * 0.025)) - 1] * r["se"]
    return dict(p_wcr=p_wcr, ub_boot=ub_boot, ci_boot=(lo, hi), max_tr=float(np.nanmax(tr)),
                q999_tr=float(np.quantile(tr, 0.999)))


def summarize(y, g, B=9999, seed=777, do_wild=True):
    r = cr1(y, g)
    df = r["gstar"] - 1
    out = dict(n=r["n"], G=int(r["G"]), gstar=r["gstar"], est=r["est"], se=r["se"], t=r["t"], p_gstar=r["p_gstar"],
               ci_t=(r["est"] - stats.t.ppf(0.975, df) * r["se"], r["est"] + stats.t.ppf(0.975, df) * r["se"]),
               ub_t=r["est"] + stats.t.ppf(LEVEL, df) * r["se"],
               mde=(stats.t.ppf(LEVEL, df) + stats.t.ppf(0.8, df)) * r["se"])
    if do_wild and r["G"] >= 2:
        w = wild(y, g, B, seed)
        out.update(p_wcr=w["p_wcr"], ub_boot=w["ub_boot"], ci_boot=w["ci_boot"], p_decide=max(w["p_wcr"], r["p_gstar"]),
                   ub=max(w["ub_boot"], out["ub_t"]))
    return out


def fmt(d, keys=("n", "G", "gstar", "est", "se", "t", "p_gstar", "p_wcr", "p_decide", "ci_t", "ub_t", "ub_boot", "ub", "mde")):
    s = []
    for k in keys:
        if k not in d:
            continue
        v = d[k]
        if isinstance(v, tuple):
            s.append(f"{k}=({v[0]:+.4f},{v[1]:+.4f})")
        elif isinstance(v, (int, np.integer)):
            s.append(f"{k}={v}")
        else:
            s.append(f"{k}={v:.4g}" if k not in ("est", "se", "ub_t", "ub_boot", "ub", "mde") else f"{k}={v:+.4f}")
    return " ".join(s)


def load(name):
    d = pd.read_csv(RES + f"samples_{name}.csv")
    d["t"] = pd.to_datetime(d["time"], utc=True)
    d["day"] = d["t"].dt.tz_localize(None).values.astype("datetime64[D]")
    d["mon"] = d["t"].dt.tz_localize(None).values.astype("datetime64[M]").astype(int)
    d["myep"] = my_episodes(d["day"].values)
    d["mymb"] = my_blocks(d["mon"].values, d["myep"].values)
    d["myqb"] = my_blocks(d["mon"].values // 3, d["myep"].values)
    d["myq"] = d["mon"].values // 3
    d["myhalf"] = (d["t"] >= pd.Timestamp("2023-01-01", tz="UTC")).astype(int)
    return d


def main():
    for name in ("H1", "H2R"):
        d = load(name)
        y = d["y"].to_numpy(float)
        print("=" * 100)
        print(name, "n", len(d), "finite", np.isfinite(y).sum())
        print(" partition checks: ep", same_partition(d["ep"], d["myep"]), "mb", same_partition(d["mb"], d["mymb"]),
              "hf", bool((d["hf"] == d["myhalf"]).all()))
        r0 = summarize(y, d["mymb"].values)
        print(" month-block:", fmt(r0))
        # leverage
        tab = d.groupby("mymb").agg(n=("y", "size"), s=("y", "sum"), m=("y", "mean"), first=("t", "min"), last=("t", "max"))
        tab["U"] = tab["s"] - tab["n"] * y.mean()
        tab["n2share"] = tab["n"] ** 2 / (tab["n"] ** 2).sum()
        tab["varshare"] = tab["U"] ** 2 / (tab["U"] ** 2).sum()
        tab = tab.sort_values("n", ascending=False)
        print(" top-3 blocks' share of sum n_g^2: %.3f; top-5 %.3f; top-3 share of CR1 sum U_g^2 (by n): %.3f" % (
            tab["n2share"].iloc[:3].sum(), tab["n2share"].iloc[:5].sum(), tab["varshare"].iloc[:3].sum()))
        tv = tab.sort_values("varshare", ascending=False)
        print(" top-3 share of CR1 sum U_g^2 (largest contributors): %.3f" % tv["varshare"].iloc[:3].sum())
        print(" largest blocks:")
        for b, r in tab.head(8).iterrows():
            print(f"   mb {b:3d} {str(r['first'])[:10]}..{str(r['last'])[:10]} n={r['n']:4d} mean={r['m']:+.4f} "
                  f"sum={r['s']:+.3f} n2share={r['n2share']:.3f} varshare={r['varshare']:.3f}")
        # leave-one-block-out for top 5 blocks by size
        print(" leave-one-block-out (top 5 by n):")
        for b in tab.index[:5]:
            k = d["mymb"].values != b
            rr = summarize(y[k], d["mymb"].values[k])
            print(f"   without mb {b} (n={tab.loc[b, 'n']}): " + fmt(rr, ("n", "G", "gstar", "est", "se", "t", "p_gstar", "p_wcr", "p_decide")))
        # all blocks: worst-case LOO t and est
        loo = []
        for b in tab.index:
            k = d["mymb"].values != b
            rr = cr1(y[k], d["mymb"].values[k])
            loo.append((b, rr["est"], rr["t"], rr["p_gstar"], rr["gstar"]))
        loo = pd.DataFrame(loo, columns=["mb", "est", "t", "p_gstar", "gstar"])
        i = loo["t"].idxmin()
        j = loo["est"].idxmin()
        print(f"  LOO over all {len(loo)} blocks: min t {loo.loc[i, 't']:.3f} (mb {loo.loc[i, 'mb']}, est {loo.loc[i, 'est']:+.4f}, p_G* {loo.loc[i, 'p_gstar']:.4f});"
              f" min est {loo.loc[j, 'est']:+.4f} (mb {loo.loc[j, 'mb']}); max p_G* {loo['p_gstar'].max():.4f}; "
              f"G* range {loo['gstar'].min():.2f}..{loo['gstar'].max():.2f}")
        # CR3 jackknife
        se3 = cr3(y, d["mymb"].values)
        gs = r0["gstar"]
        print(f"  CR3 (cluster jackknife) SE {se3:.4f} vs CR1 {r0['se']:.4f}; t3 {y.mean() / se3:.3f}; p (t, G*-1) "
              f"{stats.t.sf(y.mean() / se3, gs - 1):.5f}; p (t, G-1) {stats.t.sf(y.mean() / se3, r0['G'] - 1):.5f}")
        # pairs block bootstrap of the mean
        gi = np.unique(d["mymb"].values, return_inverse=True)[1]
        G = gi.max() + 1
        S = np.bincount(gi, weights=y, minlength=G)
        n = np.bincount(gi, minlength=G).astype(float)
        rng = np.random.default_rng(4242)
        B = 9999
        idx = rng.integers(0, G, size=(B, G))
        mb_ = S[idx].sum(1) / n[idx].sum(1)
        print(f"  pairs month-block bootstrap (B={B}): SE {mb_.std(ddof=1):.4f}; 95% pct CI ({np.quantile(mb_, .025):+.4f},{np.quantile(mb_, .975):+.4f});"
              f" 98.33% pct upper {np.quantile(mb_, LEVEL):+.4f}; share of draws <= 0: {np.mean(mb_ <= 0):.4f}; "
              f"bootstrap-se t {y.mean() / mb_.std(ddof=1):.3f}")
        # other cluster units
        for lab, g in (("episode", d["myep"].values), ("quarter-block", d["myqb"].values), ("calendar quarter", d["myq"].values),
                       ("calendar month", d["mon"].values), ("fill day", d["day"].values.astype(int)),
                       ("coin (one-way)", d["coin"].values)):
            rr = summarize(y, g)
            print(f"  {lab:18s}: " + fmt(rr, ("n", "G", "gstar", "est", "se", "t", "p_gstar", "p_wcr", "p_decide", "ub")))
        # events
        print(" events removed:")
        ftt_ep = d.loc[(d["day"] >= np.datetime64("2022-11-07")) & (d["day"] <= np.datetime64("2022-11-15")), "myep"].unique()
        ev = {
            "2025-10-10 (day)": d["day"].values == np.datetime64("2025-10-10"),
            "2025-10-10 episode": np.isin(d["myep"].values, d.loc[d["day"] == np.datetime64("2025-10-10"), "myep"].unique()),
            "2021-05-19 (day)": d["day"].values == np.datetime64("2021-05-19"),
            "2021-05-19 episode": np.isin(d["myep"].values, d.loc[d["day"] == np.datetime64("2021-05-19"), "myep"].unique()),
            "FTT episode (Nov 2022)": np.isin(d["myep"].values, ftt_ep),
            "2022-11 month": d["mon"].values == (2022 - 1970) * 12 + 10,
            "2020-03-12 (day)": d["day"].values == np.datetime64("2020-03-12"),
            "2020-03-12 episode": np.isin(d["myep"].values, d.loc[d["day"] == np.datetime64("2020-03-12"), "myep"].unique()),
        }
        ev["all four days"] = ev["2025-10-10 (day)"] | ev["2021-05-19 (day)"] | ev["FTT episode (Nov 2022)"] | ev["2020-03-12 (day)"]
        ev["all four episodes"] = ev["2025-10-10 episode"] | ev["2021-05-19 episode"] | ev["FTT episode (Nov 2022)"] | ev["2020-03-12 episode"]
        for k, m in ev.items():
            keep = ~m
            dd = d[keep]
            # recompute clusters on the remaining fills (as the runner does for its gates? it uses the full-sample mb)
            rr = summarize(y[keep], d["mymb"].values[keep])
            ep_tab = d.loc[m, ["day"]].drop_duplicates()
            print(f"   without {k:24s} (drop {m.sum():4d}; days {', '.join(sorted(set(str(x)[:10] for x in d.loc[m, 'day'])))[:80]}): "
                  + fmt(rr, ("n", "G", "gstar", "est", "se", "t", "p_gstar", "p_wcr", "p_decide")))
        # halves
        print(" halves (fill time UTC, month-block CR1 within half):")
        for h in (0, 1):
            k = d["myhalf"].values == h
            rr = summarize(y[k], d["mymb"].values[k])
            print(f"   half {h + 1}: " + fmt(rr, ("n", "G", "gstar", "est", "se", "t", "p_gstar", "p_wcr", "ci_t", "ci_boot")))
        # fills near the half boundary
        near = d[(d["t"] >= pd.Timestamp("2022-12-01", tz="UTC")) & (d["t"] < pd.Timestamp("2023-02-01", tz="UTC"))]
        print(f"  fills 2022-12-01..2023-01-31: {len(near)}; days: {sorted(set(str(x)[:10] for x in near['day']))}")
        last_h1 = d.loc[d["myhalf"] == 0, "t"].max()
        first_h2 = d.loc[d["myhalf"] == 1, "t"].min()
        print(f"  last fill in half 1: {last_h1}; first in half 2: {first_h2}")
        d.to_pickle(OUT + f"d_{name}.pkl")


if __name__ == "__main__":
    main()
