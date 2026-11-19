"""Refute check for finding d7-no-single-event-rows.

Question: is the desc module's reason for omitting D7's single-event rows ("an account's path cannot drop one day")
true? Test: call the engine's OWN stinkbid_engine.accounts (code identical to the record's, eee2ddf) on the cached
P1/U_Q1 run, once unchanged (control: must reproduce the record's F3 r_res=0 row of desc/d7_compare.csv at 7949037)
and once per single event with that event's F3 (s = 1%) fills treated as not having happened (t_F3_1 = -1, so the bid
stays reserved until its life ends, as stinkbid_desc.d6 treats its single events). B-MIX is recomputed by the engine at
each account's own invested fraction. CAGR differences use stinkbid_stats.stationary_bootstrap exactly as
stinkbid_desc.d7 does (seeded, B = 9,999, 6- and 12-month mean blocks).

Read-only: every writer of stinkbid_data is blocked, the archive fetcher raises (no network), DataFrame.to_parquet
raises, bytecode is not written and numba's cache goes to the scratch directory. Data-file mtimes are compared before
and after.
"""
import os
import sys

SCR = os.path.dirname(os.path.abspath(__file__))
os.environ["NUMBA_CACHE_DIR"] = os.path.join(SCR, "numba_cache")
sys.dont_write_bytecode = True
REPO = "/home/user/moneyline-upgrade"
sys.path.insert(0, REPO)

import io  # noqa: E402
import json  # noqa: E402
import resource  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DATA = Path(REPO) / "data" / "stinkbid"


def snapshot():
    out = {}
    for p in [DATA / "ref", DATA / "macro", DATA / "stats", DATA / "runs" / "outcomes" / "P1__U_Q1"]:
        if p.exists():
            for f in p.iterdir():
                if f.is_file():
                    st = f.stat()
                    out[str(f)] = (st.st_size, st.st_mtime_ns)
    f = DATA / "d1_full_all.parquet"
    if f.exists():
        out[str(f)] = (f.stat().st_size, f.stat().st_mtime_ns)
    return out


before = snapshot()

from analysis_2026 import stinkbid_data as sbd  # noqa: E402
from analysis_2026 import stinkbid_engine as sbe  # noqa: E402
from analysis_2026 import stinkbid_stats as sbs  # noqa: E402


def _blocked(*a, **k):
    raise RuntimeError("write blocked by the audit script")


def _no_net(*a, **k):
    raise IOError("network blocked by the audit script")


sbd._save_json = _blocked
sbd._write_parquet = _blocked
sbd._get_zip = _no_net
pd.DataFrame.to_parquet = _blocked

RUN = DATA / "runs" / "outcomes" / "P1__U_Q1"
DAY = 1440


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def git_csv(path, commit="7949037", **kw):
    s = subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], capture_output=True, text=True,
                       check=True).stdout
    return pd.read_csv(io.StringIO(s), **kw)


def main():
    t0 = time.time()
    res = {t: pd.read_parquet(RUN / f"{t}.parquet") for t in ("bids", "fills", "bench", "outcomes")}
    meta = json.loads((RUN / "meta.json").read_text())
    res.update(program=meta["program"], universe=meta["universe"], meta=meta.get("meta", {}),
               cap_curve=pd.DataFrame(), audit=pd.DataFrame(), bid_status=pd.DataFrame())
    print(f"loaded run: {len(res['bids'])} bids, {len(res['fills'])} fills; rss {rss_mb():.0f} MB", flush=True)
    world = sbe.World(None)
    fills = res["fills"]
    tF3 = fills["t_F3_1"].to_numpy(np.int64)
    f3 = tF3 >= 0
    fday = np.where(f3, tF3 // DAY, -1)

    def account(tf3_mod, label):
        r = dict(res)
        r["fills"] = fills.assign(t_F3_1=tf3_mod)
        t = time.time()
        A = sbe.accounts(r, data=world, route="F3_1", r_res=0.0)
        S, M = A["summary"], A["monthly"]
        row = dict(label=label, n_F3_fills=int((tf3_mod >= 0).sum()), positions=int(S.loc["D7", "positions"]),
                   end_value=float(S.loc["D7", "end_value"]), cagr=float(S.loc["D7", "cagr"]),
                   x_invested=float(A["x_flip"]), bmix_cagr=float(S.loc["B-MIX", "cagr"]))
        for ben in ("B-MIX", "B-TBILL"):
            for blk in (6.0, 12.0):
                bt = sbs.stationary_bootstrap(M["D7"].to_numpy(float), M[ben].to_numpy(float), stat="cagr",
                                              mean_block=blk, B=sbs.B_BOOT)
                row[f"{ben}_diff"] = bt["estimate"]
                row[f"{ben}_lo_{int(blk)}m"] = bt["ci"][0]
                row[f"{ben}_hi_{int(blk)}m"] = bt["ci"][1]
        print(f"  {label}: {time.time() - t:.0f}s, rss {rss_mb():.0f} MB -> "
              f"D7 end ${row['end_value']:,.2f}, CAGR {row['cagr']:.5f}, {row['positions']} positions; "
              f"D7 - B-MIX {row['B-MIX_diff']:+.4f} (12m {row['B-MIX_lo_12m']:+.4f} .. {row['B-MIX_hi_12m']:+.4f}; "
              f"6m {row['B-MIX_lo_6m']:+.4f} .. {row['B-MIX_hi_6m']:+.4f}); "
              f"D7 - B-TBILL {row['B-TBILL_diff']:+.4f} (12m {row['B-TBILL_lo_12m']:+.4f} .. "
              f"{row['B-TBILL_hi_12m']:+.4f})", flush=True)
        return row, A

    rows = []
    base, A0 = account(tF3.copy(), "full (control)")
    rows.append(base)
    # the record's row (desc first pass) for the control
    rec = git_csv("analysis_2026/results_stinkbid/desc/d7_compare.csv")
    rr = rec[(rec.route == "F3_1") & (rec.r_res == 0.0) & (rec.account == "D7") & (rec.benchmark == "B-MIX")].iloc[0]
    ctl = dict(record_cagr_diff=float(rr.cagr_diff), record_lo_12m=float(rr.lo_12m), record_hi_12m=float(rr.hi_12m),
               record_lo_6m=float(rr.lo_6m), record_hi_6m=float(rr.hi_6m),
               match=bool(abs(rr.cagr_diff - base["B-MIX_diff"]) < 1e-9 and abs(rr.lo_12m - base["B-MIX_lo_12m"]) < 1e-9
                          and abs(rr.hi_12m - base["B-MIX_hi_12m"]) < 1e-9))
    print(f"  control vs record (7949037 d7_compare F3_1 r_res 0 D7 vs B-MIX): {ctl}", flush=True)

    # the module's convention for "its top month-block": the month-block (stinkbid_stats.month_blocks) with the most
    # fills of the estimate's own sample (ties: the earliest); here the account's positions' fill times
    pos = A0["positions"]
    tref = pd.to_datetime(pos["t_fill"].to_numpy(np.int64) * 60_000_000_000, utc=True)
    _, tab = sbs.month_blocks(pd.DatetimeIndex(tref))
    tab = tab.sort_values(["n_fills", "block"], ascending=[False, True])
    top = tab.iloc[0]
    periods = np.asarray(list(top["periods"]), np.int64)
    gains = pos.assign(g=pos["size"] * pos["r"], mm=pd.DatetimeIndex(tref).tz_localize(None).to_numpy(
        dtype="datetime64[ns]").astype("datetime64[M]").astype(np.int64))
    top_gain_share = float(gains.loc[np.isin(gains.mm, periods), "g"].sum() / gains["g"].sum())
    print(f"  top month-block by fills (module convention): periods {[str(np.datetime64(int(p), 'M')) for p in periods]}"
          f", {int(top['n_fills'])} account fills, {top_gain_share:.1%} of the account's flip gains; next: "
          + "; ".join(f"{[str(np.datetime64(int(p), 'M')) for p in rw['periods']]} {int(rw['n_fills'])}"
                      for _, rw in tab.iloc[1:4].iterrows()), flush=True)
    fmonth = np.where(f3, pd.to_datetime(np.where(f3, tF3, 0) * 60_000_000_000).to_numpy(dtype="datetime64[ns]")
                      .astype("datetime64[M]").astype(np.int64), -10**9)

    events = {
        "without 2021-05-19": f3 & (fday == (np.datetime64("2021-05-19") - np.datetime64("1970-01-01")).astype(int)),
        "without 2025-10-10": f3 & (fday == (np.datetime64("2025-10-10") - np.datetime64("1970-01-01")).astype(int)),
        "without the top month-block (most fills)": f3 & np.isin(fmonth, periods),
    }
    # the critic's choice of block (most gains), when it differs
    may21 = (np.datetime64("2021-05") - np.datetime64("1970-01")).astype(int)
    if not np.array_equal(np.sort(periods), np.array([may21])):
        events["without 2021-05 (the critic's block, by gains)"] = f3 & (fmonth == may21)
    for name, drop in events.items():
        tm = tF3.copy()
        tm[drop] = -1
        row, _ = account(tm, f"{name} ({int(drop.sum())} F3 fills dropped)")
        rows.append(row)

    after = snapshot()
    changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
    out = dict(control_vs_record=ctl, rows=rows, top_block=dict(
        periods=[str(np.datetime64(int(p), 'M')) for p in periods], n_fills=int(top["n_fills"]),
        gain_share=top_gain_share), data_files_changed=changed, max_rss_mb=rss_mb(), seconds=time.time() - t0)
    with open(os.path.join(SCR, "d7_events_engine.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"data files changed: {changed}; max rss {rss_mb():.0f} MB; {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
