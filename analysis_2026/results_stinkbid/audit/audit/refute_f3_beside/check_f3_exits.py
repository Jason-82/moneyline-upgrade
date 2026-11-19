"""Independent re-derivation of the F3_1 (s = 1%) X-FLIP and X-FLIP-bot exits on the raw 1m index bars.

Prereg definitions used (written here, not imported):
  rule M (§8): action at t + 60 min if t is 07:00-22:59 New York, else at the next 07:00 New York.
  X-FLIP (§8): target R1/2 = ceil(L + (P0 - L)/2) on the tick, live from M(fill) (bot: fill + 1 minute); marketable
    at the go-live minute's open if already at/above R1/2; else first later minute that trades through it; else a
    market sell at the first live minute at or after M(fill + 72 h).
  F3 route (§8): target fills when index high >= R1/2 / (1 - 0.0095); market (and marketable) sells get
    index open x (1 - 0.0095); the buy pays L.
  Live index minute (§7): present, >= 30 updates, outside the Robinhood outage windows (+-1 h around the listed
    New York days).
Reads data/stinkbid/fut1m/index/<coin>/<YYYY-MM>.parquet directly (no loader, so nothing can be downloaded).
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUTD = Path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/"
            "refute_f3_beside")
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1/"
IDX = Path("data/stinkbid/fut1m/index")
SPR = 0.0095
NY = "America/New_York"
OUT_DATES = ("2021-04-15", "2021-05-04", "2022-02-25", "2025-10-06", "2025-10-20")


def tmin(ts):
    # pandas 3 keeps the input resolution (s, ms, us); force ns before reading the integers
    return (pd.DatetimeIndex(ts).tz_convert("UTC").as_unit("ns").asi8 // 60_000_000_000).astype(np.int64)


def rule_m(m):
    m = np.atleast_1d(np.asarray(m, np.int64))
    t = pd.to_datetime(m * 60, unit="s", utc=True)
    loc = t.tz_convert(NY)
    mins = loc.hour * 60 + loc.minute
    ok = (mins >= 7 * 60) & (mins <= 22 * 60 + 59)
    day = loc.tz_localize(None).normalize()
    nxt_day = np.where(mins < 7 * 60, day, day + pd.Timedelta("1D"))
    nxt = pd.DatetimeIndex(nxt_day) + pd.Timedelta("7h")
    nxt = nxt.tz_localize(NY).tz_convert("UTC")
    return np.where(ok, m + 60, tmin(nxt))


WIN = []
for d in OUT_DATES:
    a = pd.Timestamp(d).tz_localize(NY).tz_convert("UTC")
    b = (pd.Timestamp(d) + pd.Timedelta("1D")).tz_localize(NY).tz_convert("UTC")
    WIN.append((int(tmin([a])[0]) - 60, int(tmin([b])[0]) + 60))


def in_outage(t):
    m = np.zeros(t.shape, bool)
    for a, b in WIN:
        m |= (t >= a) & (t < b)
    return m


def load_index(coin, months):
    parts = []
    missing = []
    for mo in months:
        f = IDX / coin / f"{mo}.parquet"
        if not f.exists():
            missing.append(mo)
            continue
        k = pd.read_parquet(f)
        if len(k):
            parts.append(k)
    if not parts:
        return None, missing
    k = pd.concat(parts, ignore_index=True)
    t = tmin(k["open_time"])
    o = np.argsort(t, kind="stable")
    k = k.iloc[o].reset_index(drop=True)
    t = t[o]
    keep = np.r_[True, np.diff(t) > 0]
    k = k[keep].reset_index(drop=True)
    t = t[keep]
    live = (k["updates"].to_numpy(np.int64) >= 30) & ~in_outage(t)
    return dict(t=t, o=k["open"].to_numpy(float), h=k["high"].to_numpy(float), l=k["low"].to_numpy(float),
                live=live, upd=k["updates"].to_numpy(np.int64)), missing


def first_live_ge(ix, tmin_):
    i = np.searchsorted(ix["t"], tmin_)
    lv = np.flatnonzero(ix["live"][i:])
    return i + lv[0] if len(lv) else -1


def my_exit(ix, m, T, lat):
    g = m + 1 if lat == "bot" else int(rule_m(m)[0])
    S = int(rule_m(m + 72 * 60)[0])
    gi = first_live_ge(ix, g)
    if gi < 0:
        return "noexit", -1, np.nan
    if ix["t"][gi] >= S:
        si = first_live_ge(ix, S)
        return ("stop", int(ix["t"][si]), ix["o"][si] * (1 - SPR)) if si >= 0 else ("noexit", -1, np.nan)
    if ix["o"][gi] * (1 - SPR) >= T:
        return "marketable", int(ix["t"][gi]), ix["o"][gi] * (1 - SPR)
    si = first_live_ge(ix, max(int(ix["t"][gi]), S))
    end = si if si >= 0 else len(ix["t"])
    seg = np.arange(gi, end)
    hit = seg[ix["live"][seg] & (ix["h"][seg] >= T / (1 - SPR))]
    if len(hit):
        return "target", int(ix["t"][hit[0]]), T
    if si >= 0:
        return "stop", int(ix["t"][si]), ix["o"][si] * (1 - SPR)
    return "noexit", -1, np.nan


def _selfcheck():
    def M(s):
        return pd.to_datetime(int(rule_m(tmin([pd.Timestamp(s, tz="UTC")]))[0]) * 60, unit="s", utc=True)
    assert M("2021-05-19 12:00") == pd.Timestamp("2021-05-19 13:00", tz="UTC")      # 08:00 EDT, day: +60
    assert M("2021-05-19 04:00") == pd.Timestamp("2021-05-19 11:00", tz="UTC")      # 00:00 EDT -> 07:00 EDT
    assert M("2021-05-19 02:59") == pd.Timestamp("2021-05-19 03:59", tz="UTC")      # 22:59 EDT, day: +60
    assert M("2021-05-19 03:00") == pd.Timestamp("2021-05-19 11:00", tz="UTC")      # 23:00 EDT -> next 07:00 EDT
    assert M("2022-11-09 02:00") == pd.Timestamp("2022-11-09 03:00", tz="UTC")      # 21:00 EST, day: +60
    assert M("2022-11-09 05:00") == pd.Timestamp("2022-11-09 12:00", tz="UTC")      # 00:00 EST -> 07:00 EST
    assert M("2025-10-10 21:30") == pd.Timestamp("2025-10-10 22:30", tz="UTC")      # 17:30 EDT, day: +60
    a, b = WIN[4]                                                                    # 2025-10-20 New York day +-1 h
    assert pd.to_datetime(a * 60, unit="s", utc=True) == pd.Timestamp("2025-10-20 03:00", tz="UTC")
    assert pd.to_datetime(b * 60, unit="s", utc=True) == pd.Timestamp("2025-10-21 05:00", tz="UTC")
    print("rule M and outage-window self-check passed")


def main():
    _selfcheck()
    F = pd.read_parquet(RUN + "fills.parquet", columns=["fill_id", "coin", "L", "P0", "tick", "t_F3_1"])
    O = pd.read_parquet(RUN + "outcomes.parquet",
                        columns=["rule", "exit", "cost", "fill_id", "r", "exit_kind", "exit_t", "exit_px", "target",
                                 "complete", "twin_mean", "delta"],
                        filters=[("rule", "=", "F3_1"), ("exit", "in", ["FLIP", "FLIP_bot"]), ("cost", "=", "RH")])
    d = F[F["t_F3_1"] >= 0].merge(O, on="fill_id")
    d = d[d["complete"].astype(bool) & np.isfinite(d["delta"])].reset_index(drop=True)
    print("rows to check:", len(d), d.groupby("exit").size().to_dict())
    res = []
    for coin, g in d.groupby("coin", sort=True):
        need = set()
        for m_ in g["t_F3_1"].to_numpy(np.int64):
            need |= set(pd.period_range(pd.to_datetime(int(m_) * 60, unit="s"),
                                        pd.to_datetime((int(m_) + 5 * 1440) * 60, unit="s"), freq="M").strftime("%Y-%m"))
        ix, missing = load_index(coin, sorted(need))
        for _, r in g.iterrows():
            m = int(r["t_F3_1"])
            L, P0, tau = float(r["L"]), float(r["P0"]), float(r["tick"])
            Tme = math.ceil((L + 0.5 * (P0 - L)) / tau - 1e-9) * tau
            rec = dict(coin=coin, fill_id=int(r["fill_id"]), exit=r["exit"], L=L, m=m, T_engine=float(r["target"]),
                       T_mine=Tme, kind_e=r["exit_kind"], t_e=int(r["exit_t"]), px_e=float(r["exit_px"]),
                       r_e=float(r["r"]), twin_mean=float(r["twin_mean"]), missing_months=",".join(missing))
            if ix is None:
                rec.update(kind_m="noindex", t_m=-1, px_m=np.nan, fill_ok=False)
                res.append(rec)
                continue
            # the F3 fill minute itself: live and index low <= L / 1.01
            j = np.searchsorted(ix["t"], m)
            fill_ok = bool(j < len(ix["t"]) and ix["t"][j] == m and ix["live"][j] and ix["l"][j] <= L / 1.01 * (1 + 1e-12))
            k, tm, px = my_exit(ix, m, float(r["target"]), "bot" if r["exit"] == "FLIP_bot" else "M")
            rec.update(kind_m=k, t_m=tm, px_m=px, fill_ok=fill_ok)
            res.append(rec)
        del ix
    R = pd.DataFrame(res)
    R["r_mine"] = R["px_m"] / R["L"] - 1
    R["delta_mine"] = R["r_mine"] - R["twin_mean"]
    R["match"] = (R["kind_m"] == R["kind_e"]) & (R["t_m"] == R["t_e"]) & \
        np.isclose(R["px_m"], R["px_e"], rtol=1e-9, atol=0)
    R["T_match"] = np.isclose(R["T_mine"], R["T_engine"], rtol=1e-9, atol=0)
    R.to_csv(OUTD / "f3_exit_check.csv", index=False)
    for ex, g in R.groupby("exit"):
        print(f"\n{ex}: n {len(g)}; exits matching the engine (kind, minute, price): {int(g['match'].sum())}; "
              f"targets matching ceil-rule: {int(g['T_match'].sum())}; F3 fill minute verified: "
              f"{int(g['fill_ok'].sum())}; rows with missing index months: {int((g['missing_months'] != '').sum())}")
        print(f"  mean r engine {g['r_e'].mean():+.5f}; mean r from my exits {g['r_mine'].mean():+.5f} "
              f"(n finite {int(np.isfinite(g['r_mine']).sum())}); mean Delta from my exits "
              f"{g['delta_mine'].mean():+.5f}")
        bad = g[~g["match"]]
        if len(bad):
            print("  mismatches (first 10):")
            print(bad[["coin", "fill_id", "kind_e", "kind_m", "t_e", "t_m", "px_e", "px_m"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
