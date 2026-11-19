"""Verifier for finding d7-no-single-event-rows (read-only).

1. Rebuild the D7 flip account (P1 on U-Q1, F3 s = 1%, r_res = 0) from the cached engine run with the engine's own
   accounts(), and check it against the desc first pass of record (commit 7949037, d7_summary.csv / d7_compare.csv).
2. Compute the prereg §10.4 single-event versions: the fills of 2025-10-10, of 2021-05-19, or of the top month-block
   treated as not having happened (t_F3_1 = -1, so the bid stays reserved until its life ends, as stinkbid_desc.d6
   does for W, F, theta, mu*), and report D7 - B-MIX (and D7 - B-TBILL) CAGR with 6- and 12-month stationary block
   bootstrap intervals (stinkbid_stats.stationary_bootstrap, B = 9,999, the record's seed).

Run from /home/user/moneyline-upgrade with python3. No network (sockets are blocked below), no writes to the repo.
"""
import socket
import sys
import time
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
from analysis_2026 import stinkbid_engine as sbe  # noqa: E402
from analysis_2026 import stinkbid_stats as sbs  # noqa: E402

OUTDIR = Path(__file__).resolve().parent
RUN = ROOT / "data/stinkbid/runs/outcomes/P1__U_Q1"
ROUTE, TCOL = "F3_1", "t_F3_1"
DAY_M = 1440


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def load():
    res = {}
    res["bids"] = pd.read_parquet(RUN / "bids.parquet")
    res["fills"] = pd.read_parquet(RUN / "fills.parquet")
    res["bench"] = pd.read_parquet(RUN / "bench.parquet",
                                   columns=["fill_id", "rule", "alert_M", "alert_t_M", "alert_px_M", "xml_t",
                                            "xml_px"])
    res["outcomes"] = pd.read_parquet(RUN / "outcomes.parquet",
                                      columns=["rule", "exit", "lat", "cost", "fill_id", "r", "exit_t", "exit_kind"])
    res["cap_curve"] = pd.DataFrame()       # not read on F3 (accounts sizes F3 positions at Q)
    meta = json.loads((RUN / "meta.json").read_text())
    res["program"], res["universe"] = meta["program"], meta["universe"]
    return res


def boot(M, a, b, blk):
    bt = sbs.stationary_bootstrap(M[a].to_numpy(float), M[b].to_numpy(float), stat="cagr", mean_block=blk,
                                  B=sbs.B_BOOT)
    return bt["estimate"], bt["ci"][0], bt["ci"][1], bt["T"]


def run_account(res):
    t = time.time()
    A = sbe.accounts(res, data=None, route=ROUTE, r_res=0.0)
    S, M = A["summary"], A["monthly"]
    out = dict(end_value=float(S.loc["D7", "end_value"]), cagr=float(S.loc["D7", "cagr"]),
               positions=int(S.loc["D7", "positions"]), invested_avg=float(S.loc["D7", "invested_avg"]),
               bmix_cagr=float(S.loc["B-MIX", "cagr"]), tbill_cagr=float(S.loc["B-TBILL", "cagr"]),
               secs=round(time.time() - t, 1))
    for ben in ("B-MIX", "B-TBILL"):
        for blk in (6.0, 12.0):
            est, lo, hi, T = boot(M, "D7", ben, blk)
            out[f"{ben}_diff"] = est
            out[f"{ben}_lo{int(blk)}"], out[f"{ben}_hi{int(blk)}"] = lo, hi
            out["months"] = T
    return out, A


def main():
    res = load()
    F = res["fills"]
    print(f"loaded: bids {len(res['bids'])}, fills {len(F)}, outcomes {len(res['outcomes'])}; max RSS {rss_mb():.0f} MB",
          flush=True)

    # ---- 1. the full account against the record (commit 7949037)
    full, A0 = run_account(res)
    print("FULL", json.dumps(full, default=float), flush=True)
    pos = A0["positions"]
    print(f"positions {len(pos)}; max RSS {rss_mb():.0f} MB", flush=True)

    # ---- the fills on the route the account can use (F3 fill with a finite FLIP RH return)
    O = res["outcomes"]
    o = O[(O.rule == ROUTE) & (O.exit == "FLIP") & (O.cost == "RH")][["fill_id", "r"]]
    f3 = F[F[TCOL].to_numpy() >= 0][["fill_id", "bid_id", "coin", "rung", TCOL]].merge(o, on="fill_id", how="left")
    f3_all_t = pd.to_datetime(f3[TCOL].to_numpy(np.int64) * 60, unit="s", utc=True)
    f3_use = f3[f3.r.notna()]
    use_t = pd.to_datetime(f3_use[TCOL].to_numpy(np.int64) * 60, unit="s", utc=True)
    pos_t = pd.to_datetime(pos.t_fill.to_numpy(np.int64) * 60, unit="s", utc=True)

    # month-blocks and their top block under three readings of "the estimate's own sample"
    def top_block(t):
        ids, tab = sbs.month_blocks(t)
        top = tab.sort_values(["n_fills", "block"], ascending=[False, True]).iloc[0]
        return top, tab.sort_values("n_fills", ascending=False).head(5)

    tops = {}
    for name, t in (("all F3 fills", f3_all_t), ("F3 fills with a FLIP return", use_t),
                    ("account positions", pos_t)):
        top, head = top_block(t)
        tops[name] = top
        print(f"top month-block ({name}, n = {len(t)}): {top['label']} periods {top['periods']} n_fills {top['n_fills']}")
        print(head.to_string(index=False))

    # ---- 2. single events: fills of the route treated as not having happened (t_F3_1 = -1)
    fday = sbs.fill_days(f3_all_t)
    f3_mon = np.asarray(f3_all_t.tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("datetime64[M]")
                        .astype(np.int64))
    pos_day = sbs.fill_days(pos_t)
    pos_mon = pos_t.tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("datetime64[M]").astype(np.int64)
    gain = pos["size"].to_numpy(float) * pos["r"].to_numpy(float)
    total_gain = gain.sum()

    events = {}
    for dd in ("2025-10-10", "2021-05-19"):
        events[f"without {dd}"] = (fday == np.datetime64(dd), pos_day == np.datetime64(dd))
    for name in ("account positions", "all F3 fills"):
        per = np.asarray(list(tops[name]["periods"]), np.int64)
        events[f"without the top month-block ({name}: {tops[name]['label']})"] = (np.isin(f3_mon, per),
                                                                                  np.isin(pos_mon, per))
    rows = [dict(row="full", dropped_fills=0, dropped_positions=0, share_of_gains=0.0, **full)]
    for label, (mask_f, mask_p) in events.items():
        drop_ids = set(f3.fill_id.to_numpy()[mask_f].tolist())
        F2 = F.copy()
        F2.loc[F2.fill_id.isin(drop_ids), TCOL] = -1
        res2 = dict(res, fills=F2)
        r2, _ = run_account(res2)
        pd_ = pos[mask_p]
        span = (f"{pd.to_datetime(pd_.t_fill.min() * 60, unit='s').date()}.."
                f"{pd.to_datetime(pd_.t_fill.max() * 60, unit='s').date()}") if len(pd_) else ""
        row = dict(row=label, dropped_fills=int(mask_f.sum()), dropped_positions=int(mask_p.sum()),
                   positions_span=span, share_of_gains=float(gain[mask_p].sum() / total_gain), **r2)
        rows.append(row)
        print(json.dumps(row, default=float), f"max RSS {rss_mb():.0f} MB", flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(OUTDIR / "d7_events.csv", index=False)
    cols = ["row", "dropped_fills", "dropped_positions", "share_of_gains", "positions", "end_value", "cagr",
            "bmix_cagr", "B-MIX_diff", "B-MIX_lo12", "B-MIX_hi12", "B-MIX_lo6", "B-MIX_hi6", "B-TBILL_diff",
            "B-TBILL_lo12", "B-TBILL_hi12"]
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        print(T[cols].to_string(index=False))
    print(f"max RSS {rss_mb():.0f} MB")


if __name__ == "__main__":
    main()
