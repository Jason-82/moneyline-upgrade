"""Independent check of the pooled twins (prereg §10.1: fewer than 182 eligible days -> pooled twins from all U-Q1
coins' eligible minutes outside +-182 days of tau_f). Auditor's own code. Pass 1: per U-Q1 coin, eligible live
minutes per UTC day in its member months. Pass 2: per pooled fill, K draws uniform over the pooled eligible minutes
(whole days touching [tau_f - 182 d, tau_f + 182 d] left out; horizon observed). Pass 3: per coin, simulate X-FLIP
exits with the fill's relative target, rule-M clock, C-RH."""
import resource
import sys
import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest"
sys.path.insert(0, D)
sys.path.insert(0, ".")
from analysis_2026 import stinkbid_data as sbd  # symbol map only
import importlib.util
spec = importlib.util.spec_from_file_location("s7", f"{D}/s7_twins.py")
# reuse my own helpers from s7 without running it: copy the two functions here instead
NY = "America/New_York"
C = 0.0095
K = 200
DAY = 1440
END_MIN = int(pd.Timestamp("2026-11-18", tz="UTC").value // 60_000_000_000) - 1
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1"


def rule_m_min(tmin):
    ts = pd.to_datetime(np.asarray(tmin, np.int64) * 60_000_000_000, utc=True)
    loc = ts.tz_convert(NY)
    mins = np.asarray(loc.hour * 60 + loc.minute)
    day = loc.tz_localize(None).normalize()
    nxt_day = np.where(mins < 420, day, day + pd.Timedelta("1D"))
    nxt = (pd.DatetimeIndex(nxt_day) + pd.Timedelta("7h")).tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    plus = ts + pd.Timedelta("60min")
    out = np.where((mins >= 420) & (mins <= 1379), plus.as_unit("ns").asi8, nxt.as_unit("ns").asi8)
    return out // 60_000_000_000


def exits(o, h, gi, si, T, up):
    n = gi.size
    px = np.full(n, np.nan)
    N = o.size
    for k in range(n):
        g, s = gi[k], si[k]
        if g >= N or s >= N:
            continue
        if o[g] >= T[k]:
            px[k] = o[g]
            continue
        hh = np.flatnonzero(h[g:s] >= up[k])
        px[k] = T[k] if len(hh) else o[s]
    return px


def load_live(coin, cols):
    sym = sbd.coin_sym(coin)[0]
    k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet", columns=["open_time", "trades"] + cols)
    t = k.open_time.astype("int64").to_numpy() // 60_000_000_000
    live = k.trades.to_numpy() > 0
    out = [t[live]] + [k[c].to_numpy()[live] for c in cols]
    del k
    return out


F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["fill_id", "coin", "L", "t_F1"])
O = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["fill_id", "r", "delta", "twin_mean", "twin_pooled", "target", "complete"],
                    filters=[("rule", "==", "F1"), ("exit", "==", "FLIP"), ("cost", "==", "C-RH")])
H = F[F.t_F1 >= 0].merge(O[O.complete], on="fill_id")
H = H[np.isfinite(H.delta) & H.twin_pooled].reset_index(drop=True)
print("pooled-twin fills:", len(H), H.coin.value_counts().head(10).to_dict())
U = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
U = U[U.U_Q1]
coins = sorted(U.coin.unique())
Bd = pd.read_parquet(f"{RUN}/bids.parquet", columns=["coin", "t0", "tick"]).drop_duplicates(["coin", "t0"])

# pass 1: eligible minutes per day
daytab = {}
for coin in coins:
    try:
        t, = load_live(coin, [])
    except FileNotFoundError:
        print("no m1 for", coin)
        continue
    months = np.array([(int(m[:4]) - 1970) * 12 + int(m[5:7]) - 1 for m in U.loc[U.coin == coin, "month"]], np.int64)
    mon = (t * 60).astype("datetime64[s]").astype("datetime64[M]").astype(np.int64)
    el = np.isin(mon, months)
    tail = el & (t > END_MIN - 84 * 60)
    if tail.any():
        idx = np.flatnonzero(tail)
        el[idx[rule_m_min(t[tail] + 72 * 60) > END_MIN]] = False
    d = t[el] // DAY
    u, c = np.unique(d, return_counts=True)
    daytab[coin] = (u, c)
    del t, mon, el, d
print("pass 1 done; coins", len(daytab), "maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)

# pass 2: draws
rng = np.random.default_rng(4242)
draws = []   # (fill row, coin, day, rank)
allc = list(daytab)
for i, f in H.iterrows():
    tf = int(f.t_F1)
    lo_d, hi_d = (tf - 182 * DAY) // DAY, (tf + 182 * DAY) // DAY
    ws, keys = [], []
    for c in allc:
        u, cnt = daytab[c]
        keep = (u < lo_d) | (u > hi_d)
        ws.append(cnt[keep])
        keys.append((c, u[keep]))
    sizes = np.array([w.sum() for w in ws], float)
    pc = rng.multinomial(K, sizes / sizes.sum())
    for (c, ud), w, nk in zip(keys, ws, pc):
        if nk == 0:
            continue
        cw = np.cumsum(w)
        x = rng.integers(0, cw[-1], size=nk)
        j = np.searchsorted(cw, x, side="right")
        rank = x - np.r_[0, cw][j]
        for jj, rr in zip(j, rank):
            draws.append((i, c, int(ud[jj]), int(rr)))
Dr = pd.DataFrame(draws, columns=["row", "coin", "day", "rank"])
print("pass 2 done; draws", len(Dr), "on coins", Dr.coin.nunique())

# pass 3: simulate per coin
out = []
for coin, g in Dr.groupby("coin"):
    t, o, h = load_live(coin, ["open", "high"])
    months = np.array([(int(m[:4]) - 1970) * 12 + int(m[5:7]) - 1 for m in U.loc[U.coin == coin, "month"]], np.int64)
    mon = (t * 60).astype("datetime64[s]").astype("datetime64[M]").astype(np.int64)
    el = np.isin(mon, months)
    tail = el & (t > END_MIN - 84 * 60)
    if tail.any():
        idx = np.flatnonzero(tail)
        el[idx[rule_m_min(t[tail] + 72 * 60) > END_MIN]] = False
    eidx = np.flatnonzero(el)
    ed = t[eidx] // DAY
    first = np.searchsorted(ed, g.day.to_numpy(), side="left")
    pick = eidx[first + g["rank"].to_numpy()]
    assert np.all(t[pick] // DAY == g.day.to_numpy())
    te, P = t[pick], o[pick]
    ratio = (H.loc[g.row, "target"].to_numpy() / H.loc[g.row, "L"].to_numpy())
    T = P * ratio
    bt = Bd[Bd.coin == coin].sort_values("t0")
    ti = np.searchsorted(bt.t0.to_numpy(), te, side="right") - 1
    tau = bt.tick.to_numpy()[np.clip(ti, 0, len(bt) - 1)]
    gi = np.searchsorted(t, rule_m_min(te))
    si = np.searchsorted(t, rule_m_min(te + 72 * 60))
    px = exits(o, h, gi, si, T, T + tau - 1e-9 * T)
    r = px * (1 - C) / (P * (1 + C)) - 1
    out.append(pd.DataFrame({"row": g.row.to_numpy(), "r": r}))
    del t, o, h, mon, el, eidx
Tw = pd.concat(out)
m = Tw.groupby("row").r.agg(["mean", "std", "count"])
H = H.join(m)
H["diff"] = H.twin_mean - H["mean"]
se = H["std"] * np.sqrt(1 / 100 + 1 / H["count"])
H["z"] = H["diff"] / se
print(f"pooled fills: {len(H)}; mean twin file {H.twin_mean.mean():+.5f}, mine {H['mean'].mean():+.5f}; mean diff {H['diff'].mean():+.5f} "
      f"(SE {np.sqrt((se ** 2).sum()) / len(H):.5f}); z mean {H.z.mean():+.3f} sd {H.z.std():.3f}; |z|>4 {int((H.z.abs() > 4).sum())}")
print(f"H1 Delta on pooled fills: file {H.delta.mean():+.5f}; with my pooled twins {(H.r - H['mean']).mean():+.5f}")
H.to_parquet(f"{D}/pooled_check.parquet")
print("maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
