"""
Mean reversion across investment styles and sectors: overweight what has lagged for
years (e.g. small-cap value), underweight what has led (e.g. large-cap growth).

The finance literature says the horizon decides the sign. Over 3-5 years past losers
have tended to beat past winners (De Bondt & Thaler 1985; the Fama-French long-term
reversal factor uses months t-60..t-13). Over 3-12 months winners have kept winning
(industry momentum, Moskowitz & Grinblatt 1999). Rebalancing to equal weights is
itself a mild contrarian strategy, so a contrarian rule has to beat THAT benchmark,
not just the market.

Data (data/ff/, gitignored):
  FF 1949-01..2017-03 (Ken French data bundled in the linearmodels package): 9 size x
    value portfolios (S1/S3/S5 = small/mid/big size quintiles, V1/V3/V5 = growth /
    neutral / value book-to-market quintiles), 12 industries, the market and T-bills.
  iShares style ETFs (IWN IWO IWS IWP IWD IWF = small/mid/large value/growth) and the
    9 Select Sector SPDRs, 2000..2021-08 (qlib, while it is total return).
  Vanguard Russell style ETFs (VTWV VTWG VONV VONG = small/large value/growth) and the
    9 Invesco S&P SmallCap sector ETFs (PSC*), 2010..2026-09 (github.com/o-bensalah,
    adjusted close).

Rules (no look-ahead: signals use returns up to the rebalance month-end; positions are
held from the next month; weights drift between rebalances; 0.10% per side on
turnover):
  EW        equal weight in every asset, rebalanced on the same dates (benchmark)
  REV a-b   long-only contrarian: equal weight in the bottom third by cumulative return
            over months t-b+1..t-a (a = months skipped); a=12, b=60 is the FF convention
  WIN a-b   the top third instead (the mirror image)
  TILT a-b  gentle tilt: w_i = (1 - k z_i) / N, where z is the cross-sectional z-score
            of the log cumulative return; clipped at 0, k = 0.5
  MOM       top third by months t-11..t-1 (12-1 momentum), the opposite bet
  PAIR      small value vs large growth only: weight in small value = 0.5 - 0.25 *
            clip(z, -2, 2), where z is the trailing 60-month log relative return
            (small value minus large growth) standardised against its own past
            (>= 120 months); benchmark = static 50/50

Pre-registered hypotheses (written 2026-10-14, before any run):
  R1 FF style 9, annual (December) rebalance: REV 12-60 beats EW by >= 1.0%/yr
     (mean of monthly active returns, annualised) with Newey-West t >= 2, 1955-2017.
  R2 The same for FF 12 industries.
  R3 PAIR beats the static 50/50 small value / large growth mix with t >= 2, 1959-2017.
  Out-of-sample checks with the same primary rule on the ETF sets (2001/2006-2021,
  2016-2026), and a robustness grid over formation windows, rebalance frequency, tilt
  strength and momentum. The grid is exploratory: with ~100 variants, a few will
  look significant by chance.

    python -m analysis_2026.style_rotation
    python -m analysis_2026.style_rotation --extension

EXTENSION (pre-registered 2026-10-14, after the first run, before any run on these data):
Full Ken French history found on GitHub mirrors: 25 size x book-to-market portfolios
with monthly value-weighted book-to-market, 1926-07..2026-06 (202606 vintage); 10
industries to 2026-07; 49 industries to 2026-08; FF3 factors. Plus Johnbrick123 ETFs
with dividends to 2026-09 (Russell IWN IWO IWD IWF, S&P IJS IJT IVE IVW, sector SPDRs).
  E1 Out-of-sample replication, rules unchanged: R1 (the 9 corners of the 25), R3 (SMALL
     HiBM / BIG LoBM) and R2's rule on 10 and 49 industries, over the periods the first
     run never saw: 1932-1948 and 2017-2026. Report each period; the first run's
     verdicts stand.
  E2 Full-history results 1932-2026 for the 9 corners, all 25, 10 and 49 industries.
  E3 NEW hypothesis - valuation-spread timing (the theory-backed form of the idea):
     each December, the value spread = ln(BE/ME small value) - ln(BE/ME large growth),
     price-updated to that December; z against its own past Decembers (>= 20); weight
     in small value = 0.5 + 0.25 * clip(z, -2, 2) (cheap small value -> more), the rest
     in large growth; benchmark static 50/50. Pass: active return > 0 with NW t >= 2,
     1947-2026. Exploratory: the same cheapness tilt across all 25 portfolios, each
     against its own valuation history, vs equal weight.
  ETF sets 2006-2026 with the primary rule and the pair rule, out-of-sample.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ff"
OUT = ROOT / "analysis_2026" / "results_style"
COST = 0.001
STYLE9 = ["S1V1", "S1V3", "S1V5", "S3V1", "S3V3", "S3V5", "S5V1", "S5V3", "S5V5"]
IND12 = ["NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq", "Telcm", "Utils", "Shops", "Hlth", "Money", "Other"]
ISHARES6 = ["IWN", "IWO", "IWS", "IWP", "IWD", "IWF"]
SPDR9 = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
VANG4 = ["VTWV", "VTWG", "VONV", "VONG"]
PSC9 = ["PSCC", "PSCD", "PSCE", "PSCF", "PSCH", "PSCI", "PSCM", "PSCT", "PSCU"]


# ------------------------------------------------------------------ data

def load_ff():
    d = pd.read_csv(DATA / "linearmodels_french_monthly.csv", parse_dates=["dates"]).set_index("dates")
    rf = d.RF
    mkt = d.MktRF + d.RF
    return d, rf, mkt


def load_etf_sets():
    q = pd.read_csv(DATA / "qlib_etf_month_end_close.csv", parse_dates=[0], index_col=0).loc[:"2021-08-31"]
    o = pd.read_csv(DATA / "obensalah_etf_month_end_adjclose.csv", parse_dates=[0], index_col=0).loc[:"2026-09-30"]
    rq = q.pct_change(fill_method=None)
    ro = o.pct_change(fill_method=None)
    return rq, ro


def rf_monthly(index):
    from screener.strictness import TBILL  # approximate annual 3-month T-bill, %
    return pd.Series([TBILL.get(d.year, 2.0) / 100 / 12 for d in index], index=index)


# ------------------------------------------------------------------ engine

def cumret(R, pos, a, b):
    """Cumulative return over months pos-b+1 .. pos-a (inclusive) for assets with a
    complete window and a return in month pos; None if fewer than 3 such assets."""
    lo, hi = pos - b + 1, pos - a
    if lo < 0 or hi < lo:
        return None
    w = R.iloc[lo:hi + 1]
    ok = w.notna().all() & R.iloc[pos].notna()
    if ok.sum() < 3 and not (R.shape[1] == 2 and ok.all()):
        return None
    c = pd.Series(np.nan, index=R.columns)
    c[ok] = (1 + w.loc[:, ok]).prod() - 1
    return c


def target(rule, R, pos, params):
    n = R.shape[1]
    if rule == "EW":
        ok = R.iloc[pos].notna().to_numpy()
        return ok / ok.sum() if ok.sum() else None
    if rule in ("REV", "WIN", "TILT", "MOM"):
        a, b = (1, 12) if rule == "MOM" else (params["a"], params["b"])
        c = cumret(R, pos, a, b)
        if c is None:
            return None
        ok = c.notna().to_numpy(); cv = c.to_numpy()
        idx = np.where(ok)[0]
        w = np.zeros(n)
        if rule == "TILT":
            z = np.log1p(cv[idx]); z = (z - z.mean()) / (z.std() if z.std() > 0 else 1)
            ww = np.clip(1 - params.get("k", 0.5) * z, 0, None)
            w[idx] = ww / ww.sum()
            return w
        k = max(1, int(round(len(idx) * params.get("q", 1 / 3))))
        order = idx[np.argsort(cv[idx])]
        pick = order[-k:] if rule in ("WIN", "MOM") else order[:k]
        w[pick] = 1 / k
        return w
    raise ValueError(rule)


def backtest(R, rule, params=None, rebalance="annual", start=None, cost=COST):
    """Monthly returns of a rule. Rebalance at month-ends (December for annual, quarter
    ends for quarterly); the first rebalance is the first date with a valid signal on
    or after `start` (formation month-end)."""
    params = params or {}
    idx = R.index
    rebal = (idx.month == 12) if rebalance == "annual" else (idx.month % 3 == 0)
    w = None; out = []; dates = []; turnover = 0.0; n_reb = 0
    for pos in range(len(idx)):
        if w is not None:
            r = R.iloc[pos].to_numpy()
            if np.isnan(r).any():
                r = np.nan_to_num(r)
            pr = float(w @ r)
            out.append(pr); dates.append(idx[pos])
            w = w * (1 + r) / (1 + pr)
        if rebal[pos] and (start is None or idx[pos] >= pd.Timestamp(start)):
            t = target(rule, R, pos, params)
            if t is not None:
                if w is None:
                    tc = cost * np.abs(t).sum()
                else:
                    tc = cost * np.abs(t - w).sum(); turnover += np.abs(t - w).sum() / 2; n_reb += 1
                w = t
                if out:
                    out[-1] -= tc
    s = pd.Series(out, index=dates)
    s.attrs["turnover_per_year"] = turnover / max(len(s) / 12, 1e-9)
    return s


def pair_backtest(R, scv, lcg, start=None, cost=COST, rebalance="annual"):
    """Small value vs large growth, tilted against the trailing 60-month relative
    performance (z-score vs its own history, >= 120 months)."""
    rel = np.log1p(R[scv]) - np.log1p(R[lcg])
    roll = rel.rolling(60).sum()
    idx = R.index
    rebal = (idx.month == 12) if rebalance == "annual" else (idx.month % 3 == 0)
    w = None; out = []; dates = []
    for pos in range(len(idx)):
        if w is not None:
            r = R.iloc[pos][[scv, lcg]].to_numpy()
            pr = float(w @ r); out.append(pr); dates.append(idx[pos])
            w = w * (1 + r) / (1 + pr)
        if rebal[pos] and (start is None or idx[pos] >= pd.Timestamp(start)):
            hist = roll.iloc[:pos + 1].dropna()
            if len(hist) >= 120:
                z = (hist.iloc[-1] - hist.mean()) / hist.std()
                ws = 0.5 - 0.25 * float(np.clip(z, -2, 2))
                t = np.array([ws, 1 - ws])
                tc = cost * (np.abs(t).sum() if w is None else np.abs(t - w).sum())
                w = t
                if out:
                    out[-1] -= tc
    return pd.Series(out, index=dates)


# ------------------------------------------------------------------ statistics

def nw_t(x, lags=12):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    n = len(x)
    if n < 24:
        return np.nan
    u = x - x.mean()
    s = u @ u / n
    for l in range(1, lags + 1):
        s += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    return x.mean() / np.sqrt(s / n)


def perf(r, rf):
    r = r.dropna()
    rf = rf.reindex(r.index).fillna(0)
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    ex = r - rf
    return {"CAGR_%": (eq.iloc[-1] ** (1 / yrs) - 1) * 100, "vol_%": r.std() * np.sqrt(12) * 100,
            "Sharpe": ex.mean() / ex.std() * np.sqrt(12), "maxDD_%": (eq / eq.cummax() - 1).min() * 100}


def compare(r, bench, rf):
    j = pd.concat([r, bench], axis=1, sort=True).dropna()
    a = j.iloc[:, 0] - j.iloc[:, 1]
    p, pb = perf(j.iloc[:, 0], rf), perf(j.iloc[:, 1], rf)
    roll = []
    if len(j) >= 120:
        lr = np.log1p(j)
        d = (lr.iloc[:, 0] - lr.iloc[:, 1]).rolling(120).sum().dropna()
        roll = d
    return {"months": len(j), "CAGR_%": p["CAGR_%"], "bench_CAGR_%": pb["CAGR_%"],
            "CAGR_diff": p["CAGR_%"] - pb["CAGR_%"], "active_mean_%/yr": a.mean() * 1200,
            "tracking_err_%": a.std() * np.sqrt(12) * 100,
            "IR": a.mean() / a.std() * np.sqrt(12) if a.std() > 0 else np.nan, "NW_t": nw_t(a),
            "Sharpe": p["Sharpe"], "bench_Sharpe": pb["Sharpe"], "maxDD_%": p["maxDD_%"], "bench_maxDD_%": pb["maxDD_%"],
            "win_10y_%": (roll > 0).mean() * 100 if len(roll) else np.nan,
            "turnover/yr": r.attrs.get("turnover_per_year", np.nan)}


# ------------------------------------------------------------------ study

def primary_and_grid(name, R, rf, start, extra_pair=None, mkt=None):
    rows = []
    ew = backtest(R, "EW", start=start)
    prim = backtest(R, "REV", {"a": 12, "b": 60}, start=start)
    rows.append({"set": name, "rule": "REV 12-60 (PRIMARY)", "rebal": "annual", **compare(prim, ew, rf)})
    grid = []
    for a, b in [(0, 12), (0, 36), (0, 60), (12, 36), (12, 60), (24, 60), (0, 24)]:
        for rule in ("REV", "WIN", "TILT"):
            for reb in ("annual", "quarterly"):
                if (rule, a, b, reb) == ("REV", 12, 60, "annual"):
                    continue
                ew_r = ew if reb == "annual" else backtest(R, "EW", rebalance="quarterly", start=start)
                s = backtest(R, rule, {"a": a, "b": b}, rebalance=reb, start=start)
                grid.append({"set": name, "rule": f"{rule} {a}-{b}", "rebal": reb, **compare(s, ew_r, rf)})
    for reb in ("annual", "quarterly"):
        ew_r = ew if reb == "annual" else backtest(R, "EW", rebalance="quarterly", start=start)
        grid.append({"set": name, "rule": "MOM 1-12", "rebal": reb, **compare(backtest(R, "MOM", rebalance=reb, start=start), ew_r, rf)})
    if mkt is not None:
        rows.append({"set": name, "rule": "EW vs market", "rebal": "annual", **compare(ew, mkt, rf)})
        rows.append({"set": name, "rule": "REV 12-60 vs market", "rebal": "annual", **compare(prim, mkt, rf)})
    if extra_pair:
        scv, lcg = extra_pair
        pr = pair_backtest(R, scv, lcg, start=start)
        static = backtest(R[[scv, lcg]], "EW", start=pr.index[0] - pd.offsets.MonthEnd(1)).reindex(pr.index)
        rows.append({"set": name, "rule": f"PAIR {scv}/{lcg} (z-tilt)", "rebal": "annual", **compare(pr, static, rf)})
        # simple switch: all-in on whichever lagged over the last 5 years
        sw = backtest(R[[scv, lcg]], "REV", {"a": 0, "b": 60, "q": 0.5}, start=start)
        rows.append({"set": name, "rule": f"PAIR {scv}/{lcg} (switch to 5y loser)", "rebal": "annual",
                     **compare(sw, backtest(R[[scv, lcg]], "EW", start=start), rf)})
    return pd.DataFrame(rows), pd.DataFrame(grid)


def subperiods(R, rf, start, periods):
    ew = backtest(R, "EW", start=start)
    prim = backtest(R, "REV", {"a": 12, "b": 60}, start=start)
    rows = []
    for a, b in periods:
        rows.append({"period": f"{a[:4]}-{b[:4]}", **compare(prim.loc[a:b], ew.loc[a:b], rf)})
    return pd.DataFrame(rows)


CORNERS = {"S1V1": "SMALL LoBM", "S1V3": "ME1 BM3", "S1V5": "SMALL HiBM", "S3V1": "ME3 BM1", "S3V3": "ME3 BM3",
           "S3V5": "ME3 BM5", "S5V1": "BIG LoBM", "S5V3": "ME5 BM3", "S5V5": "BIG HiBM"}


def french_sections(text):
    """Split a Ken French CSV into {section title: DataFrame indexed by YYYYMM/YYYY}."""
    import re
    out = {}; title = None; header = None; rows = []

    def flush():
        if title and header and rows:
            out.setdefault(title, pd.DataFrame(rows, columns=["key"] + header).set_index("key"))
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith(","):
            flush(); header = [h.strip() for h in s.split(",")[1:] if h.strip()]; rows = []
            continue
        tok = s.split(",")[0].strip()
        if re.fullmatch(r"\d{4}(\d{2})?", tok) and header:
            vals = [v.strip() for v in s.split(",")[1:]][:len(header)]
            rows.append([tok] + [float(v) if v else np.nan for v in vals])
        else:
            if rows:
                flush(); rows = []; header = None
            title = s
    flush()
    return out


def load_ff_full():
    rd = lambda f: pd.read_csv(DATA / f, parse_dates=[0], index_col=0)
    return {"vw25": rd("ff25_vw_monthly.csv"), "bm25": rd("ff25_bm_monthly.csv"), "ind10": rd("ind10_vw_monthly.csv"),
            "ind49": rd("ind49_vw_monthly.csv"), "ff3": rd("ff3_monthly.csv")}


def price_updated_bm(vw, bm):
    """Book-to-market at each month-end, updated for price moves since the December
    whose price the reported value uses (FF BE/ME for June t..June t+1 uses ME of Dec t-1)."""
    out = pd.DataFrame(index=bm.index, columns=bm.columns, dtype=float)
    lr = np.log1p(vw)
    for d in bm.index:
        ref_year = d.year - 1 if d.month >= 7 else d.year - 2      # formation June t -> ME(Dec t-1)
        ref = pd.Timestamp(f"{ref_year}-12-31")
        since = lr.loc[(lr.index > ref) & (lr.index <= d)]
        out.loc[d] = np.log(bm.loc[d]) - since.sum()
    return out


def valuation_pair(vw, lbm, scv="SMALL HiBM", lcg="BIG LoBM", cost=COST, min_obs=20):
    spread = (lbm[scv] - lbm[lcg])
    idx = vw.index
    w = None; out = []; dates = []; zs = []
    for pos in range(len(idx)):
        if w is not None:
            r = vw.iloc[pos][[scv, lcg]].to_numpy()
            pr = float(w @ r); out.append(pr); dates.append(idx[pos])
            w = w * (1 + r) / (1 + pr)
        if idx[pos].month == 12:
            hist = spread.loc[(spread.index <= idx[pos]) & (spread.index.month == 12)].dropna()
            if len(hist) >= min_obs:
                z = (hist.iloc[-1] - hist.mean()) / hist.std()
                ws = 0.5 + 0.25 * float(np.clip(z, -2, 2)); zs.append((idx[pos], z, ws))
                t = np.array([ws, 1 - ws])
                tc = cost * (np.abs(t).sum() if w is None else np.abs(t - w).sum())
                w = t
                if out:
                    out[-1] -= tc
    s = pd.Series(out, index=dates)
    s.attrs["z"] = pd.DataFrame(zs, columns=["date", "z", "w_small_value"]).set_index("date")
    return s


def valuation_tilt25(vw, lbm, cost=COST, min_obs=20, k=0.5):
    """Each December, tilt the 25 portfolios toward those cheap vs their OWN valuation history."""
    idx = vw.index; w = None; out = []; dates = []
    dec = lbm[lbm.index.month == 12]
    for pos in range(len(idx)):
        if w is not None:
            r = vw.iloc[pos].to_numpy(); r = np.nan_to_num(r)
            pr = float(w @ r); out.append(pr); dates.append(idx[pos]); w = w * (1 + r) / (1 + pr)
        if idx[pos].month == 12:
            h = dec.loc[:idx[pos]]
            if len(h) >= min_obs:
                z = ((h.iloc[-1] - h.mean()) / h.std()).to_numpy()
                t = np.clip(1 + k * np.nan_to_num(z), 0, None); t = t / t.sum()
                tc = cost * (np.abs(t).sum() if w is None else np.abs(t - w).sum()); w = t
                if out:
                    out[-1] -= tc
    return pd.Series(out, index=dates)


def extension_main():
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    OUT.mkdir(exist_ok=True)
    f = load_ff_full()
    vw25, ind10, ind49, ff3 = f["vw25"], f["ind10"], f["ind49"], f["ff3"]
    rf, mkt = ff3["RF"], ff3["Mkt-RF"] + ff3["RF"]
    corners = vw25[list(CORNERS.values())]
    periods = [("1932-01-01", "1948-12-31", "1932-1948 (unseen)"), ("1949-01-01", "2016-12-31", "1949-2016 (first-run era)"),
               ("2017-01-01", "2026-12-31", "2017-2026 (unseen)"), ("1932-01-01", "2026-12-31", "1932-2026 (full)")]
    rows = []
    for name, R, rf_ in [("FF corners 9", corners, rf), ("FF all 25", vw25, rf), ("FF industries 10", ind10, rf), ("FF industries 49", ind49, rf)]:
        ew = backtest(R, "EW", start="1931-12-31")
        prim = backtest(R, "REV", {"a": 12, "b": 60}, start="1931-12-31")
        mom = backtest(R, "MOM", rebalance="quarterly", start="1931-12-31")
        ewq = backtest(R, "EW", rebalance="quarterly", start="1931-12-31")
        tilt = backtest(R, "TILT", {"a": 12, "b": 60}, start="1931-12-31")
        for a, b, lab in periods:
            rows.append({"set": name, "rule": "REV 12-60 (primary)", "period": lab, **compare(prim.loc[a:b], ew.loc[a:b], rf_)})
            rows.append({"set": name, "rule": "TILT 12-60", "period": lab, **compare(tilt.loc[a:b], ew.loc[a:b], rf_)})
            rows.append({"set": name, "rule": "MOM 1-12 quarterly", "period": lab, **compare(mom.loc[a:b], ewq.loc[a:b], rf_)})
            rows.append({"set": name, "rule": "EW vs market", "period": lab, **compare(ew.loc[a:b], mkt.loc[a:b], rf_)})
    pr = pair_backtest(vw25, "SMALL HiBM", "BIG LoBM", start="1931-12-31")
    st = backtest(vw25[["SMALL HiBM", "BIG LoBM"]], "EW", start="1931-12-31").reindex(pr.index)
    sw = backtest(vw25[["SMALL HiBM", "BIG LoBM"]], "REV", {"a": 0, "b": 60, "q": 0.5}, start="1931-12-31")
    st2 = backtest(vw25[["SMALL HiBM", "BIG LoBM"]], "EW", start="1931-12-31")
    for a, b, lab in periods:
        rows.append({"set": "small value / large growth", "rule": "PAIR z-tilt on 5y relative return (R3)", "period": lab, **compare(pr.loc[a:b], st.loc[a:b], rf)})
        rows.append({"set": "small value / large growth", "rule": "PAIR switch to 5y loser", "period": lab, **compare(sw.loc[a:b], st2.loc[a:b], rf)})
    lbm = price_updated_bm(vw25, f["bm25"])
    vp = valuation_pair(vw25, lbm)
    stv = backtest(vw25[["SMALL HiBM", "BIG LoBM"]], "EW", start=vp.index[0] - pd.offsets.MonthEnd(1)).reindex(vp.index)
    vt = valuation_tilt25(vw25, lbm)
    ew25 = backtest(vw25, "EW", start=vt.index[0] - pd.offsets.MonthEnd(1)).reindex(vt.index)
    vperiods = [("1947-01-01", "2026-12-31", "1947-2026 (E3 primary)"), ("1947-01-01", "1986-12-31", "1947-1986"),
                ("1987-01-01", "2026-12-31", "1987-2026"), ("2007-01-01", "2026-12-31", "2007-2026")]
    for a, b, lab in vperiods:
        rows.append({"set": "small value / large growth", "rule": "E3 VALUATION-SPREAD timing", "period": lab, **compare(vp.loc[a:b], stv.loc[a:b], rf)})
        rows.append({"set": "FF all 25", "rule": "valuation tilt vs own history (exploratory)", "period": lab, **compare(vt.loc[a:b], ew25.loc[a:b], rf)})
    zt = vp.attrs["z"]; zt.to_csv(OUT / "valuation_spread_z.csv")
    # ETF sets with dividends, 2006-2026 (out-of-sample)
    jb = pd.read_csv(DATA / "jb_etf_month_end_adjclose.csv", parse_dates=[0], index_col=0)
    rj = jb.pct_change(fill_method=None); rfj = rf_monthly(rj.index)
    for name, cols, pair in [("Russell style 4 ETFs", ["IWN", "IWO", "IWD", "IWF"], ("IWN", "IWF")),
                             ("S&P style 4 ETFs", ["IJS", "IJT", "IVE", "IVW"], ("IJS", "IVW")),
                             ("SPDR sectors 9 ETFs", SPDR9, None)]:
        R = rj[cols].loc["2000-08-31":]
        ew = backtest(R, "EW", start="2005-12-31"); prim = backtest(R, "REV", {"a": 12, "b": 60}, start="2005-12-31")
        rows.append({"set": name, "rule": "REV 12-60 (primary)", "period": "2006-2026", **compare(prim, ew, rfj)})
        rows.append({"set": name, "rule": "EW vs SPY", "period": "2006-2026", **compare(ew, rj["SPY"], rfj)})
        if pair:
            sw = backtest(R[list(pair)], "REV", {"a": 0, "b": 60, "q": 0.5}, start="2005-12-31")
            rows.append({"set": name, "rule": f"PAIR switch to 5y loser {pair}", "period": "2006-2026",
                         **compare(sw, backtest(R[list(pair)], "EW", start="2005-12-31"), rfj)})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "extension.csv", index=False)
    cols = ["set", "rule", "period", "months", "CAGR_%", "bench_CAGR_%", "CAGR_diff", "active_mean_%/yr", "NW_t", "Sharpe", "bench_Sharpe",
            "maxDD_%", "bench_maxDD_%", "win_10y_%"]
    print(res[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\nValuation spread z (December) and small-value weight, last 12 years:")
    print(zt.tail(12).to_string(float_format=lambda x: f"{x:,.2f}"))


def main():
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    OUT.mkdir(exist_ok=True)
    ff, rf_ff, mkt = load_ff()
    print(f"FF data {ff.index[0].date()} .. {ff.index[-1].date()}")
    prim_rows, grids, subs = [], [], []
    for name, cols, pair in [("FF style 9", STYLE9, ("S1V5", "S5V1")), ("FF industries 12", IND12, None)]:
        R = ff[cols]
        p, g = primary_and_grid(name, R, rf_ff, "1954-12-31", pair, mkt)
        prim_rows.append(p); grids.append(g)
        s = subperiods(R, rf_ff, "1954-12-31", [("1955-01-01", "1974-12-31"), ("1975-01-01", "1994-12-31"), ("1995-01-01", "2017-03-31")])
        s.insert(0, "set", name); subs.append(s)
    rq, ro = load_etf_sets()
    rf_q, rf_o = rf_monthly(rq.index), rf_monthly(ro.index)
    for name, R, rfx, pair, start in [("iShares style 6", rq[ISHARES6], rf_q, ("IWN", "IWF"), "2006-12-31"),
                                      ("SPDR sectors 9", rq[SPDR9], rf_q, None, "2004-12-31"),
                                      ("Vanguard style 4", ro[VANG4], rf_o, ("VTWV", "VONG"), "2015-12-31"),
                                      ("SmallCap sectors 9", ro[PSC9], rf_o, None, "2015-12-31")]:
        R = R.dropna(how="all")
        bm = rq["SPY"] if name in ("iShares style 6", "SPDR sectors 9") else ro["VONE"]
        p, g = primary_and_grid(name, R, rfx, start, pair, bm)
        prim_rows.append(p); grids.append(g)
    prim = pd.concat(prim_rows, ignore_index=True); grid = pd.concat(grids, ignore_index=True)
    prim.to_csv(OUT / "primary.csv", index=False); grid.to_csv(OUT / "grid.csv", index=False)
    sub = pd.concat(subs, ignore_index=True); sub.to_csv(OUT / "subperiods_ff.csv", index=False)
    cols = ["set", "rule", "rebal", "months", "CAGR_%", "bench_CAGR_%", "CAGR_diff", "active_mean_%/yr", "tracking_err_%", "NW_t",
            "Sharpe", "bench_Sharpe", "maxDD_%", "bench_maxDD_%", "win_10y_%", "turnover/yr"]
    print("\nPRIMARY RULE (REV 12-60, bottom third, annual) vs equal weight; pairs vs static 50/50; EW vs market:")
    print(prim[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\nFF sub-periods, primary rule vs EW:")
    print(sub[["set", "period", "months", "CAGR_diff", "active_mean_%/yr", "NW_t", "win_10y_%"]].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\nGrid (exploratory; ~100 variants, expect a few |t| > 2 by chance):")
    print(grid[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    extension_main() if "--extension" in sys.argv else main()
