"""F3 (s = 1%) alert buys behind H2R's F3 gate, from the cached 1m index months (read directly; never fetched):
first index minute at or after M(t_F3_1) with >= 30 updates, outside the Robinhood outage days (whole New York day
+-1 h, the engine's coding choice 9); paid = open x (1 + 0.0095); a_f = paid / L - 1. Auditor's own code."""
import os
import numpy as np
import pandas as pd

RUN = "data/stinkbid/runs/outcomes/P1__U_Q1"
NY = "America/New_York"
OUTAGE_DAYS = ["2021-04-15", "2021-05-04", "2022-02-25", "2025-10-06", "2025-10-20"]


def rule_m_min(tmin):
    ts = pd.to_datetime(np.asarray(tmin, np.int64) * 60_000_000_000, utc=True)
    loc = ts.tz_convert(NY)
    mins = np.asarray(loc.hour * 60 + loc.minute)
    day = loc.tz_localize(None).normalize()
    nxt_day = np.where(mins < 420, day, day + pd.Timedelta("1D"))
    nxt = (pd.DatetimeIndex(nxt_day) + pd.Timedelta("7h")).tz_localize(NY).tz_convert("UTC")
    plus = ts + pd.Timedelta("60min")
    out = np.where((mins >= 420) & (mins <= 1379), plus.as_unit("ns").asi8, nxt.as_unit("ns").asi8)
    return out // 60_000_000_000


blk = []
for d in OUTAGE_DAYS:
    a = pd.Timestamp(d).tz_localize(NY).tz_convert("UTC") - pd.Timedelta("1h")
    b = (pd.Timestamp(d) + pd.Timedelta("1D")).tz_localize(NY).tz_convert("UTC") + pd.Timedelta("1h")
    blk.append((a.value // 60_000_000_000, b.value // 60_000_000_000))

F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["fill_id", "coin", "L", "t_F3_1", "t_F1"])
F = F[F.t_F3_1 >= 0]
Bn = pd.read_parquet(f"{RUN}/bench.parquet", columns=["fill_id", "alert_M", "alert_t_M", "alert_px_M"], filters=[("rule", "==", "F3_1")])
F = F.merge(Bn, on="fill_id")
rows = []
for coin, g in F.groupby("coin"):
    A = rule_m_min(g.t_F3_1.to_numpy())
    months = sorted(set(pd.to_datetime(A * 60_000_000_000, utc=True).strftime("%Y-%m")))
    months = sorted(set(months) | {(pd.Period(m, "M") + 1).strftime("%Y-%m") for m in months})
    parts = []
    for m in months:
        p = f"data/stinkbid/fut1m/index/{coin}/{m}.parquet"
        if os.path.exists(p):
            parts.append(pd.read_parquet(p, columns=["open_time", "open", "updates"]))
    if not parts:
        for _, f in g.iterrows():
            rows.append(dict(fill_id=f.fill_id, coin=coin, note="no index file"))
        continue
    k = pd.concat(parts).sort_values("open_time")
    t = pd.to_datetime(k.open_time, utc=True).astype("int64").to_numpy() // 60_000_000_000
    ok = k.updates.to_numpy() >= 30
    for a, b in blk:
        ok &= ~((t >= a) & (t < b))
    t, o = t[ok], k.open.to_numpy()[ok]
    for (_, f), a_t in zip(g.iterrows(), A):
        i = np.searchsorted(t, a_t)
        if i >= len(t):
            rows.append(dict(fill_id=f.fill_id, coin=coin, note="no live index minute after M"))
            continue
        paid = o[i] * 1.0095
        rows.append(dict(fill_id=int(f.fill_id), coin=coin, t_mine=int(t[i]), t_file=int(f.alert_t_M), a_mine=paid / f.L - 1,
                         a_file=float(f.alert_M)))
R = pd.DataFrame(rows)
ok = (R.t_mine == R.t_file) & (np.abs(R.a_mine - R.a_file) < 1e-9)
print(f"F3_1 alert buys: {len(R)}; (time, a_f) matches: {int(ok.sum())}; notes: {R.note.value_counts().to_dict() if 'note' in R else {}}")
print(f"mean a_f mine {R.a_mine.mean():+.5f} file {R.a_file.mean():+.5f}")
bad = R[~ok]
print(bad.head(20).to_string())
