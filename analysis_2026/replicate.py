"""
Reproduces the indicator-replication evidence cited in HANDOFF.md section 2.

1. IWM daily and weekly: moneyline_ref.moneyline() on real OHLC vs the TradingView
   export (data/tv_stocks/IWM_1D.csv, _1W.csv). The yfinance file in the repo root is
   dividend-adjusted while TradingView shows split-adjusted, NOT dividend-adjusted
   prices, so each day's yfinance OHLC is rescaled by (TV close / yfinance close).
2. Neighbouring parameter sets and close-only input, for contrast.
3. hl2-consistency test on every close-only export: true range is recovered from the
   exported Wilder ATR(14) column, ATR(10) is rebuilt from it, and at every bar where
   the line ratchets or flips the implied hl2 = line -/+ factor*ATR10 must satisfy
   |hl2 - close| <= TR/2 and |hl2 - prev_close| <= TR (necessary conditions, since
   high - low <= TR and the low/high lie within TR of the previous close).
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline, supertrend, to_weekly  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_tv(path):
    tv = pd.read_csv(path)
    tv["date"] = pd.to_datetime(tv["time"], unit="s").dt.normalize()
    tv = tv.set_index("date")
    up = pd.to_numeric(tv["Up Trend"], errors="coerce")
    dn = pd.to_numeric(tv["Down Trend"], errors="coerce")
    return pd.DataFrame({"close": pd.to_numeric(tv["close"], errors="coerce"), "green": up.notna(),
                         "line": up.where(up.notna(), dn), "atr14": pd.to_numeric(tv["ATR"], errors="coerce")})


def iwm_ohlc():
    yf = pd.read_csv(ROOT / "IWM_historical_data.csv", skiprows=[1, 2]).rename(columns={"Price": "date"})
    yf["date"] = pd.to_datetime(yf["date"]); yf = yf.set_index("date")[["Open", "High", "Low", "Close"]].astype(float)
    tv = load_tv(ROOT / "data/tv_stocks/IWM_1D.csv")
    j = yf.join(tv[["close"]].rename(columns={"close": "tvc"}), how="inner")
    r = j.tvc / j.Close
    return pd.DataFrame({"open": j.Open * r, "high": j.High * r, "low": j.Low * r, "close": j.tvc}), tv


def compare(model, tv, warmup):
    c = pd.DataFrame({"m": model.green, "t": tv.green.reindex(model.index),
                      "ml": model.line, "tl": tv.line.reindex(model.index)}).iloc[warmup:].dropna()
    mf = c.m.astype(int).diff().fillna(0) != 0
    tf = c.t.astype(int).diff().fillna(0) != 0
    return {"bars": len(c), "state_agree_%": (c.m == c.t).mean() * 100,
            "line_med_err_%": float(((c.ml - c.tl).abs() / c.tl).median() * 100),
            "tv_flips": int(tf.sum()), "model_flips": int(mf.sum()), "same_day_flips": int((tf & mf).sum())}


def iwm_replication():
    ohlc, tv = iwm_ohlc()
    rows = [{"test": "daily, moneyline (ATR10 x2.0 hl2, reset)", **compare(moneyline(ohlc), tv, 100)}]
    for lbl, kw in (("daily, ta.supertrend(2,10)", dict(variant="pine")),
                    ("daily, ATR14 x2.0", dict(period=14)), ("daily, ATR10 x2.5", dict(factor=2.5)),
                    ("daily, ATR10 x3.0", dict(factor=3.0))):
        rows.append({"test": lbl, **compare(supertrend(ohlc, **kw), tv, 100)})
    co = pd.DataFrame({"open": ohlc.close, "high": ohlc.close, "low": ohlc.close, "close": ohlc.close})
    rows.append({"test": "daily, close-only input", **compare(moneyline(co), tv, 100)})
    tvw = load_tv(ROOT / "data/tv_stocks/IWM_1W.csv")
    wk = to_weekly(ohlc)
    wk = wk[wk.index >= "2010-07-19"]
    rows.append({"test": "weekly 2010+, moneyline", **compare(moneyline(wk), tvw, 30)})
    return pd.DataFrame(rows)


def rma(x, n):
    out = np.full(len(x), np.nan)
    start = np.argmax(~np.isnan(x))
    if len(x) - start < n:
        return out
    out[start + n - 1] = np.nanmean(x[start:start + n])
    for i in range(start + n, len(x)):
        out[i] = out[i - 1] + (x[i] - out[i - 1]) / n
    return out


def hl2_consistency(path, period=10, factor=2.0, warmup=100):
    d = load_tv(path).dropna(subset=["atr14"])
    a14 = d.atr14.to_numpy(float); c = d.close.to_numpy(float)
    line = d.line.to_numpy(float); g = d.green.to_numpy(bool)
    tr = np.r_[np.nan, 14 * a14[1:] - 13 * a14[:-1]]
    atr = rma(tr, period)
    ok = tot = 0
    for t in range(max(warmup, 2), len(c)):
        if np.isnan(atr[t]) or np.isnan(line[t]) or np.isnan(line[t - 1]):
            continue
        flip = g[t] != g[t - 1]
        step = (g[t] and line[t] > line[t - 1] + 1e-9) or (not g[t] and line[t] < line[t - 1] - 1e-9)
        if not (flip or step):
            continue
        hl2 = line[t] + factor * atr[t] if g[t] else line[t] - factor * atr[t]
        tol = 1e-4 * c[t]
        tot += 1
        ok += abs(hl2 - c[t]) <= tr[t] / 2 + tol and abs(hl2 - c[t - 1]) <= tr[t] + tol
    return ok, tot


def consistency_all():
    rows = []
    files = sorted(glob.glob(str(ROOT / "data/tv_full/*.csv")) + glob.glob(str(ROOT / "data/tv_stocks/*.csv")))
    for f in files:
        name = Path(f).stem
        r = {"series": name}
        for p, k in ((10, 2.0), (14, 2.0), (10, 2.5), (10, 3.0), (7, 2.0), (20, 2.0)):
            ok, tot = hl2_consistency(f, p, k)
            r[f"{p}x{k}"] = 100 * ok / tot if tot else np.nan
        r["bars_tested"] = hl2_consistency(f)[1]
        rows.append(r)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    print("=== IWM replication (TradingView export vs moneyline_ref on rescaled OHLC) ===")
    print(iwm_replication().to_string(index=False, float_format=lambda x: f"{x:,.4f}"))
    print("\n=== hl2-consistency on every export (% of ratchet/flip bars consistent) ===")
    print(consistency_all().to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
