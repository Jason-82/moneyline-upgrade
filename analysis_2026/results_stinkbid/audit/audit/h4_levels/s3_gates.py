"""Step 3: H4 gates (argmax method's b in both halves, without the worst month-block, under F3), the F3-kept row,
single-event / concentration rows, and checks on the stacked design (placebo levels, depths, band, M7 start)."""
import sys
import json
import resource
import numpy as np
import pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h4_levels")
import h4_common as hc

OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h4_levels"
pd.set_option("display.width", 250)
fr = {m: pd.read_parquet(f"{OUT}/frame_F1_{m}.parquet") for m in hc.METHODS}
f3 = {m: pd.read_parquet(f"{OUT}/frame_F3_1_{m}.parquet") for m in hc.METHODS}


def b_of(g, mask=None, blk="block"):
    if mask is not None:
        g = g[np.asarray(mask, bool)]
    f = hc.fe_fit(g.y, np.column_stack([g.realf, g.depth]), g.cw, g[blk])
    if f is None or not np.all(np.isfinite(f["theta"])):
        return np.nan, 0, 0
    return float(f["theta"][0]), f["n"], f["G"]


print("=== gates per method (F1 partition = union month-blocks); the argmax method is M7")
rows = []
for m in hc.METHODS:
    g = fr[m]
    h = (g.time.to_numpy() >= hc.HALF)
    b1, n1, G1 = b_of(g, ~h)
    b2, n2, G2 = b_of(g, h)
    worst = (np.inf, None)
    per_block = []
    for blk in pd.unique(g.block):
        bb, _, _ = b_of(g, g.block.to_numpy() != blk)
        per_block.append((blk, bb))
        if np.isfinite(bb) and bb < worst[0]:
            worst = (bb, blk)
    b3 = b_of(f3[m])[0]
    wb = pd.Timestamp(int(worst[1]) * 0, unit="D") if False else worst[1]
    rows.append(dict(method=m, b_half1=b1, n_half1=n1, G_half1=G1, b_half2=b2, n_half2=n2, G_half2=G2,
                     b_no_worst_block=worst[0], worst_block_month=str(np.datetime64(int(worst[1]), "M")),
                     b_F3=b3))
print(pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v:.6g}"))
gm = pd.DataFrame(rows).set_index("method").loc["M7"]
gates = dict(half1_pos=bool(gm.b_half1 > 0), half2_pos=bool(gm.b_half2 > 0), no_worst_block_pos=bool(gm.b_no_worst_block > 0),
             f3_pos=bool(gm.b_F3 > 0))
print("M7 gates (mine):", gates)
ref = json.load(open("analysis_2026/results_stinkbid/primary/primary.json"))
print("M7 gates (record):", ref["gates"]["H4"])

# M7 half 1 detail: fills by year and real share
g = fr["M7"]
h = g.time.to_numpy() >= hc.HALF
print(f"\nM7 half1: frame rows {int((~h).sum())}, real {int(g.realf[~h].sum())}; first fill {g.time.min()}; "
      f"half2 rows {int(h.sum())}, real {int(g.realf[h].sum())}")

# ---- F3-kept row: F1 stacked fills whose own bid also filled under F3 (s = 1%)
B, F, O = hc.load()
kept = set(F.loc[F.t_F3_1 >= 0, "fill_id"].tolist())
fk = {m: fr[m][fr[m].fill_id.isin(kept)].reset_index(drop=True).copy() for m in hc.METHODS}
allt = np.concatenate([fk[m].time.to_numpy() for m in hc.METHODS])
lab, _ = hc.month_blocks(allt)
pos = 0
for m in hc.METHODS:
    k = len(fk[m])
    fk[m]["block_k"] = lab[pos:pos + k]
    pos += k
rk = []
for m in hc.METHODS:
    gg = fk[m]
    f = hc.fe_fit(gg.y, np.column_stack([gg.realf, gg.depth]), gg.cw, gg.block_k)
    b, se = f["theta"][0], f["se"][0]
    rk.append(dict(method=m, n=f["n"], n_cw=f["n_fe"], G=f["G"], gstar=f["gstar"], b=b, se=se, t=b / se,
                   p_t=hc.tsf(b / se, f["gstar"] - 1)))
rk = pd.DataFrame(rk)
print(f"\n=== F3-kept (F1 fills whose bid also filled under F3_1): G_union = {len(np.unique(lab))}")
print(rk.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
jm = int(np.argmax(rk.t))
print("T", rk.t[jm], "argmax", rk.method[jm], "p_G*", min(1, 4 * rk.p_t[jm]),
      "| record:", {k: ref["f3kept"]["H4"][k] for k in ("T", "argmax", "p_gstar", "p_decide", "G_union", "n")})

# ---- concentration and single events for the argmax method (its own episodes / month-blocks, as the runner does)
g = fr["M7"].copy()
mb_own, ep_own = hc.month_blocks(g.time.to_numpy())
g["mb_own"], g["ep_own"] = mb_own, ep_own
u, c = np.unique(ep_own, return_counts=True)
o = np.lexsort((u, -c))
top = u[o[:3]]
sel = np.isin(ep_own, top)
day = g.time.to_numpy().astype("datetime64[D]")
names = []
for e in top:
    dd = day[ep_own == e]
    names.append(f"{dd.min()}..{dd.max()}")
uu, cc = np.unique(mb_own, return_counts=True)
tb = uu[np.lexsort((uu, -cc))[0]]
rob = dict(estimate=b_of(g)[0], top3_share=float(sel.mean()), top3_names=names, top3_without=b_of(g, ~sel)[0],
           without_2025_10_10=b_of(g, day != np.datetime64("2025-10-10"))[0], n_2025_10_10=int((day == np.datetime64("2025-10-10")).sum()),
           without_2021_05_19=b_of(g, day != np.datetime64("2021-05-19"))[0],
           top_block=str(np.datetime64(int(tb), "M")), without_top_block=b_of(g, mb_own != tb)[0])
print("\n=== M7 concentration / single events (mine):", json.dumps(rob, default=str))
print("record:", json.dumps(ref["robust"]["H4"]))

# ---- design checks on bids
Bb = pd.read_parquet(f"{hc.RUN}/bids.parquet", columns=["variant", "cw", "real", "shift", "L", "P0", "sigma30", "atr_pct",
                                                      "tick", "delta", "t0", "live_from", "life_end", "coin"])
Bb["method"] = Bb.variant.map(hc.NAME)
r = Bb[Bb.real].set_index(["method", "cw"])
p = Bb[~Bb.real].join(r[["L", "delta"]], on=["method", "cw"], rsuffix="_real")
ratio = p.L / p.L_real
expect = np.exp(p["shift"] * p.atr_pct)
dev_ticks = (p.L - p.L_real * expect) / p.tick
print("\n=== placebo checks")
print("atr_pct quantiles:", Bb.atr_pct.quantile([0.01, 0.5, 0.99]).round(4).tolist())
print("placebo L - L_real*exp(shift*atr_pct), in ticks: min %.3f max %.3f" % (dev_ticks.min(), dev_ticks.max()))
dep = p.delta - p.delta_real
dexp = -p["shift"] * p.atr_pct / p.sigma30
print("depth - (-shift*atr_pct/sigma30): max abs %.4g  (tick rounding)" % (dep - dexp).abs().max())
print("depth by shift (median):", dep.groupby(p["shift"]).median().round(4).to_dict())
rr = Bb[Bb.real]
print("real delta range per method:", rr.groupby("method").delta.agg(["min", "max"]).round(4).to_dict("index"))
print("placebos per real level:", Bb[~Bb.real].groupby(["method", "cw"]).size().value_counts().to_dict())
life = (Bb.life_end - Bb.live_from) / 1440
print("life days (quantiles):", life.quantile([0, 0.01, 0.5, 1]).round(4).tolist())
print("M7 first t0:", pd.Timestamp(int(rr[rr.method == "M7"].t0.min()) * 60, unit="s"))
print("t0 weekday/hour set:", sorted(set(pd.to_datetime(Bb.t0.drop_duplicates() * 60, unit="s").dt.strftime("%a %H:%M"))))
# stacked fills: per coin-week at most one real fill; real fill present?
for m in hc.METHODS:
    g = fr[m]
    k = g.groupby("cw").agg(nr=("realf", "sum"), n=("realf", "size"))
    print(f"{m}: coin-weeks {len(k)}, with real fill {int((k.nr > 0).sum())}, max real per cw {int(k.nr.max())}, "
          f"singletons {int((k.n == 1).sum())}, cw with >=2 rows and no real fill {int(((k.n > 1) & (k.nr == 0)).sum())}")
print("peak RSS MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
