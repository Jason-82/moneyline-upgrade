"""Step 2 (independent): re-derive every F3 (s = 1%) X-FLIP and X-FLIP-bot exit of P1/U-Q1 from the raw 1m index bars
(data/stinkbid/fut1m/index/<COIN>/<YYYY-MM>.parquet), with my own code from the prereg's text:

- §8 X-FLIP: target R1/2 = ceil(L + (P0 - L)/2) on the tick, live from M(fill). If the price is at or above R1/2 when
  the sell goes live, it executes at that minute's open (marketable). Otherwise it fills in the first later minute that
  reaches the target. Else sold at the first live minute at or after M(fill + 72 h).
  X-FLIP-bot: the same with the sell live 1 minute after the fill (time stop unchanged).
- §8 F3 rows: the target fills when index high >= R1/2 / (1 - 0.0095); market sells get index x (1 - 0.0095)
  (the marketable check likewise: open x (1 - 0.0095) >= R1/2). Bid pays L on F3, so r = exit / L - 1.
- §7: index minutes missing or with < 30 updates are outages; Robinhood outage windows (+-1 h; the whole New York day of
  each listed date, padded an hour each side) block F3 exits.
- §8 rule M: t + 60 if t is 07:00-22:59 New York, else the next 07:00 New York. Applied at the fill minute m.

No stinkbid_* import. Reads only the index months each fill needs, one coin at a time.
"""
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

OUT = Path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/f3-beside-flip/")
IDX = Path("data/stinkbid/fut1m/index")
NY = ZoneInfo("America/New_York")
SPR = 0.0095
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def to_dt(m):
    return EPOCH + timedelta(minutes=int(m))


def to_min(dt):
    return int((dt - EPOCH).total_seconds() // 60)


def rule_m(t):
    loc = to_dt(t).astimezone(NY)
    mins = loc.hour * 60 + loc.minute
    if 7 * 60 <= mins <= 22 * 60 + 59:
        return t + 60
    day = loc.date() if mins < 7 * 60 else loc.date() + timedelta(days=1)
    nxt = datetime(day.year, day.month, day.day, 7, 0, tzinfo=NY)
    return to_min(nxt.astimezone(timezone.utc))


def outage_windows():
    out = []
    for d in ("2021-04-15", "2021-05-04", "2022-02-25", "2025-10-06", "2025-10-20"):
        y, mo, dd = map(int, d.split("-"))
        a = datetime(y, mo, dd, 0, 0, tzinfo=NY)
        b = a.replace(tzinfo=None) + timedelta(days=1)
        b = datetime(b.year, b.month, b.day, 0, 0, tzinfo=NY)
        out.append((to_min(a.astimezone(timezone.utc)) - 60, to_min(b.astimezone(timezone.utc)) + 60))
    return out


OUTW = outage_windows()


def months_between(m0, m1):
    a, b = to_dt(m0), to_dt(m1)
    y, mo = a.year, a.month
    out = []
    while (y, mo) <= (b.year, b.month):
        out.append(f"{y:04d}-{mo:02d}")
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    return out


_cache = {}


def bars(coin, months):
    parts = []
    for mo in months:
        key = (coin, mo)
        if key not in _cache:
            f = IDX / coin / f"{mo}.parquet"
            if f.exists():
                k = pd.read_parquet(f, columns=["open_time", "open", "high", "updates"])
                t = (k.open_time.astype("int64") // 60_000_000_000).to_numpy(np.int64)
                _cache[key] = (t, k.open.to_numpy(float), k.high.to_numpy(float), k.updates.to_numpy(np.int64))
            else:
                _cache[key] = None
        if _cache[key] is not None:
            parts.append(_cache[key])
    if not parts:
        return None
    t = np.concatenate([p[0] for p in parts]); o = np.concatenate([p[1] for p in parts])
    h = np.concatenate([p[2] for p in parts]); u = np.concatenate([p[3] for p in parts])
    srt = np.argsort(t, kind="stable")
    t, o, h, u = t[srt], o[srt], h[srt], u[srt]
    live = u >= 30
    for a, b in OUTW:
        live &= ~((t >= a) & (t < b))
    return t[live], o[live], h[live]


def target_of(L, P0, tick):
    x = L + 0.5 * (P0 - L)
    n = math.ceil(x / tick - 1e-9)
    return n * tick


def sim(t, o, h, m, R, bot):
    go = m + 1 if bot else rule_m(m)
    ts = rule_m(m + 72 * 60)
    gi = np.searchsorted(t, go)            # first live minute >= go
    si = np.searchsorted(t, ts)            # first live minute >= time stop
    if gi >= len(t):
        return None
    if o[gi] * (1 - SPR) >= R:
        return "marketable", int(t[gi]), o[gi] * (1 - SPR)
    hit = np.nonzero(h[gi:si] >= R / (1 - SPR))[0]
    if len(hit):
        j = gi + hit[0]
        return "target", int(t[j]), R
    if si >= len(t):
        return None
    return "stop", int(t[si]), o[si] * (1 - SPR)


def run(which):
    d = pd.read_parquet(OUT / f"f3_{which}_sample.parquet")
    bot = which == "bot"
    rows = []
    for coin, g in d.groupby("coin", sort=True):
        for _, x in g.iterrows():
            m = int(x.t_F3_1)
            R_mine = target_of(float(x.L), float(x.P0), float(x.tick))
            R = float(x.target)
            ts = rule_m(m + 72 * 60)
            b = bars(coin, months_between(m, ts + 3 * 24 * 60))
            res = sim(*b, m, R, bot) if b is not None else None
            if res is None:
                rows.append(dict(fill_id=x.fill_id, coin=coin, ok=False, why="no bars", R_eng=R, R_mine=R_mine))
                continue
            kind, et, px = res
            et_eng = int(x.exit_t) if not isinstance(x.exit_t, pd.Timestamp) else int(x.exit_t.value // 60_000_000_000)
            ok = (kind == x.exit_kind) and (et == et_eng) and abs(px / float(x.exit_px) - 1) < 1e-9
            rows.append(dict(fill_id=x.fill_id, coin=coin, ok=ok, kind=kind, kind_eng=x.exit_kind, t=et, t_eng=et_eng,
                             px=px, px_eng=float(x.exit_px), r_mine=px / float(x.L) - 1, r_eng=float(x.r),
                             R_eng=R, R_mine=R_mine, L=float(x.L), delta_eng=float(x.delta),
                             twin_mean=float(x.twin_mean)))
        # free this coin's months
        for k in [k for k in _cache if k[0] == coin]:
            del _cache[k]
    r = pd.DataFrame(rows)
    r.to_csv(OUT / f"s2_{which}_check.csv", index=False)
    n = len(r)
    print(f"== F3_1 {'X-FLIP-bot' if bot else 'X-FLIP'}: {n} fills; exits reproduced exactly: {int(r.ok.sum())}; "
          f"mismatches: {int((~r.ok).sum())}")
    print("  target R1/2: engine vs my ceil-on-tick: max rel diff",
          float(np.nanmax(np.abs(r.R_eng / r.R_mine - 1))))
    print("  my exit kinds:", r.kind.value_counts().to_dict() if "kind" in r else {})
    print(f"  mean r (mine, all {n}) = {r.r_mine.mean():.6f}; engine mean r = {r.r_eng.mean():.6f}")
    dl = r.r_mine - r.twin_mean
    print(f"  mean Delta (my r - engine twin mean) = {dl.mean():.6f}; engine mean Delta = {r.delta_eng.mean():.6f}")
    if (~r.ok).any():
        print(r.loc[~r.ok].head(20).to_string())
    return r


if __name__ == "__main__":
    for w in sys.argv[1:] or ["flip", "bot"]:
        run(w)
