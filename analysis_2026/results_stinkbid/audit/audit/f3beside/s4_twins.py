"""Step 4: independent B-TWIN simulation on the F3 route (prereg §10.1, §8), my own random draws.

For each F3_1 fill whose engine twins were not pooled: 100 entries drawn uniformly from the coin's eligible minutes
(live index minutes - >= 30 updates, outside the Robinhood outage days +-1 h - inside the coin's own spot segments, in
a U-Q1 member month, outside [tau_f - 182 d, tau_f + 182 d], with the exit horizon M(entry + 72 h) inside the data);
each twin buys at the ask, index open x (1 + 0.0095), and exits by the fill's rule with the fill's relative target
(T / L) on its paid price: the F3 target fills when index high >= target / (1 - 0.0095), market sells (and the
marketable check) get index open x (1 - 0.0095); go-live M(entry) (X-FLIP) or entry + 1 (X-FLIP-bot), time stop at
the first live minute at or after M(entry + 72 h). twin r = proceeds / paid - 1.
Compares my per-fill twin means and mean Delta with the engine's.
"""
import sys
import json
from decimal import Decimal, ROUND_CEILING
import numpy as np
import pandas as pd

OUT = sys.argv[1]
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 4242
NY = "America/New_York"
SPR = 0.0095
OUTAGE_DATES = ["2021-04-15", "2021-05-04", "2022-02-25", "2025-10-06", "2025-10-20"]
DATA_END = int(pd.Timestamp("2026-11-18", tz="UTC").value // 60_000_000_000)
DAY = 1440


def rule_m_vec(t: np.ndarray) -> np.ndarray:
    t = np.asarray(t, np.int64)
    ts = pd.DatetimeIndex(pd.to_datetime(t * 60, unit="s", utc=True))
    loc = ts.tz_convert(NY)
    mins = (loc.hour * 60 + loc.minute).to_numpy()
    ok = (mins >= 420) & (mins <= 1379)
    out = t + 60
    if (~ok).any():
        l2 = loc[~ok]
        day = l2.tz_localize(None).normalize()
        add = np.where(mins[~ok] < 420, 0, 1)
        nxt = (day + pd.to_timedelta(add, unit="D") + pd.Timedelta("7h")).tz_localize(NY).tz_convert("UTC")
        out[~ok] = ((nxt - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1min")).to_numpy(np.int64)
    return out


OUTAGES = []
for ds in OUTAGE_DATES:
    a = pd.Timestamp(ds).tz_localize(NY).tz_convert("UTC").value // 60_000_000_000
    b = (pd.Timestamp(ds) + pd.Timedelta("1D")).tz_localize(NY).tz_convert("UTC").value // 60_000_000_000
    OUTAGES.append((a - 60, b + 60))

U = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
SEG = pd.read_csv("data/stinkbid/ref/segments.csv", usecols=["coin", "seg", "first_day", "end"])


def month_str(m):
    return pd.to_datetime(np.asarray(m, np.int64) * 60, unit="s", utc=True).strftime("%Y-%m").to_numpy()


def coin_series(coin):
    members = sorted(U.loc[(U.coin == coin) & U.U_Q1, "month"].unique())
    months = set(members)
    for m in members:                                   # the month after each member month (exits run past it)
        p = pd.Period(m, "M") + 1
        months.add(str(p))
    parts = []
    for m in sorted(months):
        try:
            x = pd.read_parquet(f"data/stinkbid/fut1m/index/{coin}/{m}.parquet",
                                columns=["open_time", "open", "high", "updates"])
        except FileNotFoundError:
            continue
        if not len(x):
            continue
        x["open_time"] = pd.to_datetime(x["open_time"], utc=True)
        x["tmin"] = (x["open_time"] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1min")
        parts.append(x[["tmin", "open", "high", "updates"]])
    k = pd.concat(parts, ignore_index=True)
    t = k["tmin"].to_numpy(np.int64)
    o = np.argsort(t, kind="stable")
    t, op, hi, up = t[o], k["open"].to_numpy(float)[o], k["high"].to_numpy(float)[o], k["updates"].to_numpy()[o]
    keep = np.r_[True, np.diff(t) > 0]
    t, op, hi, up = t[keep], op[keep], hi[keep], up[keep]
    live = up >= 30
    for a, b in OUTAGES:
        live &= ~((t >= a) & (t < b))
    # inside the coin's own spot segments
    s = SEG[SEG.coin == coin]
    inseg = np.zeros(len(t), bool)
    for _, r in s.iterrows():
        a = int(pd.Timestamp(r["first_day"], tz="UTC").value // 60_000_000_000)
        b = int(pd.Timestamp(r["end"]).value // 60_000_000_000)
        inseg |= (t >= a) & (t < b)
    live &= inseg
    lt, lo, lh = t[live], op[live], hi[live]
    member = np.isin(month_str(lt), np.array(members))
    return lt, lo, lh, member


def run_exits(lt, lo, lh, g, S, Tgt):
    n = len(g)
    px = np.full(n, np.nan)
    gi = np.searchsorted(lt, g)
    si = np.searchsorted(lt, S)
    for j in range(n):
        a, b = gi[j], si[j]
        if a >= len(lt):
            continue
        if lt[a] >= S[j]:
            if b < len(lt):
                px[j] = lo[b] * (1 - SPR)
            continue
        if lo[a] * (1 - SPR) >= Tgt[j]:
            px[j] = lo[a] * (1 - SPR)
            continue
        hit = np.flatnonzero(lh[a:b] >= Tgt[j] / (1 - SPR))
        if len(hit):
            px[j] = Tgt[j]
        elif b < len(lt):
            px[j] = lo[b] * (1 - SPR)
    return px


rng = np.random.default_rng(SEED)
fl = pd.read_parquet(f"{OUT}/rows_F3_1_FLIP.parquet")
fb = pd.read_parquet(f"{OUT}/rows_F3_1_FLIP_bot.parquet")
d = fl[["fill_id", "coin", "t_F3_1", "L", "target", "twin_mean", "twin_pooled", "r", "delta"]].merge(
    fb[["fill_id", "twin_mean", "twin_pooled", "r", "delta"]], on="fill_id", suffixes=("_flip", "_bot"))
rows = []
for coin, g in d.groupby("coin"):
    lt, lo, lh, member = coin_series(coin)
    # complete window: M(entry + 72 h) at or before the data end
    S_all = None
    near = lt > DATA_END - 6 * DAY
    complete = np.ones(len(lt), bool)
    if near.any():
        complete[near] = rule_m_vec(lt[near] + 72 * 60) < DATA_END
    elig = member & complete
    et = lt[elig]
    eidx = np.flatnonzero(elig)
    eday = et // DAY
    for _, f in g.iterrows():
        tau = int(f["t_F3_1"])
        out_win = (et < tau - 182 * DAY) | (et > tau + 182 * DAY)
        cand = eidx[out_win]
        ndays = len(np.unique(eday[out_win]))
        row = dict(fill_id=int(f["fill_id"]), coin=coin, elig_minutes=len(cand), elig_days=ndays,
                   pooled_eng=bool(f["twin_pooled_flip"]))
        if ndays >= 182 and not f["twin_pooled_flip"]:
            pick = cand[np.minimum((rng.random(100) * len(cand)).astype(np.int64), len(cand) - 1)]
            te = lt[pick]
            paid = lo[pick] * (1 + SPR)
            ratio = float(f["target"]) / float(f["L"])
            Tg = paid * ratio
            S = rule_m_vec(te + 72 * 60)
            px_f = run_exits(lt, lo, lh, rule_m_vec(te), S, Tg)
            px_b = run_exits(lt, lo, lh, te + 1, S, Tg)
            row.update(tm_flip_mine=float(np.nanmean(px_f / paid - 1)), tm_bot_mine=float(np.nanmean(px_b / paid - 1)),
                       n_nan=int(np.isnan(px_f).sum() + np.isnan(px_b).sum()),
                       sd_flip=float(np.nanstd(px_f / paid - 1)), sd_bot=float(np.nanstd(px_b / paid - 1)))
        row.update(tm_flip_eng=float(f["twin_mean_flip"]), tm_bot_eng=float(f["twin_mean_bot"]),
                   r_flip=float(f["r_flip"]), r_bot=float(f["r_bot"]))
        rows.append(row)
    del lt, lo, lh, member

R = pd.DataFrame(rows)
R.to_parquet(f"{OUT}/s4_twins_{SEED}.parquet")
sim = R[R.tm_flip_mine.notna()] if "tm_flip_mine" in R else R.iloc[:0]
summ = dict(seed=SEED, fills=len(R), simulated=len(sim), engine_pooled=int(R.pooled_eng.sum()),
            my_lt182_days=int((R.elig_days < 182).sum()),
            pooled_agree=int(((R.elig_days < 182) == R.pooled_eng).sum()))
for ex in ("flip", "bot"):
    diff = sim[f"tm_{ex}_mine"] - sim[f"tm_{ex}_eng"]
    se_mc = np.sqrt(((sim[f"sd_{ex}"] ** 2) / 100 * 2).sum()) / len(sim)   # both are 100-draw means
    summ[ex] = dict(mean_twin_eng=float(sim[f"tm_{ex}_eng"].mean()), mean_twin_mine=float(sim[f"tm_{ex}_mine"].mean()),
                    mean_diff=float(diff.mean()), mc_se_of_mean_diff=float(se_mc),
                    corr=float(np.corrcoef(sim[f"tm_{ex}_mine"], sim[f"tm_{ex}_eng"])[0, 1]),
                    mean_delta_eng=float((sim[f"r_{ex}"] - sim[f"tm_{ex}_eng"]).mean()),
                    mean_delta_mine=float((sim[f"r_{ex}"] - sim[f"tm_{ex}_mine"]).mean()),
                    max_abs_diff=float(diff.abs().max()))
print(json.dumps(summ, indent=1))
json.dump(summ, open(f"{OUT}/s4_twins_{SEED}.json", "w"), indent=1)
