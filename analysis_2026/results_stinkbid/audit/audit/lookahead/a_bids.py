"""(a) 12 random P1 bids (seed 11): recompute P0, sigma30, tick and L from 1m spot data truncated at the end of d0
(Sunday's close), with independent code (prereg §6.1, §6.2; A1.3 tick rule). Also cross-check P0/sigma30 against
the daily klines truncated at d0."""
import math
from decimal import Decimal, ROUND_FLOOR, getcontext

import numpy as np
import pandas as pd

getcontext().prec = 50
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1"
DAYNS = 86_400 * 10**9


def sym_of(coin):
    # data loader helper (allowed): the Binance symbol of a coin (LUNA/LUNA2 split)
    from analysis_2026 import stinkbid_data as sbd
    return sbd.coin_sym(coin)[0]


def decimals(x: float) -> int:
    s = np.format_float_positional(float(x), unique=True, trim="-")
    return len(s.split(".")[1]) if "." in s else 0


def tick_from(prices):
    dec = np.array([decimals(p) for p in prices])
    n = len(dec)
    for d in range(0, 13):
        finer = int((dec > d).sum())
        if finer <= 0.001 * n:
            return d, int(dec.max()), finer, n
    return None


def floor_tick(x: float, d: int):
    tau = Decimal(1).scaleb(-d)
    q = (Decimal(x) / tau)
    n = int(q.to_integral_value(rounding=ROUND_FLOOR))
    # a float within 1e-13 relative below a grid point counts as on it (float rounding); report if it matters
    n_tol = int((q * (1 + Decimal("1e-13"))).to_integral_value(rounding=ROUND_FLOOR))
    return n, n_tol, float(n * tau)


def daily_from_m1(k):
    k = k[k.trades > 0].copy()
    k["day"] = k.open_time.dt.tz_convert(None).dt.normalize()
    g = k.groupby("day")
    return pd.DataFrame({"open": g.open.first(), "close": g.close.last()})


def sigma_from_daily(d, d0):
    """SD (ddof 1) of the last 30 daily log returns ending d0 inside d0's segment (segment: no missing day, no >25%
    open jump), >= 25 needed."""
    d = d[d.index <= d0].sort_index()
    days = d.index.to_numpy()
    # walk back from d0 to the segment start
    i = len(d) - 1
    assert days[i] == np.datetime64(d0), "no bar on d0"
    start = i
    while start > 0:
        gap = (days[start] - days[start - 1]) / np.timedelta64(1, "D")
        jump = abs(d.open.iloc[start] / d.close.iloc[start - 1] - 1) > 0.25
        if gap != 1 or jump:
            break
        start -= 1
    lo = max(i - 30 + 1, start + 1)
    c = d.close.to_numpy()
    r = np.log(c[lo:i + 1] / c[lo - 1:i])
    return (float(np.std(r, ddof=1)) if len(r) >= 25 else float("nan")), len(r), float(c[i])


def main():
    b = pd.read_parquet(f"{RUN}/bids.parquet", columns=["bid_id", "coin", "rung", "t0", "d0", "P0", "sigma30", "tick",
                                                         "tick_str", "L", "n_ticks", "delta", "month", "seg"])
    rng = np.random.default_rng(11)
    pick = np.sort(rng.choice(len(b), size=12, replace=False))
    u = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
    d1 = None
    rows = []
    for j in pick:
        r = b.iloc[j]
        t0 = pd.Timestamp(int(r.t0) * 60 * 10**9, tz="UTC")
        d0 = (t0.tz_convert(None).normalize() - pd.Timedelta("1D"))
        assert int(r.d0) == int(d0.value // DAYNS), "d0 mismatch"
        cut = pd.Timestamp(d0 + pd.Timedelta("1D"), tz="UTC")           # Sunday's close = the input cut-off
        sym = sym_of(r.coin)
        k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet",
                            columns=["open_time", "open", "high", "low", "close", "trades"],
                            filters=[("open_time", ">=", cut - pd.Timedelta("60D")), ("open_time", "<", cut)])
        assert k.open_time.max() < cut
        dd = daily_from_m1(k)
        sig, nret, P0 = sigma_from_daily(dd, d0)
        w = k[(k.trades > 0) & (k.open_time >= cut - pd.Timedelta("7D"))]
        tk = tick_from(np.concatenate([w.open, w.high, w.low, w.close]))
        dtick, draw, nfiner, npx = tk
        x = P0 * math.exp(-float(r.rung) * sig)
        n, n_tol, L = floor_tick(x, dtick)
        # daily klines (independent source) truncated at d0
        if d1 is None:
            d1 = pd.read_parquet("data/stinkbid/d1_full_all.parquet", columns=["sym", "open_time", "open", "close",
                                                                               "trades"])
        dk = d1[(d1.sym == sym) & (d1.trades > 0)].copy()
        dk["day"] = dk.open_time.dt.tz_convert(None).dt.normalize()
        dk = dk[(dk.day <= d0) & (dk.day > d0 - pd.Timedelta("60D"))].set_index("day")[["open", "close"]]
        sig_k, nret_k, P0_k = sigma_from_daily(dk, d0)
        mon = t0.strftime("%Y-%m")
        inq1 = bool(u[(u.month == mon) & (u.coin == r.coin)].U_Q1.any())
        rows.append(dict(row=int(j), bid_id=int(r.bid_id), coin=r.coin, k=r.rung, t0=str(t0), d0=str(d0.date()),
                         month=mon, inQ1=inq1,
                         P0_eng=r.P0, P0_m1=P0, P0_d1=P0_k, sig_eng=r.sigma30, sig_m1=sig, sig_d1=sig_k, nret=nret,
                         tick_eng=r.tick_str, tick_mine=("1" if dtick == 0 else "0." + "0" * (dtick - 1) + "1"),
                         tick_raw=draw, n_finer=nfiner, n_px=npx, L_eng=r.L, L_mine=L, n_eng=int(r.n_ticks),
                         n_mine=n, n_tol=n_tol,
                         dP0=abs(P0 / r.P0 - 1), dsig=abs(sig / r.sigma30 - 1), dsig_d1=abs(sig_k / r.sigma30 - 1),
                         L_match=(n == int(r.n_ticks)) and (L == r.L)))
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(out[["row", "bid_id", "coin", "k", "t0", "d0", "month", "inQ1", "P0_eng", "P0_m1", "P0_d1", "dP0",
               "sig_eng", "sig_m1", "dsig", "dsig_d1", "nret"]].to_string())
    print(out[["bid_id", "coin", "tick_eng", "tick_mine", "tick_raw", "n_finer", "n_px", "L_eng", "L_mine", "n_eng",
               "n_mine", "n_tol", "L_match"]].to_string())
    print("all L match:", out.L_match.all(), "| max rel dP0", out.dP0.max(), "| max rel dsig (m1)", out.dsig.max(),
          "| max rel dsig (d1)", out.dsig_d1.max(), "| ticks equal:", (out.tick_eng == out.tick_mine).all(),
          "| all in U_Q1:", out.inQ1.all())
    out.to_csv("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
               "lookahead/a_bids.csv", index=False)


if __name__ == "__main__":
    main()
