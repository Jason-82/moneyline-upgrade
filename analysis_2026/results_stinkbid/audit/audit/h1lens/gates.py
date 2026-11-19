"""Own recomputation of the H1 / H2R gates, the beside rows, the bot-latency row and the E sensitivity from the cached
engine runs (prereg §10.3 definitions). Does not import stinkbid_stats or stinkbid_desc."""
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1lens")
from core import my_episodes, my_blocks, summarize, fmt  # own code

R = "data/stinkbid/runs/outcomes/"


def tmin_to_ts(m):
    return pd.to_datetime(np.asarray(m, np.int64) * 60_000_000_000, utc=True)


def add_cl(d):
    t = d["time"]
    tn = t.dt.tz_localize(None).values
    d["day"] = tn.astype("datetime64[D]")
    d["mon"] = tn.astype("datetime64[M]").astype(int)
    d["ep"] = my_episodes(d["day"].values)
    d["mb"] = my_blocks(d["mon"].values, d["ep"].values)
    d["hf"] = (t >= pd.Timestamp("2023-01-01", tz="UTC")).astype(int).values
    return d


def per_fill(run, rule, exit, cost):
    F = pd.read_parquet(R + run + "/fills.parquet", columns=["fill_id", "coin", "t_" + rule])
    F = F[F["t_" + rule] >= 0]
    O = pd.read_parquet(R + run + "/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "delta", "complete"],
                        filters=[("rule", "==", rule), ("exit", "==", exit)])
    O = O[(O.cost == cost) & O.complete.astype(bool)]
    d = F.merge(O[["fill_id", "r", "delta"]], on="fill_id")
    d = d[np.isfinite(d.delta)].reset_index(drop=True)
    d["y"] = d["delta"]
    d["time"] = tmin_to_ts(d["t_" + rule])
    return add_cl(d.sort_values("time").reset_index(drop=True))


def per_bench(run, rule, col="alert_M"):
    F = pd.read_parquet(R + run + "/fills.parquet", columns=["fill_id", "coin", "t_" + rule])
    F = F[F["t_" + rule] >= 0]
    Bn = pd.read_parquet(R + run + "/bench.parquet", columns=["fill_id", "rule", col])
    Bn = Bn[Bn.rule == rule]
    d = F.merge(Bn[["fill_id", col]], on="fill_id")
    d["y"] = pd.to_numeric(d[col], errors="coerce")
    d = d[np.isfinite(d.y)].reset_index(drop=True)
    d["time"] = tmin_to_ts(d["t_" + rule])
    return add_cl(d.sort_values("time").reset_index(drop=True))


def gates(d, ub, f3, rpos=None):
    y = d["y"].values
    g = {}
    if rpos is not None:
        g["mean_r_pos"] = rpos
    for h in (0, 1):
        g[f"half{h + 1}_pos"] = (y[d.hf.values == h].mean() > 0, y[d.hf.values == h].mean())
    # worst block: removal lowers the mean most
    s = d.groupby("mb")["y"].agg(["sum", "size"])
    rest = (y.sum() - s["sum"]) / (len(y) - s["size"])
    g["no_worst_block_pos"] = (rest.min() > 0, rest.min())
    # biggest episode by fill count (ties: earliest)
    c = d.groupby("ep").size()
    big = c.index[np.lexsort((c.index.values, -c.values))[0]]
    m = y[d.ep.values != big].mean()
    g["no_biggest_episode_pos"] = (m > 0, m)
    g["u_b_pos"] = (ub["y"].mean() > 0, ub["y"].mean(), len(ub))
    g["f3_pos"] = (f3["y"].mean() > 0, f3["y"].mean(), len(f3))
    return g


def show_gates(name, g):
    print(f" {name} gates:")
    for k, v in g.items():
        print(f"   {k}: {v}")


def main():
    # ---------------- H1
    d1 = per_fill("P1__U_Q1", "F1", "FLIP", "C-RH")
    ub1 = per_fill("P1__U_B", "F1", "FLIP", "C-RH")
    f31 = per_fill("P1__U_Q1", "F3_1", "FLIP", "RH")
    print("H1 main:", fmt(summarize(d1.y.values, d1.mb.values)), " mean r", round(d1.r.mean(), 5))
    show_gates("H1", gates(d1, ub1, f31, rpos=(d1.r.mean() > 0, d1.r.mean())))
    for lab, d in (("F3_1", f31), ("F3d_1", per_fill("P1__U_Q1", "F3d_1", "FLIP", "RH")),
                   ("F3_3", per_fill("P1__U_Q1", "F3_3", "FLIP", "RH")), ("U_B", ub1),
                   ("U_C", per_fill("P1__U_C", "F1", "FLIP", "C-RH")), ("U_C_F3", per_fill("P1__U_C", "F3_1", "FLIP", "RH"))):
        print(f"   beside {lab:7s}: " + fmt(summarize(d.y.values, d.mb.values, do_wild=False), ("n", "G", "gstar", "est", "se", "t", "ci_t")))
    # ---------------- bot latency
    db = per_fill("P1__U_Q1", "F1", "FLIP_bot", "C-RH")
    ubb = per_fill("P1__U_B", "F1", "FLIP_bot", "C-RH")
    f3b = per_fill("P1__U_Q1", "F3_1", "FLIP_bot", "RH")
    rb = summarize(db.y.values, db.mb.values)
    print("H1 bot:", fmt(rb), " mean r", round(db.r.mean(), 5))
    show_gates("H1 bot", gates(db, ubb, f3b, rpos=(db.r.mean() > 0, db.r.mean())))
    # Holm with the bot p in H1's place (the other two as of record)
    p = {"H1bot": rb["p_decide"], "H2R": 0.021618807633077927, "H4": 0.8409084875084051}
    ps = sorted(p.items(), key=lambda kv: kv[1])
    run, adj = 0, {}
    for i, (k, v) in enumerate(ps):
        run = max(run, (3 - i) * v)
        adj[k] = min(1, run)
    print(" Holm with bot in H1's place:", {k: round(v, 5) for k, v in adj.items()})
    # paired difference rule M vs bot
    m = d1[["fill_id", "y"]].merge(db[["fill_id", "y"]], on="fill_id", suffixes=("_M", "_bot"))
    print(f" bot minus rule M (paired, n={len(m)}): mean {(m.y_bot - m.y_M).mean():+.5f}")
    # ---------------- H2R
    d2 = per_bench("P1__U_Q1", "F1")
    ub2 = per_bench("P1__U_B", "F1")
    f32 = per_bench("P1__U_Q1", "F3_1")
    print("H2R main:", fmt(summarize(d2.y.values, d2.mb.values)))
    show_gates("H2R", gates(d2, ub2, f32))
    for lab, d in (("F3_1", f32), ("F3d_1", per_bench("P1__U_Q1", "F3d_1")), ("F3_3", per_bench("P1__U_Q1", "F3_3")),
                   ("U_B", ub2), ("U_C", per_bench("P1__U_C", "F1")), ("U_C_F3", per_bench("P1__U_C", "F3_1"))):
        print(f"   beside {lab:7s}: " + fmt(summarize(d.y.values, d.mb.values, do_wild=False), ("n", "G", "gstar", "est", "se", "t", "ci_t")))
    # H2R second half with its own clusters and with a placement-time reading (bid t0)
    h2 = d2[d2.hf == 1]
    r2 = summarize(h2.y.values, h2.mb.values)
    print(" H2R half 2 (fill time):", fmt(r2, ("n", "G", "gstar", "est", "se", "t", "ci_t", "ci_boot")))
    Fb = pd.read_parquet(R + "P1__U_Q1/fills.parquet", columns=["fill_id", "t0"])
    x = d2.merge(Fb, on="fill_id")
    t0 = pd.to_datetime(x["t0"], utc=True) if not np.issubdtype(x["t0"].dtype, np.integer) else tmin_to_ts(x["t0"])
    hp = np.asarray(t0 >= pd.Timestamp("2023-01-01", tz="UTC"))
    print(f" H2R half 2 by placement time t0: n={hp.sum()} mean {x.y.values[hp].mean():+.5f}; half 1 n={(~hp).sum()} mean {x.y.values[~hp].mean():+.5f};"
          f" fills whose half differs between readings: {(hp != (x.hf.values == 1)).sum()}")
    # H2R decomposition of half 2 by year
    for yr, g in h2.groupby(h2.time.dt.year):
        print(f"   H2R {yr}: n={len(g)} mean {g.y.mean():+.4f}")
    # ---------------- E sensitivity for H1
    r1 = summarize(d1.y.values, d1.mb.values)
    for E in (0.0375, 0.0226):
        print(f" H1 E={E:.4f}: ub {r1['ub']:+.4f} -> NO EDGE {r1['ub'] < E}; one-sided t vs E {(r1['est'] - E) / r1['se']:.3f}, "
              f"p(t, G*-1) {stats.t.sf((r1['est'] - E) / r1['se'], r1['gstar'] - 1):.4f}")
    # concentration: top-3 episodes by fill count and by contribution
    for name, d in (("H1", d1), ("H2R", d2)):
        tot = d.y.sum()
        c = d.groupby("ep").agg(n=("y", "size"), s=("y", "sum"), first=("day", "min"), last=("day", "max"))
        byn = c.iloc[np.lexsort((c.index.values, -c.n.values))[:3]]
        bys = c.sort_values("s", ascending=False).head(3)
        print(f" {name} top-3 episodes by fills {[(str(a)[:10], int(n)) for a, n in zip(byn['first'], byn.n)]}: share of total {byn.s.sum() / tot:.3f};"
              f" by contribution {[(str(a)[:10], int(n), round(s, 2)) for a, n, s in zip(bys['first'], bys.n, bys.s)]}: share {bys.s.sum() / tot:.3f};"
              f" mean without them {d.y[~d.ep.isin(bys.index)].mean():+.4f}")


if __name__ == "__main__":
    main()
