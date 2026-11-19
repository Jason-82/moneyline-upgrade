"""Step 6: could H1 be a mechanical artifact? Bar-level splits from my own pass (bars_pass2), capacity from fills."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
import numpy as np
import pandas as pd
from common import *

R = pd.read_parquet(f"{OUT}/bars_pass2.parquet")
O = pd.read_parquet(f"{OUT}/h1rows2.parquet")
F = load_fills(cols=["fill_id", "agg_m0", "c1_m0", "agg_first", "agg_life", "c1_first", "c1_life", "agg_missing",
                     "cap_src", "n_windows", "share_1k_1", "share_10k_1", "share_100k_1", "t_F3_1", "t_F3d_1",
                     "idx_low_rel", "idx_missing", "s24", "s6", "s1", "mw", "gap_through", "open_below",
                     "prev_close_above"])
J = O.merge(R.drop(columns=["coin", "g_me", "S_me"]), on="fill_id").merge(F, on="fill_id", suffixes=("", "_f"))
N, tot = len(J), J.delta.sum()
print("joined", N)


def show(mask, label):
    m = np.asarray(mask, bool)
    a, b = cr1(J.delta[m], J.mb_me[m]), cr1(J.delta[~m], J.mb_me[~m])
    print(f"  {label}: n={m.sum()} ({m.mean():.1%}); share of sum {J.delta[m].sum() / tot:+.1%}; "
          f"mean r_f {J.r[m].mean():+.2%} twin {J.twin_mean[m].mean():+.2%} delta {J.delta[m].mean():+.2%}\n"
          f"     H1 without them: {fmt(b)}")


# ---- 0. re-check of my independent exit with the tolerant ceil
d = (J.r_me - J.r).abs()
print("my r_f == engine r (|d|<=1e-12):", (d <= 1e-12).sum(), "of", N, " target exact:", (J.T_me == J.target).sum(),
      " exit kinds:", (J.kind_me == J.exit_kind).sum(), " exit_t:", (J.exit_t_me == J.exit_t).sum())
own = J[~J.pooled_me]
dt = (own.twin_me - own.twin_mean).abs()
print("own twins: fills", len(own), " twin mean |d|<=1e-12:", (dt <= 1e-12).sum(), " |d|<=1e-4:", (dt <= 1e-4).sum(),
      " max:", dt.max(), " fills with segment-crossing twins:", (own.twin_crossed > 0).sum())
xm = own[(dt > 1e-12)]
print("   mismatches without crossing twins:", int((xm.twin_crossed == 0).sum()))
print(xm[["fill_id", "coin", "twin_me", "twin_mean", "twin_crossed"]].head(12).to_string())

# ---- 1. gap-through and opening below L (raw bars)
print("\n== gap-through ==")
print("minute's high < L (gap-through):", int((J.h < J.L).sum()), " opened below L:", int((J.o < J.L).sum()),
      " engine flags gap_through:", int(J.gap_through.fillna(0).astype(bool).sum()),
      " open_below:", int(J.open_below.fillna(0).astype(bool).sum()),
      " previous live close at or below L:", int((J.prev_c <= J.L).sum()))
show(J.o < J.L, "opened below L")

# ---- 2. spike vs slide
print("\n== spike vs slide ==")
J["depth"] = 1 - J.l / J.L                      # how far the minute's low went below L
J["prev_above"] = J.prev_c / J.L - 1            # how far above L the previous live minute closed
J["drop1"] = 1 - J.l / J.prev_c                 # one-minute drop from the previous close to the low
J["recov_in_min"] = J.c >= J.L
bins = [-1, 0.01, 0.03, 0.10, 1]
J["depth_bin"] = pd.cut(J.depth, bins, labels=["<1%", "1-3%", "3-10%", ">=10%"])
J["prev_bin"] = pd.cut(J.prev_above, [-1, 0.01, 0.03, 0.10, 10], labels=["<1%", "1-3%", "3-10%", ">=10%"])


def tab(by):
    g = J.groupby(by, observed=True)
    t = pd.DataFrame({"n": g.size(), "r_f": g.r.mean(), "twin": g.twin_mean.mean(), "delta": g.delta.mean(),
                      "share": g.delta.sum() / tot, "hit": g.exit_kind.apply(lambda s: (s == "target").mean())})
    print(t.to_string(float_format=lambda x: f"{x:+.4f}"))


print("-- by depth of the fill minute's low below L"); tab("depth_bin")
print("-- by how far above L the previous minute closed"); tab("prev_bin")
print("-- by in-minute recovery (fill minute closed at or above L)"); tab("recov_in_min")
J["spike"] = (J.depth >= 0.03) & J.recov_in_min
J["slide"] = J.prev_above < 0.01
show(J.spike, "single-minute spikes (low >= 3% below L, minute closed back at/above L)")
show(J.slide, "slides (previous minute closed < 1% above L)")
for nm, col in (("s1", "s1"), ("s24", "s24")):
    q = pd.qcut(J[col], 3, labels=["slow", "mid", "fast"])
    print(f"-- by speed {nm} tercile (engine's speed field)")
    g = J.groupby(q, observed=True)
    print(pd.DataFrame({"n": g.size(), "delta": g.delta.mean(), "share": g.delta.sum() / tot}).to_string())

# ---- 3. possible bad prints
print("\n== possible bad prints (low > 10% below the previous close, recovering within 5 minutes) ==")
big = J.l < 0.9 * J.prev_c
mx5 = np.fmax(J.c, J.next5_maxc)
defs = {"A: back within 5% of the previous close within 5 min": big & (mx5 >= 0.95 * J.prev_c),
        "B: recovers half the drop within 5 min": big & (mx5 >= J.prev_c - 0.5 * (J.prev_c - J.l)),
        "C: fill minute itself closes back at/above L": big & (J.c >= J.L),
        "D: any drop >10% in one minute": big}
for k, m in defs.items():
    print(k)
    show(m, "flagged")
    f3 = J.t_F3_1[m] >= 0
    print(f"     of which F3 (index, s=1%) also filled the bid: {int(f3.sum())}; "
          f"index low in the fill minute <= L/1.01: {int((J.idx_low_rel[m] <= 1 / 1.01).sum())}; "
          f"index missing: {int(J.idx_missing[m].fillna(0).astype(bool).sum())}")
m = defs["B: recovers half the drop within 5 min"]
print(J.loc[m, ["fill_id", "coin", "ts", "L", "prev_c", "o", "l", "c", "next5_maxc", "r", "twin_mean", "delta",
                "exit_kind", "t_F3_1", "idx_low_rel", "agg_m0", "c1_m0"]].sort_values("delta", ascending=False)
      .head(25).to_string())

# ---- 4. the pre-registered bad-print sensitivity (§4.1): < $1k seller notional below L in the fill minute alone,
#         or the index low in that minute above L
print("\n== §4.1 bad-print sensitivity ==")
cap0 = np.where(J.cap_src == "agg", J.agg_m0, J.c1_m0)
print("cap_src:", J.cap_src.value_counts().to_dict(), " agg_missing:", J.agg_missing.value_counts().to_dict())
thin = cap0 < 1000
idx_above = J.idx_low_rel > 1
print("fill-minute seller notional below L < $1k:", int(thin.sum()), " index low above L in the fill minute:",
      int(idx_above.sum()), " either:", int((thin | idx_above).sum()), " index missing:",
      int(J.idx_missing.fillna(0).astype(bool).sum()))
show(thin | idx_above, "§4.1 bad-print rule")
show(thin, "thin fill minute only")
show(idx_above, "index above L only")

# ---- 5. capacity terciles
print("\n== capacity ==")
capw = np.where(J.cap_src == "agg", J.agg_first, J.c1_first)
J["cap_first"] = capw
J["cap_m0"] = cap0
for col in ("cap_first", "cap_m0"):
    q = pd.qcut(J[col].rank(method="first"), 3, labels=["low", "mid", "high"])
    g = J.groupby(q, observed=True)
    print(f"-- by tercile of {col} (seller-initiated $ below L)")
    print(pd.DataFrame({"n": g.size(), "cap_median": g[col].median(), "r_f": g.r.mean(), "twin": g.twin_mean.mean(),
                        "delta": g.delta.mean(), "share": g.delta.sum() / tot}).to_string(
        float_format=lambda x: f"{x:+.4f}" if abs(x) < 10 else f"{x:,.0f}"))
    for lab in ("low", "mid", "high"):
        print(f"   {lab}: {fmt(cr1(J.delta[q == lab], J.mb_me[q == lab]))}")
print("fills with < $10k of capacity in the first window:", int((capw < 1e4).sum()))
show(capw < 1e4, "first-window capacity < $10k")
show(J.share_10k_1 < 1, "Q=$10k not fully filled (theta=1)")
w = np.minimum(1e4, capw)
print("dollar-weighted (min($10k, first-window capacity)) mean delta:", np.sum(w * J.delta) / np.sum(w))

# ---- 6. decomposition around the go-live time
print("\n== decomposition (gross, before costs) ==")
J["pre_fill"] = J.o_g / J.L - 1                   # price at go-live vs L (what H2R's alert buyer pays extra)
J["post_fill"] = J.exit_px_me / J.o_g - 1          # from the go-live open to the exit
J["in_min"] = J.c / J.L - 1
print("fills: mean c_m/L-1 %.4f  mean o_g/L-1 %.4f  mean exit/o_g-1 %.4f  mean exit/L-1 %.4f" % (
    J.in_min.mean(), J.pre_fill.mean(), J.post_fill.mean(), (J.exit_px_me / J.L - 1).mean()))
ow = J[~J.pooled_me]
print("own twins: mean o_g/o_e-1 %.4f  mean exit/o_e-1 %.4f" % (ow.twin_pre.mean(), ow.twin_gross.mean()))
print("same fills: mean o_g/L-1 %.4f, exit/L-1 %.4f, exit/o_g-1 %.4f" % (
    ow.pre_fill.mean(), (ow.exit_px_me / ow.L - 1).mean(), ow.post_fill.mean()))
post_tw = (1 + ow.twin_gross) / (1 + ow.twin_pre) - 1
print("post-go-live: fills %.4f vs twins (approx.) %.4f -> difference %.4f" % (
    ow.post_fill.mean(), post_tw.mean(), ow.post_fill.mean() - post_tw.mean()))
print("pre-go-live: fills %.4f vs twins %.4f -> difference %.4f" % (
    ow.pre_fill.mean(), ow.twin_pre.mean(), ow.pre_fill.mean() - ow.twin_pre.mean()))
print("go-live lag after rule-M time (first live bar - g), fills:", (J.t_g - J.g_me).describe().to_dict())
print("price above R1/2 at some point before go-live (rebound came before the sell was live):",
      int((J.maxh_pre >= J.target).sum()))
J.to_parquet(f"{OUT}/joined2.parquet")
