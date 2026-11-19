import pandas as pd, numpy as np
base = "data/stinkbid/runs/outcomes/P1__U_Q1/"
o = pd.read_parquet(base + "outcomes.parquet", columns=["rule", "exit", "lat", "cost", "complete"])
g = o.groupby(["rule", "exit", "lat", "cost"], dropna=False).agg(n=("complete", "size"), ncomp=("complete", "sum")).reset_index()
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 500)
print(g[~g["exit"].str.startswith("G_")].to_string())
b = pd.read_parquet(base + "bench.parquet", columns=["rule", "fill_id", "alert_M", "alert_72h", "knife", "twin_knife", "post_mean_C-RH", "post_mean_RH"])
print(b.groupby("rule").agg(n=("fill_id", "size"), aM=("alert_M", lambda s: np.isfinite(s.astype(float)).sum()),
      a72=("alert_72h", lambda s: np.isfinite(s.astype(float)).sum()),
      knife=("knife", lambda s: np.isfinite(pd.to_numeric(s, errors="coerce")).sum()),
      twin_knife=("twin_knife", lambda s: np.isfinite(pd.to_numeric(s, errors="coerce")).sum()),
      post_crh=("post_mean_C-RH", lambda s: np.isfinite(s.astype(float)).sum()),
      post_rh=("post_mean_RH", lambda s: np.isfinite(s.astype(float)).sum())).to_string())
