"""
Walk-forward test of STOCK SELECTION rules for the indicator.

The question: "pick the 20 stocks where the indicator worked best and only trade
those" - does past effectiveness predict future effectiveness, or is it luck?

Method (no lookahead):
  1. Indicator computed causally on each stock's full daily history.
  2. Execution: signal at the close, trade at the NEXT OPEN, 0.03% per side.
  3. Rolling splits: a FORMATION window (e.g. 5 yrs) to score every stock, then the
     following TEST window (e.g. 3 yrs) to measure what the picks actually did.
  4. For each selection criterion: top-N vs bottom-N vs all eligible stocks on the
     test window's edge (signal CAGR minus buy & hold CAGR), the share of picks whose
     test edge is positive, and the rank correlation between formation score and test
     edge. If selection works, top-N beats all/bottom-N consistently and the rank
     correlation is clearly positive across splits.

Criteria (scored on the formation window only):
  edge        CAGR edge vs buy & hold                    (past effectiveness)
  pf          profit factor of trades                    (past effectiveness)
  gate        edge > 0 AND PF >= 2 AND edge still > 0 after dropping the best trade,
              ranked by edge                             (past effectiveness, filtered)
  vr20        20-day variance ratio of returns (>1 = trending)   (mechanism)
  bh_dd       depth of buy & hold max drawdown          (mechanism)
  vol         annualised volatility                      (mechanism)
  random      random score                               (control)

    python -m screener.selection --csv-folder data/universe
    python -m screener.selection --synthetic random_walk   # harness check: no persistence expected
    python -m screener.selection --synthetic regime        # harness check: persistence expected
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline  # noqa: E402
from screener.data import from_csv_folder  # noqa: E402

COST = 0.0003


# ---------------------------------------------------------------- per-stock series

def daily_returns(df: pd.DataFrame):
    """Strategy and buy & hold daily returns (close-to-close), next-open execution."""
    o, c = df.open.to_numpy(float), df.close.to_numpy(float)
    g = moneyline(df).green.to_numpy(bool)
    h = np.r_[False, g[:-1]]                      # held during day j if green at close j-1
    hp = np.r_[False, h[:-1]]
    cc = np.r_[np.nan, c[1:] / c[:-1]]
    r = np.zeros(len(c))
    hold = h & hp
    entry = h & ~hp
    exit_ = ~h & hp
    r[hold] = cc[hold] - 1
    r[entry] = (1 - COST) * c[entry] / o[entry] - 1
    prev_c = np.r_[np.nan, c[:-1]]
    r[exit_] = (1 - COST) * o[exit_] / prev_c[exit_] - 1
    bh = np.nan_to_num(cc - 1)
    return pd.DataFrame({"strat": r, "bh": bh, "held": h, "entry": entry, "exit": exit_}, index=df.index)


def window_metrics(s: pd.DataFrame, start, end) -> dict | None:
    w = s.loc[start:end]
    if len(w) < 200:
        return None
    yrs = (w.index[-1] - w.index[0]).days / 365.25
    if yrs < 0.8 * ((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25):
        return None                               # not enough coverage of the window
    eq = np.cumprod(1 + w.strat.to_numpy()); bh = np.cumprod(1 + w.bh.to_numpy())
    sc = (eq[-1] ** (1 / yrs) - 1) * 100; bc = (bh[-1] ** (1 / yrs) - 1) * 100
    dd = float(np.min(eq / np.maximum.accumulate(eq)) - 1) * 100
    bdd = float(np.min(bh / np.maximum.accumulate(bh)) - 1) * 100
    # trades fully inside the window
    held = w.held.to_numpy(); r = w.strat.to_numpy()
    trades, cur = [], None
    for j in range(len(w)):
        if held[j] and cur is None:
            cur = 1.0
        if held[j]:
            cur *= 1 + r[j]
        elif cur is not None:
            cur *= 1 + r[j]; trades.append(cur - 1); cur = None
    t = np.array(trades)
    win, los = t[t > 0].sum(), abs(t[t <= 0].sum())
    lr = np.log1p(w.bh.to_numpy())
    k = 20
    lk = pd.Series(lr).rolling(k).sum().dropna().to_numpy()[::k]
    vr = (np.var(lk) / (k * np.var(lr))) if np.var(lr) > 0 and len(lk) > 5 else np.nan
    edge_ex_best = np.nan
    if len(t):
        best = t.max()
        eq_ex = eq[-1] / (1 + best)
        edge_ex_best = ((eq_ex ** (1 / yrs) - 1) * 100) - bc
    return {"edge": sc - bc, "sig_cagr": sc, "bh_cagr": bc, "sig_dd": dd, "bh_dd": bdd,
            "pf": win / los if los > 0 else np.nan, "trades": len(t),
            "vol": float(np.std(w.bh) * np.sqrt(252) * 100), "vr20": vr, "edge_ex_best": edge_ex_best,
            "log_edge": float(np.log(eq[-1]) - np.log(bh[-1]))}


# ---------------------------------------------------------------- selection test

def score(m: dict, crit: str, rng) -> float:
    if crit == "edge":
        return m["edge"]
    if crit == "pf":
        return m["pf"]
    if crit == "gate":
        ok = m["edge"] > 0 and (m["pf"] or 0) >= 2 and (m["edge_ex_best"] or -1) > 0
        return m["edge"] if ok else -np.inf
    if crit == "vr20":
        return m["vr20"]
    if crit == "bh_dd":
        return -m["bh_dd"]                         # deeper drawdown -> higher score
    if crit == "vol":
        return m["vol"]
    if crit == "random":
        return rng.random()
    raise ValueError(crit)


CRITERIA = ["edge", "pf", "gate", "vr20", "bh_dd", "vol", "random"]


def splits(first: pd.Timestamp, last: pd.Timestamp, form=5, test=3, step=1):
    out = []
    y = first.year + 1
    while pd.Timestamp(f"{y + form + test}-01-01") <= last + pd.Timedelta(days=7):
        out.append((f"{y}-01-01", f"{y + form - 1}-12-31", f"{y + form}-01-01", f"{y + form + test - 1}-12-31"))
        y += step
    return out


def run(data: dict[str, pd.DataFrame], top_n=20, form=5, test=3, step=1, min_trades=8, seed=0):
    series = {s: daily_returns(df) for s, df in data.items() if len(df) > 400}
    first = min(v.index[0] for v in series.values()); last = max(v.index[-1] for v in series.values())
    rng = np.random.default_rng(seed)
    rows = []
    for fs, fe, ts, te in splits(first, last, form, test, step):
        fm = {s: window_metrics(v, fs, fe) for s, v in series.items()}
        tm = {s: window_metrics(v, ts, te) for s, v in series.items()}
        elig = [s for s in series if fm[s] and tm[s] and fm[s]["trades"] >= min_trades]
        if len(elig) < 3 * top_n:
            continue
        test_edge = pd.Series({s: tm[s]["edge"] for s in elig})
        for crit in CRITERIA:
            sc = pd.Series({s: score(fm[s], crit, rng) for s in elig}).replace([np.inf, -np.inf], np.nan)
            ranked = sc.dropna().sort_values(ascending=False)
            if len(ranked) < top_n:
                continue
            top = ranked.index[:top_n]; bot = ranked.index[-top_n:]
            rho = sc.dropna().rank().corr(test_edge[sc.dropna().index].rank())
            rows.append({"formation": f"{fs[:4]}-{fe[:4]}", "test": f"{ts[:4]}-{te[:4]}", "criterion": crit,
                         "eligible": len(elig), "top_test_edge": test_edge[top].mean(),
                         "bottom_test_edge": test_edge[bot].mean(), "all_test_edge": test_edge.mean(),
                         "top_pos_share": (test_edge[top] > 0).mean() * 100,
                         "top_minus_all": test_edge[top].mean() - test_edge.mean(), "rank_corr": rho,
                         "top_formation_edge": np.mean([fm[s]["edge"] for s in top])})
    return pd.DataFrame(rows)


def summarise(res: pd.DataFrame) -> pd.DataFrame:
    g = res.groupby("criterion")
    out = pd.DataFrame({
        "splits": g.size(),
        "formation_edge_of_picks": g.top_formation_edge.mean(),
        "test_edge_top": g.top_test_edge.mean(),
        "test_edge_all": g.all_test_edge.mean(),
        "test_edge_bottom": g.bottom_test_edge.mean(),
        "top_beats_all_%": g.apply(lambda x: (x.top_minus_all > 0).mean() * 100, include_groups=False),
        "picks_positive_%": g.top_pos_share.mean(),
        "rank_corr_mean": g.rank_corr.mean(),
    })
    return out.reindex([c for c in CRITERIA if c in out.index])


# ---------------------------------------------------------------- synthetic universes

def synthetic(kind: str, n=300, years=20, seed=1) -> dict[str, pd.DataFrame]:
    """
    random_walk: each stock is a random walk with its own volatility and drift. The
                 indicator has no real edge anywhere, so selection must NOT persist.
    regime:      each stock alternates between up- and down-trend regimes with its own,
                 fixed persistence. Trend-friendly stocks stay trend-friendly, so
                 selection SHOULD persist.
    Prices are synthetic - this only checks the harness and illustrates selection bias.
    """
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2005-01-03", periods=252 * years)
    out = {}
    for i in range(n):
        sig = rng.uniform(0.15, 0.80) / np.sqrt(252)
        if kind == "random_walk":
            r = rng.normal(rng.normal(0.08, 0.08) / 252, sig, len(days))
        else:
            stay = rng.uniform(0.95, 0.997); amp = rng.uniform(0.0, 1.2) / 252
            state = np.empty(len(days)); s = 1
            for j in range(len(days)):
                if rng.random() > stay:
                    s = -s
                state[j] = s
            r = 0.06 / 252 + amp * state + rng.normal(0, sig, len(days))
        c = 50 * np.exp(np.cumsum(r))
        o = np.r_[50, c[:-1]] * np.exp(rng.normal(0, 0.2 * sig, len(days)))
        hi = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.5 * sig, len(days))))
        lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.5 * sig, len(days))))
        out[f"S{i:03d}"] = pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c}, index=days)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv-folder")
    src.add_argument("--synthetic", choices=["random_walk", "regime"])
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--form", type=int, default=5)
    ap.add_argument("--test", type=int, default=3)
    ap.add_argument("--out")
    a = ap.parse_args()
    data = from_csv_folder(a.csv_folder) if a.csv_folder else synthetic(a.synthetic)
    res = run(data, top_n=a.top, form=a.form, test=a.test)
    pd.set_option("display.width", 220)
    print(f"{len(data)} symbols, {res['formation'].nunique()} rolling splits "
          f"(formation {a.form}y -> test {a.test}y), top/bottom {a.top}\n")
    print(summarise(res).to_string(float_format=lambda x: f"{x:,.2f}"))
    if a.out:
        res.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
