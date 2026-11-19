import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/recompute-h4-topblock")
import numpy as np, pandas as pd
from h4_topblock import frames, month_blocks, month_of, mlabel, fe_b
out, _ = frames()
M = out["M7"]; tM = M["tmin"].to_numpy()
labA, moA = month_blocks(tM)
allt = np.concatenate([out[m]["tmin"].to_numpy() for m in ("M4", "M5b", "M6", "M7")])
labU_all, _ = month_blocks(allt); labU = labU_all[-len(M):]
sel = (moA >= 2025*12+6) & (moA <= 2025*12+9)
print("M7 rows by M7-own block within 2025-07..2025-10:")
print(pd.Series([mlabel(x) for x in labA[sel]]).value_counts().sort_index().to_string())
print("M7 rows by calendar month 2025-07..10:", pd.Series([mlabel(x) for x in moA[sel]]).value_counts().sort_index().to_dict())
uA = list(np.unique(labA)); uU = list(np.unique(labU_all))
print("index of 2023-05 block: own", uA.index(2023*12+4), "shared", uU.index(2023*12+4), "| index of 2025-07 block shared", uU.index(2025*12+6))
# b without each of the two candidate blocks on each partition, and b without the whole 2025-07..10 span
print("b without 2025-07..10 months (shared top block):", fe_b(M, ~sel)[0])
print("b without M7-own 2025-09+10:", fe_b(M, labA != 2025*12+8)[0])
