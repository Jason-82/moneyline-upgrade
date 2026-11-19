"""(a, widened) Every P1 U-Q1 bid: P0 = close of d0, sigma30 = SD of the last <= 30 daily log returns ending d0 inside
d0's segment (>= 25), from the daily klines using only rows up to d0 (segment breaks are causal: a missing day or a
> 25% open jump), and L = floor(P0 exp(-k sigma)) on the bid's tick (the tick itself was checked from 1m data on 12
bids in a_bids.py). Counts mismatches."""
import math
import sys
from decimal import Decimal, ROUND_FLOOR, getcontext

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/moneyline-upgrade")
from analysis_2026 import stinkbid_data as sbd

getcontext().prec = 50


def main():
    b = pd.read_parquet("data/stinkbid/runs/outcomes/P1__U_Q1/bids.parquet",
                        columns=["bid_id", "coin", "rung", "t0", "d0", "P0", "sigma30", "tick_str", "L", "n_ticks"])
    res = []
    for coin, g in b.groupby("coin"):
        sym = sbd.coin_sym(coin)[0]
        d = pd.read_parquet("data/stinkbid/d1_full_all.parquet",
                            columns=["sym", "open_time", "open", "close", "trades"], filters=[("sym", "==", sym)])
        d = d[d.trades > 0].sort_values("open_time")
        day = (np.asarray((d.open_time.dt.tz_convert(None).dt.normalize() - pd.Timestamp("1970-01-01"))
                          // pd.Timedelta("1D"), dtype=np.int64))
        o, c = d.open.to_numpy(float), d.close.to_numpy(float)
        brk = np.r_[True, (np.diff(day) != 1) | (np.abs(o[1:] / c[:-1] - 1) > 0.25)]
        start = np.maximum.accumulate(np.where(brk, np.arange(len(day)), 0))
        for r in g.itertuples(index=False):
            i = int(np.searchsorted(day, int(r.d0)))
            if i >= len(day) or day[i] != int(r.d0):
                res.append(dict(bid_id=r.bid_id, coin=coin, ok=False, why="no bar on d0"))
                continue
            cc = c[:i + 1]                                        # truncated at d0
            lo = max(i - 29, int(start[i]) + 1)
            rr = np.log(cc[lo:i + 1] / cc[lo - 1:i])
            sig = float(np.std(rr, ddof=1)) if len(rr) >= 25 else float("nan")
            P0 = float(cc[i])
            tau = Decimal(r.tick_str)
            x = P0 * math.exp(-float(r.rung) * sig)
            n = int((Decimal(x) / tau * (1 + Decimal("1e-13"))).to_integral_value(rounding=ROUND_FLOOR))
            res.append(dict(bid_id=r.bid_id, coin=coin, ok=True, dP0=abs(P0 / r.P0 - 1),
                            dsig=abs(sig / r.sigma30 - 1), n_mine=n, n_eng=int(r.n_ticks),
                            L_eq=float(n * tau) == float(r.L)))
    R = pd.DataFrame(res)
    print("bids:", len(R), "| with a d0 bar:", int(R.ok.sum()), "| P0 equal:", int((R.dP0 == 0).sum()),
          "| max rel dP0:", R.dP0.max(), "| sigma within 1e-12:", int((R.dsig < 1e-12).sum()),
          "| max rel dsig:", R.dsig.max(), "| n_ticks equal:", int((R.n_mine == R.n_eng).sum()),
          "| L equal:", int(R.L_eq.sum()))
    bad = R[(R.dP0 > 0) | (R.dsig >= 1e-12) | (R.n_mine != R.n_eng) | ~R.L_eq.astype(bool)]
    print(bad.head(20).to_string())


if __name__ == "__main__":
    main()
