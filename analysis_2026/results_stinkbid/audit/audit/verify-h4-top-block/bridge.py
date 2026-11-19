"""Which methods' fill days link 2025-08 and 2025-09 (and 2025-07/08, 2025-09/10) in the union's episodes."""
import numpy as np, pandas as pd
RUN = "data/stinkbid/runs/outcomes/H4__U_Q1/"
METHODS = {"M4 N=90 buffer=0.5": "M4", "M5b": "M5b", "M6": "M6", "M7": "M7"}
F = pd.read_parquet(RUN + "fills.parquet", columns=["fill_id", "variant", "cw", "t_F1"])
O = pd.read_parquet(RUN + "outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "delta", "complete"])
Bd = pd.read_parquet(RUN + "bids.parquet", columns=["variant", "cw", "real", "delta"])
o = O[(O.rule == "F1") & (O.exit == "FLIP") & (O.cost == "C-RH") & O.complete.astype(bool)][["fill_id", "delta"]]
f = F[F.t_F1 >= 0].merge(o, on="fill_id")
rb = Bd[Bd.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "dr"})
f = f.merge(rb, on=["variant", "cw"], how="left")
f = f[np.isfinite(f.delta.astype(float)) & np.isfinite(f.dr.astype(float))]
f["m"] = f.variant.map(METHODS); f = f[f.m.notna()]
f["day"] = pd.to_datetime(f.t_F1.astype(np.int64) * 60, unit="s", utc=True).dt.strftime("%Y-%m-%d")
w = f[(f.day >= "2025-07-20") & (f.day <= "2025-10-12")]
t = w.groupby(["day", "m"]).size().unstack(fill_value=0)
print(t.to_string())
