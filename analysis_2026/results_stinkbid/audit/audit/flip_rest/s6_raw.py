"""Raw-bar check of every P1/U-Q1 F1 fill (auditor's own code from prereg §7, §8, §10.1):
 - fill minute: first minute >= live_from (< life_end) with trades > 0 and low <= L - tau (F1)
 - rule M: t + 60 if New York clock 07:00-22:59, else next 07:00 New York
 - B-ALERT: open of the first traded minute >= M(fill)  ->  a_f = open / L - 1
 - X-FLIP: sell live at the first traded minute >= M(fill); marketable at its open if open >= R1/2; else the first
   traded minute (from go-live, inclusive [engine reading] / exclusive [strict reading]) before the stop with
   high >= R1/2 + tau fills at R1/2; else market sell at the open of the first traded minute >= M(fill + 72 h).
Reads one coin's 1m bars at a time (columns and rows filtered)."""
import resource
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from analysis_2026 import stinkbid_data as sbd   # data loader helpers only (symbol map)

D = "/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/audit/flip_rest"
RUN = "data/stinkbid/runs/outcomes/P1__U_Q1"
NY = "America/New_York"


def rule_m_min(tmin):
    """tmin: int64 minutes since epoch (UTC) -> rule-M minute."""
    ts = pd.to_datetime(np.asarray(tmin, np.int64) * 60_000_000_000, utc=True)
    loc = ts.tz_convert(NY)
    mins = loc.hour * 60 + loc.minute
    day = loc.tz_localize(None).normalize()
    nxt_day = np.where(mins < 420, day, day + pd.Timedelta("1D"))
    nxt = (pd.DatetimeIndex(nxt_day) + pd.Timedelta("7h")).tz_localize(NY).tz_convert("UTC")
    plus = ts + pd.Timedelta("60min")
    out = np.where((mins >= 420) & (mins <= 1379), plus.as_unit("ns").asi8, nxt.as_unit("ns").asi8)
    return out // 60_000_000_000


F = pd.read_parquet(f"{RUN}/fills.parquet", columns=["fill_id", "coin", "lineage", "live_from", "life_end", "L", "tick",
                                                      "P0", "t_F1", "i_F1"])
F = F[F.t_F1 >= 0].reset_index(drop=True)
O = pd.read_parquet(f"{RUN}/outcomes.parquet", columns=["exit", "fill_id", "exit_kind", "exit_t", "exit_px", "target",
                                                         "complete", "horizon_t"],
                    filters=[("rule", "==", "F1"), ("exit", "in", ["FLIP", "FLIP_bot"]), ("cost", "==", "C-RH")])
Bn = pd.read_parquet(f"{RUN}/bench.parquet", columns=["fill_id", "alert_t_M", "alert_px_M", "alert_M"],
                     filters=[("rule", "==", "F1")])
F = F.merge(Bn, on="fill_id", how="left")
OF = O[O.exit == "FLIP"].set_index("fill_id")
OB = O[O.exit == "FLIP_bot"].set_index("fill_id")

rows = []
for coin, g in F.groupby("coin"):
    sym = sbd.coin_sym(coin)[0]
    lo_t = pd.Timestamp(int(g.live_from.min()) * 60, unit="s", tz="UTC") - pd.Timedelta("1D")
    hi_t = pd.Timestamp(int(g.t_F1.max()) * 60, unit="s", tz="UTC") + pd.Timedelta("10D")
    try:
        k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet", columns=["open_time", "open", "high", "low", "trades"],
                            filters=[("open_time", ">=", lo_t), ("open_time", "<", hi_t)])
    except FileNotFoundError:
        for _, f in g.iterrows():
            rows.append(dict(fill_id=f.fill_id, coin=coin, note="no m1 file"))
        continue
    t = (k.open_time.astype("int64").to_numpy() // 60_000_000_000) if k.open_time.dtype.kind == "M" else None
    if t is None:
        t = k.open_time.dt.tz_convert("UTC").astype("int64").to_numpy() // 60_000_000_000
    o, h, lw, tr = (k[c].to_numpy() for c in ("open", "high", "low", "trades"))
    live = tr > 0
    tl, ol, hlv, lwl = t[live], o[live], h[live], lw[live]
    del k
    for _, f in g.iterrows():
        rec = dict(fill_id=int(f.fill_id), coin=coin, lineage=f.lineage)
        L, tau = float(f.L), float(f.tick)
        # fill minute
        a = np.searchsorted(tl, f.live_from)
        b = np.searchsorted(tl, f.life_end)
        hit = np.nonzero(lwl[a:b] <= L - tau + 1e-9 * L)[0]
        rec["fill_mine"] = int(tl[a + hit[0]]) if len(hit) else -1
        rec["fill_file"] = int(f.t_F1)
        tf = int(f.t_F1)
        A = int(rule_m_min([tf])[0])
        gi = np.searchsorted(tl, A)
        rec["M"] = A
        if gi >= len(tl):
            rec["note"] = "no live bar after M in window"
            rows.append(rec)
            continue
        rec["alert_t_mine"], rec["alert_px_mine"] = int(tl[gi]), float(ol[gi])
        rec["alert_t_file"], rec["alert_px_file"] = int(f.alert_t_M), float(f.alert_px_M)
        # X-FLIP
        if f.fill_id in OF.index:
            of = OF.loc[f.fill_id]
            T = float(of.target)
            S = int(rule_m_min([tf + 72 * 60])[0])
            si = np.searchsorted(tl, S)
            stop_t = int(tl[si]) if si < len(tl) else -1
            stop_px = float(ol[si]) if si < len(tl) else np.nan
            if ol[gi] >= T:
                kind, et, px = "marketable", int(tl[gi]), float(ol[gi])
                kind_s = kind
            else:
                up = T + tau - 1e-9 * T
                hh = np.nonzero(hlv[gi:si] >= up)[0]
                if len(hh):
                    kind, et, px = "target", int(tl[gi + hh[0]]), T
                else:
                    kind, et, px = "stop", stop_t, stop_px
                # strict reading: target only from the minute after go-live
                hh2 = np.nonzero(hlv[gi + 1:si] >= up)[0]
                kind_s = "target" if len(hh2) else "stop"
                rec["px_strict"] = T if len(hh2) else stop_px
            rec.update(flip_kind_mine=kind, flip_t_mine=et, flip_px_mine=px, flip_kind_file=of.exit_kind,
                       flip_t_file=int(of.exit_t), flip_px_file=float(of.exit_px), flip_kind_strict=kind_s,
                       complete=bool(of.complete), stop_t_mine=stop_t)
            if "px_strict" not in rec:
                rec["px_strict"] = px
        # X-FLIP-bot (sell live 1 minute after the fill); two readings of its time stop
        if f.fill_id in OB.index:
            ob = OB.loc[f.fill_id]
            T = float(ob.target)
            gb = np.searchsorted(tl, tf + 1)
            res = {}
            for lab, S in (("stopM", int(rule_m_min([tf + 72 * 60])[0])), ("stop72", tf + 72 * 60)):
                si = np.searchsorted(tl, S)
                if gb < len(tl) and ol[gb] >= T:
                    res[lab] = ("marketable", int(tl[gb]), float(ol[gb]))
                    continue
                hh = np.nonzero(hlv[gb:si] >= T + tau - 1e-9 * T)[0]
                if len(hh):
                    res[lab] = ("target", int(tl[gb + hh[0]]), T)
                else:
                    res[lab] = ("stop", int(tl[si]) if si < len(tl) else -1, float(ol[si]) if si < len(tl) else np.nan)
            rec.update(bot_file=(ob.exit_kind, int(ob.exit_t), float(ob.exit_px)), bot_M=res["stopM"], bot_72=res["stop72"])
        rows.append(rec)
    del t, o, h, lw, tr, tl, ol, hlv, lwl
R = pd.DataFrame(rows)
R.to_pickle(f"{D}/raw_check.pkl")
print("fills checked:", len(R), " coins:", R.coin.nunique(), " maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
if "note" in R:
    print("notes:", R.note.value_counts(dropna=True).to_dict())
ok_fill = R.fill_mine == R.fill_file
print("fill minute matches:", int(ok_fill.sum()), "of", len(R))
ok_alert = (R.alert_t_mine == R.alert_t_file) & (np.abs(R.alert_px_mine / R.alert_px_file - 1) < 1e-9)
print("alert (t, px) matches:", int(ok_alert.sum()), "of", int(R.alert_t_file.notna().sum()))
c = R[R.flip_kind_file.notna()]
ok_flip = (c.flip_kind_mine == c.flip_kind_file) & (c.flip_t_mine == c.flip_t_file) & (np.abs(c.flip_px_mine / c.flip_px_file - 1) < 1e-9)
print("FLIP (kind, t, px) matches:", int(ok_flip.sum()), "of", len(c), "; complete rows:", int(c.complete.sum()),
      "; complete-row matches:", int((ok_flip & c.complete).sum()))
print("FLIP strict-reading kind differs from engine reading:", int((c.flip_kind_strict != c.flip_kind_mine).sum()))
bb = R[R.bot_file.notna()]
mM = sum(1 for _, x in bb.iterrows() if x.bot_file[0] == x.bot_M[0] and x.bot_file[1] == x.bot_M[1] and abs(x.bot_file[2] / x.bot_M[2] - 1) < 1e-9)
m72 = sum(1 for _, x in bb.iterrows() if x.bot_file[0] == x.bot_72[0] and x.bot_file[1] == x.bot_72[1] and abs(x.bot_file[2] / x.bot_72[2] - 1) < 1e-9)
print(f"bot matches with stop at M(fill+72h): {mM} of {len(bb)}; with stop at fill+72h: {m72}")
print("\nMISMATCHES (fill / alert / flip):")
bad = R[~ok_fill | ~ok_alert | (R.flip_kind_file.notna() & ~((R.flip_kind_mine == R.flip_kind_file) & (R.flip_t_mine == R.flip_t_file)))]
cols = [c_ for c_ in ["fill_id", "coin", "lineage", "fill_mine", "fill_file", "alert_t_mine", "alert_t_file", "alert_px_mine",
                      "alert_px_file", "flip_kind_mine", "flip_kind_file", "flip_t_mine", "flip_t_file", "flip_px_mine",
                      "flip_px_file", "complete"] if c_ in bad]
pd.set_option("display.width", 250)
print(bad[cols].to_string())
