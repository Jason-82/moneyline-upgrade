"""(e) Rule M (§8) on the real outputs: for every P1 U-Q1 F1 fill, my own America/New_York clock (zoneinfo, written
here) gives M(fill) and M(fill + 72 h / 7 d / 30 d / 90 d / 365 d); the stored alert minute (bench alert_t_M) must be
the first live spot minute at or after M(fill), and every stop exit (FLIP / HOLDh, exit_kind 'stop') the first live
minute at or after M(fill + h); marketable FLIP exits the first live minute at or after M(fill). Mismatches are
checked against the 1m bars (no live minute in between). Lists fills around the 14 DST changes 2020-2026."""
import datetime as dt
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/moneyline-upgrade")
from analysis_2026 import stinkbid_data as sbd

NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
R = "data/stinkbid/runs/outcomes/P1__U_Q1"


def rule_m(tmin: int) -> int:
    t = EPOCH + dt.timedelta(minutes=int(tmin))
    loc = t.astimezone(NY)
    hm = loc.hour * 60 + loc.minute
    if 7 * 60 <= hm <= 22 * 60 + 59:
        return int(tmin) + 60
    day = loc.date() if hm < 7 * 60 else loc.date() + dt.timedelta(days=1)
    nxt = dt.datetime(day.year, day.month, day.day, 7, 0, tzinfo=NY).astimezone(UTC)
    return int((nxt - EPOCH).total_seconds() // 60)


def naive_m(tmin: int, off_h: int) -> int:
    """rule M with a FIXED offset (what a clock without DST would give): for contrast only."""
    lt = tmin - off_h * 60
    hm = lt % 1440
    if 420 <= hm <= 1379:
        return tmin + 60
    day = lt // 1440 + (0 if hm < 420 else 1)
    return day * 1440 + 420 + off_h * 60


def ts(m):
    return pd.Timestamp(int(m) * 60, unit="s", tz="UTC")


def main():
    F = pd.read_parquet(f"{R}/fills.parquet", columns=["fill_id", "coin", "t_F1"])
    F = F[F.t_F1 >= 0]
    B = pd.read_parquet(f"{R}/bench.parquet", columns=["fill_id", "rule", "alert_t_M", "alert_M"])
    B = B[B.rule == "F1"]
    O = pd.read_parquet(f"{R}/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "exit_kind", "exit_t"])
    O = O[(O.rule == "F1") & (O.cost == "C-RH") & O.exit.isin(["FLIP", "HOLD7", "HOLD30", "HOLD90", "HOLD365"])]
    d = F.merge(B, on="fill_id")
    d["M"] = [rule_m(t) for t in d.t_F1]
    rows = []
    for _, r in d.iterrows():
        rows.append(dict(fill_id=r.fill_id, coin=r.coin, kind="alert", want=r.M, got=int(r.alert_t_M)))
    span = {"FLIP": 72 * 60, "HOLD7": 7 * 1440, "HOLD30": 30 * 1440, "HOLD90": 90 * 1440, "HOLD365": 365 * 1440}
    o = O.merge(F, on="fill_id")
    for _, r in o.iterrows():
        if r.exit_kind == "stop":
            rows.append(dict(fill_id=r.fill_id, coin=r.coin, kind=f"{r.exit}:stop",
                             want=rule_m(int(r.t_F1) + span[r.exit]), got=int(r.exit_t)))
        elif r.exit_kind == "marketable":
            rows.append(dict(fill_id=r.fill_id, coin=r.coin, kind=f"{r.exit}:marketable", want=rule_m(int(r.t_F1)),
                             got=int(r.exit_t)))
    X = pd.DataFrame(rows)
    X["same"] = X.want == X.got
    print("checks:", len(X), "equal:", int(X.same.sum()), "| got < want (an action before M):", int((X.got < X.want).sum()))
    print(X.groupby("kind").same.agg(["size", "sum"]).to_string())
    bad = X[~X.same]
    # mismatches: verify no live 1m bar in [want, got)
    ok_gap = []
    for coin, g in bad.groupby("coin"):
        sym = sbd.coin_sym(coin)[0]
        lo, hi = ts(g.want.min()), ts(g.got.max()) + pd.Timedelta("1min")
        k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet", columns=["open_time", "trades"],
                            filters=[("open_time", ">=", lo), ("open_time", "<", hi)])
        kt = (k.open_time.astype("int64") // 60_000_000_000).to_numpy()
        live = set(kt[k.trades.to_numpy() > 0].tolist())
        for _, r in g.iterrows():
            between = [m for m in range(int(r.want), int(r.got)) if m in live]
            ok_gap.append(dict(fill_id=r.fill_id, coin=coin, kind=r.kind, want=str(ts(r.want)), got=str(ts(r.got)),
                               gap_min=int(r.got - r.want), live_between=len(between), got_is_live=int(r.got) in live))
    G = pd.DataFrame(ok_gap)
    if len(G):
        print("mismatches explained by non-live minutes (no live bar between M and the stored minute):",
              int((G.live_between == 0).sum()), "of", len(G), "| stored minute live:", int(G.got_is_live.sum()))
        print(G.sort_values("gap_min", ascending=False).head(15).to_string())
    # DST: fills whose M(fill) or M(fill + 72 h) differs from a fixed-offset clock (EST or EDT of the fill time)
    dst = []
    for _, r in d.iterrows():
        t = int(r.t_F1)
        off = int(-(EPOCH + dt.timedelta(minutes=t)).astimezone(NY).utcoffset().total_seconds() // 3600)
        m_fill, m_stop = rule_m(t), rule_m(t + 72 * 60)
        if naive_m(t, off) != m_fill or naive_m(t + 72 * 60, off) != m_stop:
            dst.append(dict(fill_id=r.fill_id, coin=r.coin, fill=str(ts(t)),
                            fill_ny=str((EPOCH + dt.timedelta(minutes=t)).astimezone(NY)),
                            M_fill=str(ts(m_fill)), M_fill_ny=str((EPOCH + dt.timedelta(minutes=m_fill)).astimezone(NY)),
                            alert_t_M=str(ts(r.alert_t_M)),
                            M_stop72=str(ts(m_stop)),
                            M_stop72_ny=str((EPOCH + dt.timedelta(minutes=m_stop)).astimezone(NY)),
                            naive_fill=str(ts(naive_m(t, off))), naive_stop=str(ts(naive_m(t + 72 * 60, off)))))
    D = pd.DataFrame(dst)
    pd.set_option("display.width", 250)
    print(f"\nfills whose rule-M times cross a DST change (a fixed-offset clock would differ): {len(D)}")
    if len(D):
        fx = O[O.exit == "FLIP"][["fill_id", "exit_kind", "exit_t"]]
        D = D.merge(fx, on="fill_id", how="left")
        D["flip_exit"] = [str(ts(x)) if x >= 0 else "" for x in D.exit_t]
        print(D.drop(columns=["exit_t"]).to_string())
    X.to_csv("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
             "lookahead/e_rulem_checks.csv", index=False)


if __name__ == "__main__":
    main()
