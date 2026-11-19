"""Independent B-TWIN check for H1 (prereg §10.1), auditor's own code: for every H1 fill with own-coin twins,
draw K entry minutes uniformly from the coin's live minutes in its U-Q1 member months, outside
[tau_f - 182 d, tau_f + 182 d], whose X-FLIP horizon M(e + 72 h) is observed; each twin enters at the minute's open,
targets open x (R1/2 / L), sells live at M(e) (marketable at that minute's open if open >= target, else resting until
the first minute with high >= target + tick), time stop at the open of the first live minute >= M(e + 72 h); C-RH on
both sides. Compares my twin means with the engine's twin_mean, and H1's mean Delta with my twins."""
import resource
import sys
import numba as nb
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from analysis_2026 import stinkbid_data as sbd  # symbol map only

D = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest"
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1"
NY = "America/New_York"
C = 0.0095
K = int(sys.argv[1]) if len(sys.argv) > 1 else 200
END_MIN = int(pd.Timestamp("2026-11-18", tz="UTC").value // 60_000_000_000) - 1
DAY = 1440


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


@nb.njit(cache=False)
def exits(o, h, gi, si, T, up):
    n = gi.size
    px = np.full(n, np.nan)
    kind = np.zeros(n, np.int64)   # 1 marketable, 2 target, 3 stop, 0 censored
    N = o.size
    for k in range(n):
        g, s = gi[k], si[k]
        if g >= N or s >= N:
            continue
        if o[g] >= T[k]:
            px[k] = o[g]
            kind[k] = 1
            continue
        hit = -1
        for j in range(g, s):
            if h[j] >= up[k]:
                hit = j
                break
        if hit >= 0:
            px[k] = T[k]
            kind[k] = 2
        else:
            px[k] = o[s]
            kind[k] = 3
    return px, kind


F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["fill_id", "coin", "L", "t_F1"])
O = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["fill_id", "r", "delta", "twin_mean", "twin_pooled", "target", "complete"],
                    filters=[("rule", "==", "F1"), ("exit", "==", "FLIP"), ("cost", "==", "C-RH")])
H = F[F.t_F1 >= 0].merge(O[O.complete], on="fill_id")
H = H[np.isfinite(H.delta)].reset_index(drop=True)
U = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
U = U[U.U_Q1]
Bd = pd.read_parquet(f"{RUN}/bids.parquet", columns=["coin", "t0", "tick"]).drop_duplicates(["coin", "t0"])
rng = np.random.default_rng(777)
res = []
for coin, g in H[~H.twin_pooled].groupby("coin"):
    sym = sbd.coin_sym(coin)[0]
    k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet", columns=["open_time", "open", "high", "trades"])
    t = k.open_time.astype("int64").to_numpy() // 60_000_000_000
    live = k.trades.to_numpy() > 0
    t, o, h = t[live], k.open.to_numpy()[live], k.high.to_numpy()[live]
    del k
    months = np.array([(int(m[:4]) - 1970) * 12 + int(m[5:7]) - 1 for m in U.loc[U.coin == coin, "month"]], np.int64)
    mon = (t * 60).astype("datetime64[s]").astype("datetime64[M]").astype(np.int64)
    elig = np.isin(mon, months)
    del mon
    # horizon observed: M(e + 72 h) <= END_MIN  (rule M adds at most ~9.5 h; check exactly for the tail)
    tail = elig & (t > END_MIN - 72 * 60 - 12 * 60)
    if tail.any():
        hz = rule_m_min(t[tail] + 72 * 60)
        idx = np.flatnonzero(tail)
        elig[idx[hz > END_MIN]] = False
    eidx = np.flatnonzero(elig)
    et = t[eidx]
    bt = Bd[Bd.coin == coin].sort_values("t0")
    for _, f in g.iterrows():
        tf = int(f.t_F1)
        lo = np.searchsorted(et, tf - 182 * DAY, side="left")
        hi = np.searchsorted(et, tf + 182 * DAY, side="right")
        nL, nR = lo, len(et) - hi
        if nL + nR == 0:
            continue
        u = rng.integers(0, nL + nR, size=K)
        pick = np.where(u < nL, eidx[np.minimum(u, max(nL - 1, 0))], eidx[np.minimum(hi + u - nL, len(eidx) - 1)])
        te = t[pick]
        P = o[pick]
        ratio = float(f.target) / float(f.L)
        T = P * ratio
        ti = np.searchsorted(bt.t0.to_numpy(), te, side="right") - 1
        tau = bt.tick.to_numpy()[np.clip(ti, 0, len(bt) - 1)]
        up = T + tau - 1e-9 * T
        gi = np.searchsorted(t, rule_m_min(te))
        si = np.searchsorted(t, rule_m_min(te + 72 * 60))
        px, kind = exits(o, h, gi, si, T, up)
        r = px * (1 - C) / (P * (1 + C)) - 1
        ok = np.isfinite(r)
        res.append(dict(fill_id=int(f.fill_id), coin=coin, t=tf, r=float(f.r), delta=float(f.delta), twin_file=float(f.twin_mean),
                        twin_mine=float(r[ok].mean()), twin_sd=float(r[ok].std(ddof=1)), n_ok=int(ok.sum()),
                        n_elig_days_L=int(nL), n_R=int(nR),
                        share_target=float((kind == 2).mean()), share_stop=float((kind == 3).mean())))
    del t, o, h, elig, eidx, et
R = pd.DataFrame(res)
R.to_parquet(f"{D}/twins_check_K{K}.parquet")
R["diff"] = R.twin_file - R.twin_mine
se_i = R.twin_sd * np.sqrt(1 / 100 + 1 / R.n_ok)
R["z"] = R["diff"] / se_i
print(f"fills compared: {len(R)} of {int((~H.twin_pooled).sum())} own-twin fills (pooled-twin fills: {int(H.twin_pooled.sum())}), K = {K}")
print(f"mean twin (file) {R.twin_file.mean():+.5f}; mean twin (mine) {R.twin_mine.mean():+.5f}; mean diff {R['diff'].mean():+.5f}; "
      f"SE of mean diff (indep.) {np.sqrt((se_i ** 2).sum()) / len(R):.5f}")
print(f"z of per-fill diffs: mean {R.z.mean():+.3f}, sd {R.z.std():.3f} (expect ~0, ~1); |z|>4: {int((R.z.abs() > 4).sum())}; corr {np.corrcoef(R.twin_file, R.twin_mine)[0, 1]:.4f}")
print(f"H1 mean Delta on these fills: file {R.delta.mean():+.5f}; with my twins {(R.r - R.twin_mine).mean():+.5f}")
print("largest |z|:")
print(R.reindex(R.z.abs().sort_values(ascending=False).index).head(12)[["fill_id", "coin", "t", "twin_file", "twin_mine", "twin_sd", "n_ok", "z", "n_R"]].to_string())
print("maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
