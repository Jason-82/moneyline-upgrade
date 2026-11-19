"""(c) Swaps: positions of P1 U-Q1 fills whose exit falls after the predecessor's last trade continue in the successor
at the frozen ratio (§4.1, A1.1/A2.1): exit_px = successor's open at exit_t x units (stop exits). Fill minutes lie
inside the bid's life (no fill before placement + 1 or after the life). Lineage months lost between a predecessor's
last U-Q1 month and its successor's first U-Q1 month (coverage, for the caveats)."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/moneyline-upgrade")
from analysis_2026 import stinkbid_data as sbd

R = "data/stinkbid/runs/outcomes/P1__U_Q1"


def main():
    F = pd.read_parquet(f"{R}/fills.parquet", columns=["fill_id", "coin", "t_F1", "live_from", "life_end", "L", "t0"])
    F = F[F.t_F1 >= 0]
    print("fill minute inside [live_from, life_end):", bool(((F.t_F1 >= F.live_from) & (F.t_F1 < F.life_end)).all()),
          "| min minutes after placement:", int((F.t_F1 - F.t0).min()))
    O = pd.read_parquet(f"{R}/outcomes.parquet", columns=["rule", "exit", "cost", "fill_id", "coin", "exit_kind",
                                                          "exit_t", "exit_px", "r"])
    O = O[(O.rule == "F1") & (O.cost == "C-RH")]
    seg = pd.read_csv("data/stinkbid/ref/segments.csv")
    rows = []
    for pred in ["BTT", "EOS", "FTM", "MATIC", "RNDR"]:
        succ, units, _ = sbd.SWAPS[pred]
        s = seg[(seg.coin == pred) & (seg.kind == "swap")].iloc[0]
        t_end = int(pd.Timestamp(s.last_trade_time).value // 60_000_000_000) + 1
        o = O[(O.coin == pred) & (O.exit_t >= t_end) & (O.exit_kind == "stop")]
        if not len(o):
            rows.append(dict(pred=pred, succ=succ, units=units, n=0))
            continue
        sym = sbd.coin_sym(succ)[0]
        ts = pd.to_datetime(o.exit_t.to_numpy() * 60, unit="s", utc=True)
        k = pd.read_parquet(f"data/stinkbid/m1_spot/{sym}.parquet", columns=["open_time", "open", "trades"],
                            filters=[("open_time", "in", list(ts))])
        k["t"] = np.asarray((k.open_time - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1min"))
        m = o.merge(k[["t", "open", "trades"]], left_on="exit_t", right_on="t", how="left")
        dev = (m.exit_px / (m.open * units) - 1).abs()
        rows.append(dict(pred=pred, succ=succ, units=units, n=len(m), exits=m.exit.value_counts().to_dict(),
                         max_rel_dev=float(dev.max()), all_live=bool((m.trades > 0).all())))
    print(pd.DataFrame(rows).to_string())
    # lineage months lost around swaps (successor's U-B membership needs its own 90-day window: coding choice 2)
    u = pd.read_parquet("data/stinkbid/ref/universes.parquet", columns=["month", "coin", "U_Q1"])
    q = u[u.U_Q1]
    out = []
    for pred, (succ, units, _) in sbd.SWAPS.items():
        a, b = q[q.coin == pred], q[q.coin == succ]
        if len(a) and len(b):
            la, fb = a.month.max(), b.month[b.month > a.month.max()].min()
            gap = (int(fb[:4]) * 12 + int(fb[5:7])) - (int(la[:4]) * 12 + int(la[5:7])) - 1 if isinstance(fb, str) else None
            s = seg[(seg.coin == pred) & (seg.kind == "swap")]
            out.append(dict(pred=pred, last_pred_Q1=la, swap_day=str(s.last_day.iloc[0]) if len(s) else "",
                            first_succ_Q1_after=fb, months_without=gap))
    print(pd.DataFrame(out).to_string())


if __name__ == "__main__":
    main()


def vwap_check():
    """Delisting values: VWAP (quote volume / volume) of the last full trading day from the daily klines."""
    seg = pd.read_csv("data/stinkbid/ref/segments.csv")
    for coin in ["XMR", "WAVES", "LUNA", "OMG", "REN", "NULS", "ICX", "FTT", "SRM"]:
        s = seg[(seg.coin == coin) & (seg.kind.isin(["delisting", "gap"]))].iloc[0]
        sym = sbd.coin_sym(coin)[0]
        d = pd.read_parquet("data/stinkbid/d1_full_all.parquet", columns=["sym", "open_time", "volume", "quote_volume"],
                            filters=[("sym", "==", sym)])
        d["day"] = d.open_time.dt.tz_convert(None).dt.normalize()
        r = d[d.day == pd.Timestamp(s.last_full_day)]
        v = float(r.quote_volume.iloc[0] / r.volume.iloc[0])
        print(f"{coin:6s} last full day {s.last_full_day}  VWAP from klines {v:.6g}  segments.csv {s.vwap_last_full_day:.6g}"
              f"  x0.70 = {0.7 * v:.6g}  last trade {s.last_trade_time}")


if __name__ == "__main__":
    vwap_check()
