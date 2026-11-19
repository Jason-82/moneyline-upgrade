"""Step 4: the sheet's column 5 per coin and rung (own F1 fills; np.quantile like sheet_stats): life sum (record's
reading) against the fill's own window (the prereg's C(L)); a few user-style coins and the ratio distribution."""
import numpy as np
import pandas as pd

OUTD = ("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
        "capcap-impact")
R = pd.read_parquet(f"{OUTD}/s2_fills.parquet")
rows = []
for (coin, rg), g in R.groupby(["coin", "rung"]):
    rows.append(dict(coin=coin, rung=rg, fills=len(g),
                     life_p50=np.median(g.eng_agg_life), life_p10=np.quantile(g.eng_agg_life, .1),
                     first_p50=np.median(g.my_agg_first), first_p10=np.quantile(g.my_agg_first, .1)))
T = pd.DataFrame(rows)
T["qmax_life"] = 0.25 * T.life_p10
T["qmax_first"] = 0.25 * T.first_p10
T["ratio"] = T.qmax_life / T.qmax_first
print("coin-rungs", len(T), "ratio of Q_max (life / own window): median %.1f, p10 %.1f, p90 %.1f" % (
    T.ratio.median(), T.ratio.quantile(.1), T.ratio.quantile(.9)))
print("coin-rungs whose Q_max is below $10k: life %d, own window %d (of %d)" % (
    (T.qmax_life < 1e4).sum(), (T.qmax_first < 1e4).sum(), len(T)))
user = ["NEAR", "AAVE", "SOL", "AVAX", "LINK", "ETH", "BTC", "DOGE", "INJ", "SUI", "TAO", "RENDER"]
pd.set_option("display.width", 250)
print(T[T.coin.isin(user)].to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
T.to_csv(f"{OUTD}/s4_sheet_coin_rung.csv", index=False)
