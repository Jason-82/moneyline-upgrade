import numpy as np, pandas as pd, pyarrow.parquet as pq
RUN = "/home/user/moneyline-upgrade/data/stinkbid/runs/outcomes/P1__U_Q1"
F = pd.read_parquet(RUN + "/fills.parquet", columns=["fill_id", "coin", "t_F1", "L", "seg", "lineage"])
B = pd.read_parquet(RUN + "/bench.parquet", columns=["fill_id", "rule", "knife"])
d = F[F.t_F1 >= 0].merge(B[B.rule == "F1"], on="fill_id")
d = d[np.isfinite(d.knife)]
print(pq.ParquetFile("/home/user/moneyline-upgrade/data/stinkbid/m1_spot/ETHUSDT.parquet").schema.names)
rng = np.random.default_rng(7)
# simple coins without renames (coin == lineage or lineage empty) to avoid chain logic
d = d[(d.lineage.isna()) | (d.lineage.astype(str) == d.coin.astype(str))]
pick = d.sample(12, random_state=3)
for r in pick.itertuples():
    f = f"/home/user/moneyline-upgrade/data/stinkbid/m1_spot/{r.coin}USDT.parquet"
    day0 = pd.Timestamp(int(r.t_F1) * 60, unit="s", tz="UTC").normalize()
    d365 = day0 + pd.Timedelta(days=365)
    try:
        k = pd.read_parquet(f, columns=["open_time", "volume", "quote_volume"],
                            filters=[("open_time", ">=", d365), ("open_time", "<", d365 + pd.Timedelta(days=1))])
    except Exception as e:
        print(r.coin, "read error", e); continue
    vw = k.quote_volume.sum() / k.volume.sum() if len(k) and k.volume.sum() > 0 else np.nan
    print(f"{r.coin:6s} fill {day0.date()} L {r.L:.6g}  day365 {d365.date()} vwap {vw:.6g} ratio {vw / r.L:.3f}  "
          f"mine {float(vw <= 0.5 * r.L) if np.isfinite(vw) else 'nan'} engine {r.knife}")
