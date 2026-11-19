"""Step 3 (independent): the full F3 (s = 1%) row the bot line and the R sentence would carry, with my own month-block
clusters and CR1 / G* arithmetic (prereg §10.2), checked first against rows of record that exist (H1 F1, H1 beside
F3_1, the bot F1 row). No stinkbid_* import.

Month-blocks (§10.2): calendar months of the fill, merged when an event episode spans two months; an episode is a run
of fill days at most 3 days apart (UTC fill days, from the fill minute of the rule).
"""
import json
import numpy as np
import pandas as pd
from scipy import stats

OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/f3-beside-flip/"
P = json.load(open("analysis_2026/results_stinkbid/primary/primary.json"))


def month_blocks(tmin):
    t = pd.to_datetime(np.asarray(tmin, np.int64) * 60_000_000_000, utc=True)
    day = t.normalize()
    mon = t.year * 100 + t.month
    days = np.sort(day.unique())
    # episodes: runs of fill days at most 3 days apart
    ep_of_day, e = {}, 0
    for i, dd in enumerate(days):
        if i and (dd - days[i - 1]) > pd.Timedelta(days=3):
            e += 1
        ep_of_day[dd] = e
    ep = np.array([ep_of_day[x] for x in day])
    # union months that share an episode
    parent = {m: m for m in np.unique(mon)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e_ in np.unique(ep):
        ms = np.unique(mon[ep == e_])
        for m in ms[1:]:
            a, b = find(ms[0]), find(m)
            if a != b:
                parent[b] = a
    return np.array([find(m) for m in mon]), ep


def row(y, cl, level=1 - 0.05 / 3):
    y = np.asarray(y, float)
    n = len(y)
    th = y.mean()
    e = y - th
    g = pd.Series(e).groupby(cl).sum().to_numpy()
    ng = pd.Series(np.ones(n)).groupby(cl).sum().to_numpy()
    G = len(g)
    se = np.sqrt(G / (G - 1) * np.sum(g ** 2) / n ** 2)
    gstar = np.sum(ng ** 2) ** 2 / np.sum(ng ** 4)
    df = gstar - 1
    q = stats.t.ppf(0.975, df)
    return dict(n=n, G=G, gstar=gstar, estimate=th, se=se, ci95=(th - q * se, th + q * se),
                ub_t=th + stats.t.ppf(level, df) * se, p_gstar=float(stats.t.sf(th / se, df)))


f1 = pd.read_parquet(OUT + "f1_flip_sample.parquet")
f3 = pd.read_parquet(OUT + "f3_flip_sample.parquet")
f3b = pd.read_parquet(OUT + "f3_bot_sample.parquet")
# the F1 bot sample: re-read from the run (own filter, as step 1)
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1/"
F = pd.read_parquet(RUN + "fills.parquet", columns=["fill_id", "t_F1"])
O = pd.read_parquet(RUN + "outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "r", "delta", "complete"],
                    filters=[("rule", "==", "F1"), ("exit", "==", "FLIP_bot"), ("cost", "==", "C-RH")])
f1b = F[F.t_F1 >= 0].merge(O[O.complete.astype(bool)], on="fill_id")
f1b = f1b[np.isfinite(f1b.delta)]

out = {}
for name, d, tcol, rec in [("H1 F1 X-FLIP Delta (record)", f1, "t_F1", P["rows"]["H1"]),
                           ("H1 F3_1 X-FLIP Delta (beside, record)", f3, "t_F3_1", P["beside"]["H1"]["F3_1"]),
                           ("bot F1 X-FLIP-bot Delta (record)", f1b, "t_F1", P["bot"]["row"]),
                           ("bot F3_1 X-FLIP-bot Delta (NOT in record)", f3b, "t_F3_1", None),
                           ("R F1 mean r_f (record: beside.H1.mean_r)", f1, "t_F1", None),
                           ("R F3_1 mean r_f (NOT in record)", f3, "t_F3_1", None)]:
    mb, ep = month_blocks(d[tcol])
    yv = d["r"] if name.startswith("R ") else d["delta"]
    r = row(yv, mb)
    r["n_episodes"] = int(len(np.unique(ep)))
    if rec is not None:
        r["record"] = {k: rec.get(k) for k in ("n", "G", "gstar", "estimate", "se", "ub_t", "p_gstar", "ci95", "ci_lo",
                                               "ci_hi") if k in rec}
    out[name] = r
    print(name)
    print("   mine  :", {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items() if k != "record"})
    if rec is not None:
        print("   record:", r["record"])
if __name__ == "__main__":
    print("record beside.H1.mean_r =", P["beside"]["H1"]["mean_r"])
json.dump(out, open(OUT + "s3_rows.json", "w"), indent=1, default=float)
