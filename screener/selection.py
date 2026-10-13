"""
Walk-forward test of STOCK SELECTION rules for the indicator.

The question: "pick the stocks where the indicator worked best and only trade those"
- does past effectiveness predict future effectiveness, or is it luck?

Method (no lookahead):
  1. Indicator computed causally on each stock's full daily history.
  2. Execution: signal at the close, trade at the NEXT OPEN, 0.03% per side.
  3. Non-overlapping splits by default: a FORMATION window (5 yrs) scores every stock;
     the following TEST window (3 yrs) measures what the picks did.
  4. Eligibility uses only what is known at formation end: enough formation history,
     >= min_trades, and still trading at formation end. A pick that delists inside the
     test window keeps its returns to the last bar and then sits in cash.
  5. Test metric = drift-neutral timing SKILL, in % per year:
         (strategy log return - exposure x buy-and-hold log return) / years
     Raw "signal CAGR minus the stock's own buy-and-hold CAGR" rewards stocks that fell
     (the signal is flat during the fall), so a no-skill universe can look persistent.
     That edge is still reported, but it is not the test.
  6. PRIMARY criterion (declared in advance): formation-window skill. The others are
     exploratory. A one-sided permutation test applies one permutation of stock
     identities to every split, which keeps the overlap between splits inside the null;
     Holm corrects across the non-control criteria.
  7. HOLDOUT: by default only data up to 2022-12-31 is used (--until). 2023-2025 is
     reserved for one final run of a frozen rule (README "Holdout").

Criteria (formation window only):
  skill   drift-neutral timing skill                    PRIMARY (past effectiveness)
  edge    signal CAGR - own buy & hold CAGR              exploratory (biased toward fallers)
  pf      profit factor of trades                        exploratory
  gate    edge > 0, PF >= 2, edge still > 0 after dropping the best trade; passers ranked
          by skill; bottom = every stock that failed     exploratory
  vr20    20-day variance ratio (>1 = trending)          exploratory (mechanism)
  bh_dd   depth of buy & hold max drawdown               exploratory (mechanism)
  vol     annualised volatility                          exploratory (mechanism)
  random  random score                                   control

    python -m screener.selection --csv-folder data/universe
    python -m screener.selection --csv-folder data/universe --members data/universe/members.csv
    python -m screener.selection --synthetic random_walk   # harness check: no persistence
    python -m screener.selection --synthetic regime        # harness check: persistence

Survivorship: a universe of TODAY's index members (screener.data --sp500) with yfinance
history (no delisted tickers) is biased, so treat results on it as illustrative.
Trustworthy runs need point-in-time membership plus delisted price history
(--members CSV: symbol,start,end).
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
PRIMARY = "skill"
CRITERIA = ["skill", "edge", "pf", "gate", "vr20", "bh_dd", "vol", "random"]
HOLDOUT_START = "2023-01-01"


# ---------------------------------------------------------------- per-stock series

def daily_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Strategy and buy & hold daily returns (close-to-close), next-open execution."""
    o, c = df.open.to_numpy(float), df.close.to_numpy(float)
    g = moneyline(df).green.to_numpy(bool)
    h = np.r_[False, g[:-1]]                      # held during day j if green at close j-1
    hp = np.r_[False, h[:-1]]
    cc = np.r_[np.nan, c[1:] / c[:-1]]
    r = np.zeros(len(c))
    hold, entry, exit_ = h & hp, h & ~hp, ~h & hp
    r[hold] = cc[hold] - 1
    r[entry] = (1 - COST) * c[entry] / o[entry] - 1
    prev_c = np.r_[np.nan, c[:-1]]
    r[exit_] = (1 - COST) * o[exit_] / prev_c[exit_] - 1
    return pd.DataFrame({"strat": r, "bh": np.nan_to_num(cc - 1), "held": h}, index=df.index)


def window_metrics(s: pd.DataFrame, start, end, test: bool = False) -> dict | None:
    w = s.loc[start:end]
    span = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    if test:
        if len(w) == 0 or (w.index[0] - pd.Timestamp(start)).days > 7:
            return None                            # not trading when the test window opens
        pad = pd.bdate_range(w.index[-1], end)[1:]  # delisted inside the window -> cash
        if len(pad):
            w = pd.concat([w, pd.DataFrame({"strat": 0.0, "bh": 0.0, "held": False}, index=pad)])
    else:
        if len(w) < 200 or (w.index[-1] - w.index[0]).days / 365.25 < 0.8 * span:
            return None                            # not enough formation history
    yrs = max((w.index[-1] - w.index[0]).days / 365.25, 1e-9)
    r, b, held = w.strat.to_numpy(), w.bh.to_numpy(), w.held.to_numpy(bool)
    eq, bh = np.cumprod(1 + r), np.cumprod(1 + b)
    sc, bc = (eq[-1] ** (1 / yrs) - 1) * 100, (bh[-1] ** (1 / yrs) - 1) * 100
    ls, lb = float(np.log1p(r).sum()), float(np.log1p(b).sum())
    expo = float(held.mean())
    trades, cur = [], None
    for j in range(len(w)):
        if held[j]:
            cur = (1.0 if cur is None else cur) * (1 + r[j])
        elif cur is not None:
            cur *= 1 + r[j]; trades.append(cur - 1); cur = None
    t = np.array(trades)
    win, los = t[t > 0].sum(), abs(t[t <= 0].sum())
    lr = np.log1p(b)
    k = 20
    lk = pd.Series(lr).rolling(k).sum().dropna().to_numpy()[::k]
    vr = (np.var(lk) / (k * np.var(lr))) if np.var(lr) > 0 and len(lk) > 5 else np.nan
    edge_ex_best = (((eq[-1] / (1 + t.max())) ** (1 / yrs) - 1) * 100 - bc) if len(t) else np.nan
    return {"skill": (ls - expo * lb) / yrs * 100, "edge": sc - bc, "sig_cagr": sc, "bh_cagr": bc,
            "exposure": expo, "pf": win / los if los > 0 else np.nan, "trades": len(t),
            "sig_dd": float(np.min(eq / np.maximum.accumulate(eq)) - 1) * 100,
            "bh_dd": float(np.min(bh / np.maximum.accumulate(bh)) - 1) * 100,
            "vol": float(np.std(b) * np.sqrt(252) * 100), "vr20": vr, "edge_ex_best": edge_ex_best}


# ---------------------------------------------------------------- selection test

def score(m: dict, crit: str, rng) -> float:
    if crit in ("skill", "edge", "pf", "vr20", "vol"):
        return m[crit]
    if crit == "gate":
        ok = m["edge"] > 0 and (m["pf"] or 0) >= 2 and (m["edge_ex_best"] or -1) > 0
        return m["skill"] if ok else -np.inf
    if crit == "bh_dd":
        return -m["bh_dd"]                         # deeper drawdown -> higher score
    if crit == "random":
        return rng.random()
    raise ValueError(crit)


def splits(first, last, form=5, test=3, step=None):
    step = step or test                            # non-overlapping test windows by default
    out, y = [], pd.Timestamp(first).year + 1
    while pd.Timestamp(f"{y + form + test}-01-01") <= pd.Timestamp(last) + pd.Timedelta(days=7):
        out.append((f"{y}-01-01", f"{y + form - 1}-12-31", f"{y + form}-01-01", f"{y + form + test - 1}-12-31"))
        y += step
    return out


def perm_pvalues(kept, top_n, n_perm, seed) -> dict:
    """One-sided p for mean over splits of (top-N test skill - all test skill). One
    permutation of stock identities is applied to every split (keeps overlap in the null)."""
    if not kept:
        return {}
    syms = sorted(set().union(*(te.index for _, te in kept)))

    def stat(order):
        out = {}
        for c in CRITERIA:
            v = []
            for scores, te in kept:
                if c not in scores:
                    continue
                sc = scores[c]
                if order is not None:
                    canon = [s for s in syms if s in sc.index]
                    perm = [s for s in order if s in sc.index]
                    sc = pd.Series(sc[perm].to_numpy(), index=canon)
                fin = sc[np.isfinite(sc)]
                top = fin.sort_values(ascending=False).index[:top_n]
                if len(top):
                    v.append(te[top].mean() - te.mean())
            if v:
                out[c] = float(np.mean(v))
        return out

    obs = stat(None)
    rng = np.random.default_rng(seed + 12345)
    exceed = {c: 0 for c in obs}
    for _ in range(n_perm):
        null = stat(list(rng.permutation(syms)))
        for c in obs:
            exceed[c] += null.get(c, -np.inf) >= obs[c]
    p = {c: (1 + exceed[c]) / (1 + n_perm) for c in obs}
    fam = sorted((c for c in p if c != "random"), key=p.get)
    holm, run_max = {}, 0.0
    for i, c in enumerate(fam):
        run_max = max(run_max, min(1.0, (len(fam) - i) * p[c]))
        holm[c] = run_max
    return {c: (p[c], holm.get(c, np.nan)) for c in p}


def run(data, top_n=20, form=5, test=3, step=None, min_trades=8, seed=0, n_perm=500, members=None):
    series = {s: daily_returns(df) for s, df in data.items() if len(df) > 400}
    if not series:
        return pd.DataFrame()
    first = min(v.index[0] for v in series.values()); last = max(v.index[-1] for v in series.values())
    rng = np.random.default_rng(seed)
    rows, kept = [], []
    for fs, fe, ts, te in splits(first, last, form, test, step):
        pool = list(series)
        if members is not None:                    # point-in-time membership at formation start
            m = members
            active = m[(m.start <= pd.Timestamp(fs)) & (m.end.isna() | (m.end >= pd.Timestamp(fs)))]
            pool = [s for s in pool if s in set(active.symbol)]
        fm = {s: window_metrics(series[s], fs, fe) for s in pool}
        listed = pd.Timestamp(fe) - pd.Timedelta(days=7)
        elig = [s for s in pool if fm[s] and fm[s]["trades"] >= min_trades and series[s].index[-1] >= listed]
        tm = {s: window_metrics(series[s], ts, te, test=True) for s in elig}
        elig = [s for s in elig if tm[s]]
        if len(elig) < 3 * top_n:
            continue
        skill = pd.Series({s: tm[s]["skill"] for s in elig})
        edge = pd.Series({s: tm[s]["edge"] for s in elig})
        mkt = pd.concat([series[s].bh.loc[ts:te] for s in elig], axis=1).fillna(0).mean(axis=1)
        mq = np.cumprod(1 + mkt.to_numpy())
        mkt_dd = float(np.min(mq / np.maximum.accumulate(mq)) - 1) * 100
        split_scores = {}
        for crit in CRITERIA:
            raw = pd.Series({s: score(fm[s], crit, rng) for s in elig}, dtype=float).dropna()
            fin = raw[np.isfinite(raw)].sort_values(ascending=False)
            top = fin.index[:top_n]
            bot = raw.index[np.isneginf(raw.to_numpy())] if crit == "gate" else fin.index[-top_n:]
            if crit != "gate" and len(fin) < 2 * top_n:
                continue
            split_scores[crit] = raw
            rho = raw.rank().corr(skill[raw.index].rank()) if raw.nunique() > 1 else np.nan
            t_mean = skill[top].mean() if len(top) else np.nan
            rows.append({"formation": f"{fs[:4]}-{fe[:4]}", "test": f"{ts[:4]}-{te[:4]}", "criterion": crit,
                         "eligible": len(elig), "n_picks": len(top), "test_mkt_dd": mkt_dd,
                         "regime": "bear" if mkt_dd <= -30 else "bull",
                         "form_skill_picks": float(np.mean([fm[s]["skill"] for s in top])) if len(top) else np.nan,
                         "test_skill_top": t_mean, "test_skill_all": skill.mean(),
                         "test_skill_bottom": skill[bot].mean() if len(bot) else np.nan,
                         "top_minus_all": t_mean - skill.mean(), "rank_corr": rho,
                         "top_pos_share": (skill[top] > 0).mean() * 100 if len(top) else np.nan,
                         "test_edge_top": edge[top].mean() if len(top) else np.nan,
                         "test_edge_all": edge.mean()})
        kept.append((split_scores, skill))
    res = pd.DataFrame(rows)
    res.attrs["p"] = perm_pvalues(kept, top_n, n_perm, seed) if n_perm else {}
    return res


def summarise(res: pd.DataFrame) -> pd.DataFrame:
    if res.empty:
        return res
    g = res.groupby("criterion")
    out = pd.DataFrame({
        "splits": g.size(),
        "picks": g.n_picks.mean(),
        "form_skill_picks": g.form_skill_picks.mean(),
        "test_skill_top": g.test_skill_top.mean(),
        "test_skill_all": g.test_skill_all.mean(),
        "test_skill_bottom": g.test_skill_bottom.mean(),
        "top_beats_all_%": g.apply(lambda x: (x.top_minus_all > 0).mean() * 100, include_groups=False),
        "rank_corr": g.rank_corr.mean(),
        "test_edge_top": g.test_edge_top.mean(),
    })
    p = res.attrs.get("p", {})
    out["p_perm"] = pd.Series({c: v[0] for c, v in p.items()})
    out["p_holm"] = pd.Series({c: v[1] for c, v in p.items()})
    out["role"] = ["PRIMARY" if c == PRIMARY else ("control" if c == "random" else "exploratory") for c in out.index]
    return out.reindex([c for c in CRITERIA if c in out.index])


# ---------------------------------------------------------------- synthetic universes

def synthetic(kind: str, n=300, years=20, seed=1) -> dict[str, pd.DataFrame]:
    """
    random_walk: random walks with stock-specific vol and drift - no timing skill exists.
    regime:      alternating up/down trend regimes with stock-specific, fixed persistence
                 - trend-friendly stocks stay trend-friendly.
    Synthetic prices only check the harness and illustrate selection bias.
    """
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2003-01-01", periods=252 * years)
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
    ap.add_argument("--members", help="CSV symbol,start,end for point-in-time membership")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--form", type=int, default=5)
    ap.add_argument("--test", type=int, default=3)
    ap.add_argument("--step", type=int, default=None, help="default = test (non-overlapping)")
    ap.add_argument("--perm", type=int, default=500, help="permutations for p-values")
    ap.add_argument("--until", default="2022-12-31",
                    help="last date used; 2023+ is the holdout. Pass 'holdout' for the one final run.")
    ap.add_argument("--out")
    a = ap.parse_args()
    data = from_csv_folder(a.csv_folder) if a.csv_folder else synthetic(a.synthetic)
    if a.until != "holdout":
        data = {s: df.loc[:a.until] for s, df in data.items()}
    else:
        print("HOLDOUT RUN: report the result whatever it is; do not re-tune and re-run.\n")
    members = None
    if a.members:
        members = pd.read_csv(a.members, parse_dates=["start", "end"])
        members["symbol"] = members.symbol.str.upper()
    elif a.csv_folder:
        print("WARNING: no --members file. If this folder holds today's index members with yfinance "
              "history, the universe is survivorship-biased; treat results as illustrative.\n")
    if a.step and a.step < a.test:
        print("WARNING: test windows overlap; '% of splits' is not a count of independent results.\n")
    res = run(data, top_n=a.top, form=a.form, test=a.test, step=a.step, n_perm=a.perm, members=members)
    pd.set_option("display.width", 240)
    if res.empty:
        print("not enough eligible stocks for any split"); return
    print(f"{len(data)} symbols | {res['test'].nunique()} test windows (formation {a.form}y -> test {a.test}y) | "
          f"top {a.top} | metric = drift-neutral timing skill, % per year\n")
    print(summarise(res).to_string(float_format=lambda x: f"{x:,.2f}"))
    piv = res.pivot_table(index=["test", "regime"], columns="criterion", values="top_minus_all")
    print("\nTop-minus-all skill per test window:\n" + piv.to_string(float_format=lambda x: f"{x:,.1f}"))
    if a.out:
        res.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
