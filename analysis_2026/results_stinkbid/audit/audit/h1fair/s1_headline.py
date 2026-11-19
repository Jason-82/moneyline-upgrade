"""Step 1: reproduce H1's headline from outcomes.parquet; check samples_H1.csv; pooled twins; x30 / pool rows."""
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/h1fair")
import numpy as np
import pandas as pd
from common import *

o = load_out()
print("H1 rows (F1, FLIP, M, C-RH):", len(o), "unique fill_id:", o.fill_id.nunique())
print(o.exit_kind.value_counts(dropna=False).to_string())
print("complete:", o.complete.value_counts().to_dict())
print("finite r:", np.isfinite(o.r).sum(), "finite delta:", np.isfinite(o.delta).sum(),
      "finite twin_mean:", np.isfinite(o.twin_mean).sum())

F = load_fills(cols=["fill_id", "coin", "t_F1", "i_F1", "rung", "L", "P0", "sigma30", "tick", "episode",
                     "month_block", "half", "in_U_Q1", "gap_through", "open_below", "prev_close_above",
                     "real", "method", "variant"])
F1 = F[F.i_F1 >= 0].copy()
print("fills table rows:", len(F), "with F1 fill:", len(F1), "in_U_Q1:", F1.in_U_Q1.sum())
print("fills method/variant/real:", F1.method.value_counts().to_dict(), F1.variant.value_counts().to_dict(),
      F1.real.value_counts().to_dict())

s = pd.read_csv(f"{RES}/primary/samples_H1.csv")
print("samples_H1 rows:", len(s))
m = s.merge(o[["fill_id", "r", "delta", "twin_mean", "twin_pooled", "exit_kind", "complete"]], on="fill_id",
            how="left")
print("max |y - delta|:", np.nanmax(np.abs(m.y - m.delta)), " max |r - r|:", np.nanmax(np.abs(m.r_x - m.r_y)))
miss = o[~o.fill_id.isin(s.fill_id)]
print("outcome rows not in samples_H1:", len(miss))
print(miss[["fill_id", "coin", "r", "delta", "twin_mean", "exit_kind", "complete", "twin_pooled", "twin_n"]]
      .to_string())

# my month blocks
O = o.merge(F1[["fill_id", "t_F1", "rung", "episode", "month_block", "half", "L", "P0", "sigma30"]], on="fill_id")
O = O[np.isfinite(O.delta)].copy()
blk, ep = month_blocks_from_times(O.t_F1.to_numpy())
O["mb_me"], O["ep_me"] = blk, ep
# compare partitions
ct = pd.crosstab(O.mb_me, O.month_block)
print("month-block partitions identical:", (ct.gt(0).sum(1) == 1).all() and (ct.gt(0).sum(0) == 1).all(),
      "G me", O.mb_me.nunique(), "G engine", O.month_block.nunique())
ct2 = pd.crosstab(O.ep_me, O.episode)
print("episode partitions identical:", (ct2.gt(0).sum(1) == 1).all() and (ct2.gt(0).sum(0) == 1).all(),
      O.ep_me.nunique(), O.episode.nunique())
print("H1 headline (my CR1):", fmt(cr1(O.delta, O.mb_me)))
print("mean r_f:", O.r.mean(), " mean twin_mean:", O.twin_mean.mean())

# ---- pooled twins
print("\n== pooled twins ==")
print("twin_pooled counts:", O.twin_pooled.value_counts().to_dict())
pp = O[O.twin_pooled]
print(pp.groupby("coin").size().sort_values(ascending=False).to_string())
print("twin_n distribution (own):", O.loc[~O.twin_pooled, "twin_n"].describe().to_dict())
print("twin_n distribution (pooled):", O.loc[O.twin_pooled, "twin_n"].describe().to_dict())
print("without pooled-twin fills:", fmt(cr1(O.delta[~O.twin_pooled], O.mb_me[~O.twin_pooled])))
print("pooled-twin fills only:", fmt(cr1(O.delta[O.twin_pooled], O.mb_me[O.twin_pooled])))
print("pooled fills: mean r", O.r[O.twin_pooled].mean(), "mean twin", O.twin_mean[O.twin_pooled].mean())
print("own fills: mean r", O.r[~O.twin_pooled].mean(), "mean twin", O.twin_mean[~O.twin_pooled].mean())

# ---- sensitivity twins
print("\n== x30 / always-pooled / drift ==")
for c in ("delta_x30", "delta_pool", "delta_drift"):
    ok = np.isfinite(O[c])
    print(c, fmt(cr1(O[c][ok], O.mb_me[ok])))
print("twin_pooled_x30 counts:", O.twin_pooled_x30.value_counts(dropna=False).to_dict())
print("corr(twin_mean, twin_mean_pool):", np.corrcoef(O.twin_mean, O.twin_mean_pool)[0, 1])
print("mean twin_mean_pool:", O.twin_mean_pool.mean(), "mean twin_mean_x30:", O.twin_mean_x30.mean())

O.to_parquet(f"{OUT}/h1rows.parquet")
