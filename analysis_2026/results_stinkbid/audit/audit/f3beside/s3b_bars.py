"""Step 3: every F3_1 flip exit (X-FLIP rule M and X-FLIP-bot) recomputed from the raw 1m index bars, from the
prereg's words (§7, §8) with my own clock:

- rule M: an event at minute t acts at t + 60 if t's America/New_York clock time is 07:00-22:59, else at the next
  07:00 New York time (zoneinfo);
- live index minute: present, >= 30 index updates, outside the Robinhood outage windows (each listed date's New York
  calendar day, +-1 h);
- target R1/2 = ceil(L + (P0 - L)/2) on the tick; the F3 target fills when the index high >= R1/2 / (1 - 0.0095);
  market sells (and the marketable check at go-live) get index open x (1 - 0.0095); entry at L (no cost);
- X-FLIP: live from M(fill); X-FLIP-bot: live from fill + 1 minute; time stop at the first live minute at or after
  M(fill + 72 h) for both.
r_f = proceeds / L - 1. Compared fill by fill with the engine's outcome rows.
"""
import sys
import json
from decimal import Decimal, ROUND_CEILING
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

OUT = sys.argv[1]
NY = ZoneInfo("America/New_York")
SPR = 0.0095
OUTAGE_DATES = ["2021-04-15", "2021-05-04", "2022-02-25", "2025-10-06", "2025-10-20"]


def minute_of(dt) -> int:
    return int(dt.timestamp() // 60)


def rule_m(t: int) -> int:
    u = datetime.fromtimestamp(t * 60, tz=timezone.utc)
    loc = u.astimezone(NY)
    mins = loc.hour * 60 + loc.minute
    if 7 * 60 <= mins <= 22 * 60 + 59:
        return t + 60
    d = loc.date() if mins < 7 * 60 else loc.date() + timedelta(days=1)
    nxt = datetime(d.year, d.month, d.day, 7, 0, tzinfo=NY)
    return minute_of(nxt.astimezone(timezone.utc))


OUTAGES = []
for ds in OUTAGE_DATES:
    y, mo, dd = map(int, ds.split("-"))
    a = datetime(y, mo, dd, tzinfo=NY)
    b = datetime.combine(a.date() + timedelta(days=1), datetime.min.time(), tzinfo=NY)
    OUTAGES.append((minute_of(a) - 60, minute_of(b) + 60))


def ceil_tick(x: float, tick_str: str) -> float:
    q = Decimal(tick_str)
    n = (Decimal(repr(x)) / q).to_integral_value(rounding=ROUND_CEILING)
    return float(n * q)


def load_index(coin: str, months) -> pd.DataFrame:
    parts = []
    for m in sorted(months):
        p = f"data/stinkbid/fut1m/index/{coin}/{m}.parquet"
        try:
            k = pd.read_parquet(p, columns=["open_time", "open", "high", "updates"])
        except FileNotFoundError:
            continue
        parts.append(k)
    if not parts:
        return pd.DataFrame(columns=["t", "open", "high", "live"])
    k = pd.concat(parts, ignore_index=True)
    t = (k["open_time"].astype("int64") // 60_000_000_000).to_numpy(np.int64)
    k = pd.DataFrame({"t": t, "open": k["open"].to_numpy(float), "high": k["high"].to_numpy(float),
                      "upd": k["updates"].to_numpy(np.int64)})
    k = k.sort_values("t").drop_duplicates("t", keep="last").reset_index(drop=True)
    live = k["upd"].to_numpy() >= 30
    for a, b in OUTAGES:
        live &= ~((k["t"].to_numpy() >= a) & (k["t"].to_numpy() < b))
    k["live"] = live
    return k


def exit_of(k_t, k_o, k_h, k_live, m, g, S, T, include_golive=True):
    lt = k_t[k_live]
    lo = k_o[k_live]
    lh = k_h[k_live]
    gi = np.searchsorted(lt, g)
    if gi >= len(lt):
        return dict(kind="none")
    if lt[gi] >= S:
        si = np.searchsorted(lt, S)
        return dict(kind="stop", t=int(lt[si]), px=float(lo[si] * (1 - SPR)))
    if lo[gi] * (1 - SPR) >= T:
        return dict(kind="marketable", t=int(lt[gi]), px=float(lo[gi] * (1 - SPR)))
    si = np.searchsorted(lt, S)
    a = gi if include_golive else gi + 1
    hit = np.nonzero(lh[a:si] >= T / (1 - SPR))[0]
    if len(hit):
        return dict(kind="target", t=int(lt[a + hit[0]]), px=float(T))
    if si >= len(lt):
        return dict(kind="none")
    return dict(kind="stop", t=int(lt[si]), px=float(lo[si] * (1 - SPR)))


rows = []
for ex in ("FLIP", "FLIP_bot"):
    d = pd.read_parquet(f"{OUT}/rows_F3_1_{ex}.parquet")
    for coin, g in d.groupby("coin"):
        ms_ = set()
        for m in g["t_F3_1"].to_numpy(np.int64):
            for dd in range(-1, 8):
                ms_.add(datetime.fromtimestamp((m + dd * 1440) * 60, tz=timezone.utc).strftime("%Y-%m"))
        k = load_index(coin, ms_)
        k_t, k_o, k_h, k_l = (k["t"].to_numpy(np.int64), k["open"].to_numpy(float), k["high"].to_numpy(float),
                              k["live"].to_numpy(bool))
        for _, f in g.iterrows():
            m = int(f["t_F3_1"])
            xL, xP = Decimal(repr(float(f["L"]))), Decimal(repr(float(f["P0"]))) 
            q = Decimal(str(f["tick_str"]))
            T = float(((xL + (xP - xL) / 2) / q).to_integral_value(rounding=ROUND_CEILING) * q)
            g0 = rule_m(m) if ex == "FLIP" else m + 1
            S = rule_m(m + 72 * 60)
            e = exit_of(k_t, k_o, k_h, k_l, m, g0, S, T)
            e2 = exit_of(k_t, k_o, k_h, k_l, m, g0, S, T, include_golive=False)
            rows.append(dict(exit=ex, fill_id=int(f["fill_id"]), coin=coin, m=m, L=float(f["L"]), T_mine=T,
                             T_eng=float(f["target"]), kind_mine=e["kind"], t_mine=e.get("t", -1),
                             px_mine=e.get("px", np.nan), r_mine=e.get("px", np.nan) / float(f["L"]) - 1,
                             kind_eng=f["exit_kind"], t_eng=int(f["exit_t"]), px_eng=float(f["exit_px"]),
                             r_eng=float(f["r"]), delta_eng=float(f["delta"]), twin_mean=float(f["twin_mean"]),
                             r_mine_strict=e2.get("px", np.nan) / float(f["L"]) - 1, kind_strict=e2["kind"]))
        del k

R = pd.DataFrame(rows)
R.to_parquet(f"{OUT}/s3b_bars.parquet")
summ = {}
for ex, g in R.groupby("exit"):
    tgt_ok = np.isclose(g.T_mine, g.T_eng, rtol=0, atol=1e-12 * np.maximum(1, g.T_eng.abs()))
    same_kind = (g.kind_mine == g.kind_eng)
    same_t = (g.t_mine == g.t_eng)
    same_px = np.isclose(g.px_mine, g.px_eng, rtol=1e-12, atol=0)
    bad = g[~(same_kind & same_t & same_px)]
    summ[ex] = dict(n=len(g), target_mismatch=int((~tgt_ok).sum()), exit_mismatch=len(bad),
                    mean_r_mine=float(g.r_mine.mean()), mean_r_engine=float(g.r_eng.mean()),
                    mean_delta_with_my_r=float((g.r_mine - g.twin_mean).mean()),
                    mean_r_mine_strict_later_minute=float(g.r_mine_strict.mean()),
                    strict_differs=int((~np.isclose(g.r_mine_strict, g.r_mine)).sum()),
                    kinds_mine=g.kind_mine.value_counts().to_dict())
    print(ex, json.dumps(summ[ex]))
    if len(bad):
        print(bad[["fill_id", "coin", "m", "T_mine", "T_eng", "kind_mine", "kind_eng", "t_mine", "t_eng", "px_mine",
                   "px_eng"]].head(20).to_string())
json.dump(summ, open(f"{OUT}/s3b_bars.json", "w"), indent=1)
