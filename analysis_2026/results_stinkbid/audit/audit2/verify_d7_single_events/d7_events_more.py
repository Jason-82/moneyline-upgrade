"""Supplement to d7_events.py (read-only): (a) per month-block shares of the F3 flip account's gains, to locate the
critic's "top month-block (2021-05-16..23, 71 fills, 35% of the account's gains)"; (b) the account without the
2021-05 month-block; (c) the r_res = 3.35% account (whose record interval against B-MIX is above zero) with its
single events. Same method as d7_events.py: the dropped fills get t_F3_1 = -1 (bid reserved until its life ends)."""
import socket
import sys
import json
import resource
from pathlib import Path


def _blocked(*a, **k):
    raise RuntimeError("network blocked in this verifier")


socket.socket.connect = _blocked
socket.create_connection = _blocked

import numpy as np
import pandas as pd

ROOT = Path("/home/user/moneyline-upgrade")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_2026 import stinkbid_engine as sbe  # noqa: E402
from analysis_2026 import stinkbid_stats as sbs  # noqa: E402
import d7_events as base  # noqa: E402

OUTDIR = Path(__file__).resolve().parent
ROUTE, TCOL = "F3_1", "t_F3_1"


def run(res, r_res):
    A = sbe.accounts(res, data=None, route=ROUTE, r_res=r_res)
    S, M = A["summary"], A["monthly"]
    out = dict(r_res=r_res, end_value=float(S.loc["D7", "end_value"]), cagr=float(S.loc["D7", "cagr"]),
               positions=int(S.loc["D7", "positions"]), bmix_cagr=float(S.loc["B-MIX", "cagr"]))
    for ben in ("B-MIX", "B-TBILL"):
        for blk in (6.0, 12.0):
            est, lo, hi, T = base.boot(M, "D7", ben, blk)
            out[f"{ben}_diff"], out[f"{ben}_lo{int(blk)}"], out[f"{ben}_hi{int(blk)}"] = est, lo, hi
    return out, A


def main():
    res = base.load()
    F = res["fills"]
    f3 = F[F[TCOL].to_numpy() >= 0][["fill_id", TCOL]]
    t_all = pd.to_datetime(f3[TCOL].to_numpy(np.int64) * 60, unit="s", utc=True)
    mon_all = t_all.tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("datetime64[M]").astype(np.int64)
    day_all = sbs.fill_days(t_all)

    rows = []
    # (a) full account at r_res 0 again, for the positions and gains by month-block
    full0, A0 = run(res, 0.0)
    pos = A0["positions"]
    pt = pd.to_datetime(pos.t_fill.to_numpy(np.int64) * 60, unit="s", utc=True)
    ids, tab = sbs.month_blocks(pt)
    gain = pos["size"].to_numpy(float) * pos["r"].to_numpy(float)
    tab["gain_share"] = [gain[ids == b].sum() / gain.sum() for b in tab.block]
    tab["first_day"] = [str(pt[ids == b].min().date()) for b in tab.block]
    tab["last_day"] = [str(pt[ids == b].max().date()) for b in tab.block]
    print("month-blocks of the account's positions, top by fills and by gain share:")
    print(tab.sort_values("n_fills", ascending=False).head(6).to_string(index=False))
    print(tab.sort_values("gain_share", ascending=False).head(6).to_string(index=False))
    ep, etab = sbs.episodes(pt)
    etab["gain_share"] = [gain[ep == e].sum() / gain.sum() for e in etab.episode]
    print("episodes of the account's positions, top by gain share:")
    print(etab.sort_values("gain_share", ascending=False).head(5).to_string(index=False))
    tab.to_csv(OUTDIR / "d7_blocks_r0.csv", index=False)

    may21 = (2021 - 1970) * 12 + 4
    events = {"without the 2021-05 month-block": np.isin(mon_all, [may21])}
    # (b) without the 2021-05 block at r_res 0
    for label, m in events.items():
        F2 = F.copy()
        F2.loc[F2.fill_id.isin(set(f3.fill_id.to_numpy()[m].tolist())), TCOL] = -1
        r, _ = run(dict(res, fills=F2), 0.0)
        rows.append(dict(row=label, dropped_fills=int(m.sum()), **r))
        print(json.dumps(rows[-1], default=float), flush=True)

    # (c) r_res 3.35%: full and the three single events of the module's convention (top block by fills)
    top_per = tab.sort_values(["n_fills", "block"], ascending=[False, True]).iloc[0]["periods"]
    ev3 = {"full": np.zeros(len(f3), bool),
           "without 2025-10-10": day_all == np.datetime64("2025-10-10"),
           "without 2021-05-19": day_all == np.datetime64("2021-05-19"),
           f"without the top month-block ({top_per})": np.isin(mon_all, np.asarray(list(top_per), np.int64))}
    for label, m in ev3.items():
        F2 = F.copy()
        F2.loc[F2.fill_id.isin(set(f3.fill_id.to_numpy()[m].tolist())), TCOL] = -1
        r, _ = run(dict(res, fills=F2), 0.0335)
        rows.append(dict(row=label, dropped_fills=int(m.sum()), **r))
        print(json.dumps(rows[-1], default=float), flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(OUTDIR / "d7_events_more.csv", index=False)
    cols = ["row", "r_res", "dropped_fills", "positions", "cagr", "bmix_cagr", "B-MIX_diff", "B-MIX_lo12", "B-MIX_hi12",
            "B-MIX_lo6", "B-MIX_hi6", "B-TBILL_diff", "B-TBILL_lo12", "B-TBILL_hi12"]
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(T[cols].to_string(index=False))
    print(f"max RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")


if __name__ == "__main__":
    main()
