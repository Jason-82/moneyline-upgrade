"""Independent recomputation of 14 P1 fills from raw 1m spot bars (prereg §6.1, §7 F1, §8 X-FLIP / rule M,
§9-§10.2 C-RH, §10.1 B-TWIN and B-ALERT). Written from the pre-registration; imports only stinkbid_data loaders.
Read-only on the repository and the data."""
import gc
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, getcontext
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = "/home/user/moneyline-upgrade"
sys.path.insert(0, ROOT)
from analysis_2026 import stinkbid_data as sbd  # data loaders only  # noqa: E402

OUT = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/engine_spot"
getcontext().prec = 50
NY = ZoneInfo("America/New_York")
UTC = timezone.utc
C = 0.0095
DAY = 1440
END_MIN = int(datetime(2026, 11, 18, tzinfo=UTC).timestamp() // 60) - 1      # 2026-11-17 23:59 UTC
SEED = 20261118
FLIP_H = 72


# ------------------------------------------------------------------------------------------------ time
def to_min(ts) -> int:
    return int(pd.Timestamp(ts).tz_convert("UTC").value // 60_000_000_000)


def mts(m) -> str:
    return datetime.fromtimestamp(int(m) * 60, tz=UTC).strftime("%Y-%m-%d %H:%M")


def rule_m(t: int) -> int:
    """§8 rule M: t + 60 if t's New York clock time is 07:00-22:59, else the next 07:00 New York time."""
    loc = datetime.fromtimestamp(int(t) * 60, tz=UTC).astimezone(NY)
    hm = loc.hour * 60 + loc.minute
    if 7 * 60 <= hm <= 22 * 60 + 59:
        return int(t) + 60
    d = loc.date() if hm < 7 * 60 else loc.date() + timedelta(days=1)
    nxt = datetime(d.year, d.month, d.day, 7, 0, tzinfo=NY)
    return int(nxt.astimezone(UTC).timestamp() // 60)


def monday_0330_before(m: int) -> int:
    """The latest Monday 03:30 UTC placement strictly before minute m (a bid placed at t0 is live from t0 + 1)."""
    t = datetime.fromtimestamp(int(m) * 60, tz=UTC)
    d = t.date() - timedelta(days=t.weekday())
    c = int(datetime(d.year, d.month, d.day, 3, 30, tzinfo=UTC).timestamp() // 60)
    while c >= m:
        c -= 7 * DAY
    return c


def monday_0330_at_or_before(m: int) -> int:
    t = datetime.fromtimestamp(int(m) * 60, tz=UTC)
    d = t.date() - timedelta(days=t.weekday())
    c = int(datetime(d.year, d.month, d.day, 3, 30, tzinfo=UTC).timestamp() // 60)
    while c > m:
        c -= 7 * DAY
    return c


# ------------------------------------------------------------------------------------------------ decimals
def ndec(x: float) -> int:
    """Decimals of the shortest decimal string of a double (repr round-trips)."""
    d = Decimal(repr(float(x)))
    e = d.normalize().as_tuple().exponent
    return max(0, -e)


def tick_from_prices(px: np.ndarray, finer_max: float = 0.001):
    """A1.3: the coarsest decimal step holding at least 99.9% of the window's prices."""
    uq, cnt = np.unique(np.asarray(px, float), return_counts=True)
    du = np.array([ndec(v) for v in uq], dtype=np.int64)
    dec = np.repeat(du, cnt)
    n = len(dec)
    for d in range(0, 16):
        if (dec > d).sum() <= finer_max * n:
            return d, int((dec > d).sum()), int(dec.max()), n
    return None, None, None, n


def tick_str(d: int) -> str:
    return "1" if d == 0 else "0." + "0" * (d - 1) + "1"


def dfloor(x: Decimal, tau: Decimal) -> Decimal:
    return (x / tau).to_integral_value(rounding=ROUND_FLOOR) * tau


def dceil(x: Decimal, tau: Decimal) -> Decimal:
    return (x / tau).to_integral_value(rounding=ROUND_CEILING) * tau


# ------------------------------------------------------------------------------------------------ data
class Coin:
    def __init__(self, coin: str):
        self.coin = coin
        sym, lo, hi = sbd.coin_sym(coin)
        self.sym = sym
        # daily klines of the pair (the file d1_panel reads), segment ids by §4.1's rule written here: a new segment
        # after a missing UTC day (no kline or trades = 0) or at an open more than 25% from the prior close
        d = pd.read_parquet(f"{ROOT}/data/stinkbid/d1_full_all.parquet", filters=[("sym", "==", sym)],
                            columns=["open_time", "open", "high", "low", "close", "trades"])
        if d.open_time.dt.tz is None:
            raise RuntimeError("naive daily open_time")
        d["day"] = d.open_time.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy().astype("datetime64[D]") \
            .astype(np.int64)
        d = d.sort_values("day").reset_index(drop=True)
        if lo:
            d = d[d.day >= int(pd.Timestamp(lo).value // 60_000_000_000 // DAY)]
        if hi:
            d = d[d.day <= int(pd.Timestamp(hi).value // 60_000_000_000 // DAY)]
        d = d[d.trades > 0].reset_index(drop=True)
        dd_ = d.day.to_numpy()
        op, cl = d.open.to_numpy(float), d.close.to_numpy(float)
        brk = np.r_[False, (np.diff(dd_) > 1) | (np.abs(op[1:] / cl[:-1] - 1) > 0.25)]
        d["seg"] = np.cumsum(brk)
        self.d1 = d
        import pyarrow.parquet as pq
        tb = pq.read_table(f"{ROOT}/data/stinkbid/m1_spot/{sym}.parquet",
                           columns=["open_time", "open", "high", "low", "close", "trades"])
        unit = tb.schema.field("open_time").type.unit
        div = {"ns": 60_000_000_000, "us": 60_000_000, "ms": 60_000, "s": 60}[unit]
        t = tb.column("open_time").cast("int64").to_numpy() // div
        o = tb.column("open").to_numpy()
        h = tb.column("high").to_numpy()
        l_ = tb.column("low").to_numpy()
        c = tb.column("close").to_numpy()
        tr = tb.column("trades").to_numpy().astype(np.int32)
        del tb
        day = t // DAY
        keep = np.ones(len(t), bool)
        if lo:
            keep &= day >= int(pd.Timestamp(lo).value // 60_000_000_000 // DAY)
        if hi:
            keep &= day <= int(pd.Timestamp(hi).value // 60_000_000_000 // DAY)
        if keep.all():
            self.t, self.o, self.h, self.l, self.c, self.tr = t, o, h, l_, c, tr
        else:
            self.t, self.o, self.h, self.l, self.c, self.tr = t[keep], o[keep], h[keep], l_[keep], c[keep], tr[keep]
        dmap = dict(zip(self.d1.day.tolist(), self.d1.seg.tolist()))
        dd = self.t // DAY
        ud, inv = np.unique(dd, return_inverse=True)
        self.seg = np.array([dmap.get(int(x), -1) for x in ud], np.int64)[inv].astype(np.int32)
        del dd, inv
        self.live = (self.tr > 0) & (self.seg >= 0)
        assert np.all(np.diff(self.t) > 0)
        u = pd.read_parquet(f"{ROOT}/data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
        q = u[(u.coin == coin) & u.U_Q1.astype(bool)]
        self.q1_months = set(q.month.astype(str).str[:7])
        self._ticks = {}

    def inputs(self, t0: int):
        """§6.1 inputs at a Monday 03:30 placement t0: d0 = Sunday; P0 = d0's close; sigma30 over d0's segment."""
        d0 = t0 // DAY - 1
        D = self.d1
        i = np.flatnonzero(D.day.to_numpy() == d0)
        if not len(i):
            return None
        i = int(i[0])
        sg = int(D.seg.iloc[i])
        P0 = float(D.close.iloc[i])
        # the 30 returns ending d0, both closes inside d0's segment (consecutive days)
        rets = []
        for j in range(i, i - 30, -1):
            if j - 1 < 0:
                break
            if int(D.seg.iloc[j]) != sg or int(D.seg.iloc[j - 1]) != sg:
                break
            if int(D.day.iloc[j]) - int(D.day.iloc[j - 1]) != 1:
                break
            rets.append(math.log(float(D.close.iloc[j]) / float(D.close.iloc[j - 1])))
        sig = float(np.std(rets, ddof=1)) if len(rets) >= 25 else float("nan")
        tk = self.tick_at_placement(t0)
        return dict(d0=d0, P0=P0, sigma30=sig, n_ret=len(rets), seg=sg, **tk)

    def tick_at_placement(self, t0: int):
        if t0 in self._ticks:
            return self._ticks[t0]
        d0 = t0 // DAY - 1
        a = np.searchsorted(self.t, (d0 - 6) * DAY)
        b = np.searchsorted(self.t, (d0 + 1) * DAY)
        sl = slice(a, b)
        tr = self.tr[sl] > 0
        px = np.concatenate([self.o[sl][tr], self.h[sl][tr], self.l[sl][tr], self.c[sl][tr]])
        d, nfiner, dmax, n = tick_from_prices(px)
        res = dict(tick_dec=d, tick_n_finer=nfiner, tick_dec_max=dmax, tick_n_px=n)
        self._ticks[t0] = res
        return res

    def first_live(self, i: int) -> int:
        """First live bar index at or after bar index i (-1 none)."""
        n = len(self.live)
        step = 4096
        while i < n:
            j = min(n, i + step)
            nz = np.flatnonzero(self.live[i:j])
            if len(nz):
                return int(i + nz[0])
            i = j
            step *= 4
        return -1


def flip_exit(cn: Coin, m: int, T: float, up: float, inclusive: bool = True):
    """§8 X-FLIP: sell live at M(m); marketable at the go-live bar's open if open >= T; else resting, filled at T in
    the first (inclusive: from the go-live bar on; else: later) live bar with high >= up before the stop bar; else
    sold at the open of the first live bar at or after M(m + 72 h). Returns (kind, bar time, price, gi, si)."""
    g = rule_m(m)
    S = rule_m(m + FLIP_H * 60)
    gi = cn.first_live(int(np.searchsorted(cn.t, g)))
    si = cn.first_live(int(np.searchsorted(cn.t, S)))
    if gi < 0:
        return ("censored", -1, float("nan"), gi, si)
    if cn.t[gi] >= S:
        return ("stop", int(cn.t[si]), float(cn.o[si]), gi, si) if si >= 0 else ("censored", -1, np.nan, gi, si)
    if cn.o[gi] >= T:
        return ("marketable", int(cn.t[gi]), float(cn.o[gi]), gi, si)
    a = gi if inclusive else gi + 1
    b = si if si >= 0 else len(cn.t)
    hh = np.where(cn.live[a:b], cn.h[a:b], -np.inf)
    hit = np.flatnonzero(hh >= up)
    if len(hit):
        j = a + int(hit[0])
        return ("target", int(cn.t[j]), float(T), gi, si)
    if si >= 0:
        return ("stop", int(cn.t[si]), float(cn.o[si]), gi, si)
    return ("censored", -1, float("nan"), gi, si)


def segs_crossed(cn: Coin, a: int, b: int) -> bool:
    if a < 0 or b < 0:
        return True
    s = cn.seg[a:b + 1]
    s = s[s >= 0]
    return len(np.unique(s)) > 1


def main():
    M = pd.read_pickle(f"{OUT}/selected.pkl")
    if len(sys.argv) > 1:
        M = M[M.coin.isin(sys.argv[1].split(","))]
    rows = []
    twin_rows = []
    for coin in M.coin.unique():
        cn = Coin(coin)
        for _, e in M[M.coin == coin].iterrows():
            fid = int(e.fill_id)
            k = float(e.rung)
            m_eng = int(e.t_F1)
            m_sample = to_min(e.time)
            out = dict(fill_id=fid, coin=coin, why=e.why, rung=k, m_sample=mts(m_sample), m_eng=mts(m_eng))
            # (a) placement
            t0 = monday_0330_before(m_sample)
            I = cn.inputs(t0)
            tau_d = I["tick_dec"]
            tau = Decimal(tick_str(tau_d))
            x = I["P0"] * math.exp(-k * I["sigma30"])
            Ld = dfloor(Decimal(x), tau)
            L = float(Ld)
            L_tau = float(Ld - tau)
            out.update(t0=mts(t0), t0_eng=mts(int(e.t0)), d0=str(datetime.fromtimestamp(I["d0"] * 86400, tz=UTC).date()),
                       P0=I["P0"], P0_eng=float(e.P0), sigma30=I["sigma30"], sigma30_eng=float(e.sigma30),
                       n_ret=I["n_ret"], tick=tick_str(tau_d), tick_eng=str(e.tick_str), tick_n_finer=I["tick_n_finer"],
                       tick_dec_max=I["tick_dec_max"], L=L, L_eng=float(e.L), month_in_q1=mts(t0)[:7] in cn.q1_months)
            # (b) F1: first live minute from t0 + 1 within the 7-day life, same segment as d0, low <= L - tau
            a = int(np.searchsorted(cn.t, t0 + 1))
            b = int(np.searchsorted(cn.t, t0 + 7 * DAY))
            ok = cn.live[a:b] & (cn.seg[a:b] == I["seg"]) & (cn.l[a:b] <= L_tau)
            hit = np.flatnonzero(ok)
            m = int(cn.t[a + hit[0]]) if len(hit) else -1
            # also: did the segment change inside the life before the fill (the bid would be cancelled)?
            segchg = np.flatnonzero((cn.seg[a:b] != I["seg"]) & (cn.seg[a:b] >= 0))
            first_other = int(cn.t[a + segchg[0]]) if len(segchg) else -1
            fi = a + hit[0] if len(hit) else -1
            out.update(m_mine=mts(m) if m >= 0 else "none", fill_match=(m == m_eng),
                       fill_bar_low=float(cn.l[fi]) if fi >= 0 else np.nan, fill_bar_open=float(cn.o[fi]) if fi >= 0 else np.nan,
                       fill_bar_high=float(cn.h[fi]) if fi >= 0 else np.nan, gap_through=bool(fi >= 0 and cn.h[fi] < L),
                       seg_change_in_life=mts(first_other) if first_other >= 0 else "")
            # (c) X-FLIP on my own numbers
            R = dceil((Decimal(repr(L)) + Decimal(repr(I["P0"]))) / 2, tau)
            Rf = float(R)
            up = float(R + tau)
            kind, et, epx, gi, si = flip_exit(cn, m, Rf, up, inclusive=True)
            kind2, et2, epx2, _, _ = flip_exit(cn, m, Rf, up, inclusive=False)
            r = epx * (1 - C) / (L * (1 + C)) - 1
            r2 = epx2 * (1 - C) / (L * (1 + C)) - 1
            out.update(R=Rf, R_eng=float(e.target), golive=mts(rule_m(m)), stop=mts(rule_m(m + FLIP_H * 60)),
                       golive_bar_open=float(cn.o[gi]), exit_kind=kind, exit_kind_eng=e.exit_kind, exit_t=mts(et),
                       exit_t_eng=mts(int(e.exit_t)), exit_px=epx, exit_px_eng=float(e.exit_px), r=r, r_eng=float(e.r_o),
                       r_sample=float(e.r), r_literal_later=r2, exit_kind_literal=kind2,
                       chain_cross=segs_crossed(cn, int(np.searchsorted(cn.t, m)), si))
            # (e) H2R: the alert buyer's open at the first live minute at or after M(m)
            ai = cn.first_live(int(np.searchsorted(cn.t, rule_m(m))))
            p_alert = float(cn.o[ai])
            a_f = p_alert * (1 + C) / (L * (1 + C)) - 1
            out.update(alert_t=mts(int(cn.t[ai])), alert_t_eng=mts(int(e.alert_t_M)), alert_open=p_alert,
                       alert_px_eng=float(e.alert_px_M), a_f=a_f, a_f_eng=float(e.alert_M), a_f_sample=float(e.y_H2R))
            # (d) twins: B-TWIN reconstructed from the seed (§10.1; uniforms -> eligible minutes)
            rng = np.random.default_rng(SEED + fid)
            u = rng.random(100)
            mon = (cn.t // DAY).astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
            qm = np.array([np.datetime64(x, "M").astype(np.int64) for x in cn.q1_months], np.int64)
            elig = cn.live & np.isin(mon, qm)
            # complete exit window: M(te + 72 h) <= END_MIN -> the largest such te (monotone)
            lo_c, hi_c = END_MIN - 80 * 60 - 4 * DAY, END_MIN
            while hi_c - lo_c > 1:
                mid = (lo_c + hi_c) // 2
                if rule_m(mid + FLIP_H * 60) <= END_MIN:
                    lo_c = mid
                else:
                    hi_c = mid
            cut = lo_c
            eb = np.flatnonzero(elig & (cn.t <= cut))
            et_ = cn.t[eb]
            left = eb[et_ < m - 182 * DAY]
            right = eb[et_ > m + 182 * DAY]
            nL, nR = len(left), len(right)
            days = len(np.unique(np.r_[cn.t[left] // DAY, cn.t[right] // DAY]))
            kk = np.minimum((u * (nL + nR)).astype(np.int64), nL + nR - 1)
            bars = np.r_[left, right][kk]            # k < nL -> left[k]; else right[k - nL]
            ratio = float(e.target) / float(e.L)           # the fill's relative target (engine's rounded R / L)
            tw_r = []
            for j, bi in enumerate(bars):
                te = int(cn.t[bi])
                ent = float(cn.o[bi])
                T = ent * ratio
                tdec = cn.tick_at_placement(monday_0330_at_or_before(te))["tick_dec"]
                tw_up = T + float(tick_str(tdec))
                kd, xt, xp, g2, s2 = flip_exit(cn, te, T, tw_up, inclusive=True)
                cross = segs_crossed(cn, int(bi), s2) or s2 < 0
                rr = xp * (1 - C) / (ent * (1 + C)) - 1 if np.isfinite(xp) else np.nan
                tw_r.append(rr)
                twin_rows.append(dict(fill_id=fid, coin=coin, j=j, entry=mts(te), entry_px=ent, target=T, kind=kd,
                                      exit=mts(xt) if xt >= 0 else "", exit_px=xp, r=rr, cross=cross))
            tw_r = np.array(tw_r)
            out.update(twin_eligible_days=days, twin_nL=nL, twin_nR=nR, twin_mean=float(np.nanmean(tw_r)),
                       twin_n=int(np.isfinite(tw_r).sum()), twin_mean_eng=float(e.twin_mean),
                       twin_n_eng=int(e.twin_n), n_cross=int(sum(t["cross"] for t in twin_rows if t["fill_id"] == fid)),
                       delta=r - float(np.nanmean(tw_r)), delta_eng=float(e.delta_o), y_sample=float(e.y))
            rows.append(out)
            print(json.dumps({k_: (v if not isinstance(v, (np.floating, np.integer, np.bool_)) else v.item())
                              for k_, v in out.items()}, default=str), flush=True)
        del cn
        gc.collect()
        import resource
        print("maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, flush=True)
    tag = sys.argv[1].replace(",", "_") if len(sys.argv) > 1 else "all"
    pd.DataFrame(rows).to_csv(f"{OUT}/recompute_{tag}.csv", index=False)
    pd.DataFrame(twin_rows).to_csv(f"{OUT}/twins_{tag}.csv", index=False)


if __name__ == "__main__":
    main()
