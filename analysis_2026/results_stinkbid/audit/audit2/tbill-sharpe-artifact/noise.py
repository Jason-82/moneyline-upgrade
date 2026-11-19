"""What _summ's formula prints for B-TBILL once both mismatches are removed (compounded rf_m; month 1 from K):
the excess is floating-point noise, and mean/SD of noise is an arbitrary number."""
import math, runpy
g = runpy.run_path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit2/tbill-sharpe-artifact/repro.py")
import numpy as np
V, K, me_idx, rf_m_cmp, monthly = g["V"], g["K"], g["me_idx"], g["rf_m_cmp"], g["monthly"]
r = monthly(V); r[0] = V[me_idx[0]] / K - 1
ex = r - rf_m_cmp
sd = ex.std(ddof=1)
print("\n[noise] both fixes: mean", ex.mean(), "sd", sd, "-> _summ formula would print",
      ex.mean() / sd * math.sqrt(12) if sd and sd > 0 else float("nan"))
