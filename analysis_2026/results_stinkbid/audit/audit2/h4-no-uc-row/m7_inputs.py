from pathlib import Path
import pandas as pd
root = Path("/home/user/moneyline-upgrade")
uc = set(pd.read_csv(root / "analysis_2026/stinkbid_ref/u_c_2026-11-18.csv")["coin"].astype(str))
met = {p.stem for p in (root / "data/stinkbid/metrics").glob("*.parquet")}
mk = {p.stem for p in (root / "data/stinkbid/mark1h").glob("*.parquet")}
print("U-C coins:", len(uc))
print("U-C coins with metrics parquet:", len(uc & met), " without:", len(uc - met))
print("U-C coins with mark1h parquet:", len(uc & mk), " without:", len(uc - mk))
print("without metrics:", sorted(uc - met))
