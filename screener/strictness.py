"""
How strict should the "the indicator fits this stock" filter be?

Each re-pick date, every eligible stock is scored on its past (formation window).
Baskets are built at different strictness levels, from "only the best few" to
"every stock". Then each basket trades the signal through the following test
window, exactly as it would be traded live. The question is which strictness
level did best AFTER it was chosen, net of costs and tax, against simply holding
SPY.

    python -m screener.strictness --csv-folder data/universe --members data/universe/members.csv
    python -m screener.strictness --synthetic regime          # harness check
    python -m screener.strictness ... --until holdout          # the one final run

Basket mechanics (per test window):
  - Equal money per stock at the start; no rebalancing inside the window.
  - Each stock's slot holds the stock while the indicator is green. Signal at the
    close, trade at the next open, 0.03% per side. While red the slot holds cash
    earning T-bills (park=cash), or SPY (park=spy).
  - Tax (illustrative 35% short-term / 20% long-term, same as gate.py): realised
    gains netted across the whole basket each calendar year, losses carried forward
    (also from one window to the next), T-bill interest taxed as short-term,
    dividends at the long-term rate. The basket is liquidated and taxed at the end of
    each window (conservative: in reality a re-picked stock would be kept).
  - SPY benchmark: buy at the first open, dividends reinvested and taxed yearly,
    sold and taxed at the end of the window.
  - Prices: --prices split (Robinhood/TradingView style; dividends added from the
    approximate SPY yield table for SPY only, none for stocks: conservative for the
    strategy) or --prices total (dividend-adjusted data; nothing added, but the yearly
    dividend tax is charged on every equity position using the SPY yield as a proxy),
    or --prices qlib (qlib's US data: total return until 2021-09-16, price-only after).
  - Data cut-offs: when many series end on the same date well before the rest (qlib's
    2020-11-10 collection), those series are not tested past that date.

Strictness levels (score = formation-window metric, higher = better fit):
  top5/top10/top20/top40   the N best-scoring eligible stocks
  top25%/top50%            fractions of the eligible list
  all                      every eligible stock (no selection)
  >0, >5, >10              every stock whose score exceeds the threshold (% per year
                           for skill) - the "decent fit" levels
Criteria: skill (PRIMARY, drift-neutral timing skill, as in selection.py), gate
(strict: edge > 0, PF >= 2, edge after dropping the best trade > 0), edge, vol, random.

Survivorship: without delisted stocks the universe is biased (see README). Membership
(--members) is applied at the re-pick date: you can only pick from the index you
could see then.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline  # noqa: E402
from screener.data import from_csv_folder, quality_filter  # noqa: E402
from screener.selection import daily_returns, window_metrics, splits, synthetic, HOLDOUT_START  # noqa: E402

COST = 0.0003
ST, LT = 0.35, 0.20
# Approximate annual averages, % (3-month T-bill; SPY trailing dividend yield). Used only
# for the cash yield and, with --prices split, SPY's dividends.
TBILL = {1999: 4.6, 2000: 5.8, 2001: 3.4, 2002: 1.6, 2003: 1.0, 2004: 1.4, 2005: 3.2, 2006: 4.7,
         2007: 4.4, 2008: 1.4, 2009: 0.15, 2010: 0.14, 2011: 0.05, 2012: 0.09, 2013: 0.06,
         2014: 0.03, 2015: 0.05, 2016: 0.32, 2017: 0.93, 2018: 1.94, 2019: 2.06, 2020: 0.36,
         2021: 0.05, 2022: 2.02, 2023: 5.07, 2024: 4.97, 2025: 4.2, 2026: 3.7}
SPY_DIV = {1999: 1.1, 2000: 1.1, 2001: 1.2, 2002: 1.6, 2003: 1.7, 2004: 1.6, 2005: 1.8, 2006: 1.8,
           2007: 1.8, 2008: 2.3, 2009: 2.3, 2010: 1.9, 2011: 2.0, 2012: 2.1, 2013: 2.0, 2014: 1.9,
           2015: 2.1, 2016: 2.1, 2017: 1.9, 2018: 1.9, 2019: 1.9, 2020: 1.7, 2021: 1.3, 2022: 1.6,
           2023: 1.5, 2024: 1.3, 2025: 1.2, 2026: 1.1}
CRITERIA = ["skill", "gate", "edge", "vol", "random"]
QLIB_TOTAL_RETURN_UNTIL = pd.Timestamp("2021-09-16")   # qlib US prices are price-only afterwards
PRIMARY = "skill"
LEVELS = ["top5", "top10", "top20", "top40", "top25%", "top50%", "all", ">0", ">5", ">10"]
ETFS = {"SPY", "QQQ", "IWM", "DIA", "VOO", "IVV"}
SHARE_CLASS_DUPES = {"GOOG", "FOX", "NWS", "BF.A", "BRK.A", "DISCK", "UA", "LEN.B", "CMCSK"}


# ---------------------------------------------------------------- price panel

def _year_rate(cal, table, default):
    return np.array([table.get(d.year, default) for d in cal]) / 100 / 252


class Panel:
    """All stocks aligned to SPY's trading calendar."""

    def __init__(self, data, spy, prices="split"):
        self.cal = spy.index
        self.spy_o = spy.open.to_numpy(float); self.spy_c = spy.close.to_numpy(float)
        self.tb = _year_rate(self.cal, TBILL, 2.0)
        # Days whose prices already include dividends: none (split), all (total), or up to
        # 2021-09-16 for qlib's US data, which is price-only after that date.
        embedded = {"split": np.zeros(len(self.cal), bool), "total": np.ones(len(self.cal), bool),
                    "qlib": np.asarray(self.cal <= QLIB_TOTAL_RETURN_UNTIL)}[prices]
        y = _year_rate(self.cal, SPY_DIV, 1.8)
        self.spy_div = np.where(embedded, 0.0, y)   # SPY dividends added where prices lack them
        # embedded dividends are still taxed yearly; the SPY yield is the proxy for every
        # equity position (SPY, stocks, buy & hold alike). Stocks get no dividends where
        # prices lack them (conservative for the strategy).
        self.div_tax = np.where(embedded, y, 0.0)
        self.o, self.c, self.g, self.alive = {}, {}, {}, {}
        for s, df in data.items():
            df = df[(df.index >= self.cal[0]) & (df.index <= self.cal[-1])]
            if len(df) < 120:
                continue
            green = moneyline(df).green.astype(float)
            c = df.close.reindex(self.cal).ffill()
            o = df.open.reindex(self.cal).fillna(c.shift(1)).fillna(c)
            alive = (self.cal >= df.index[0]) & (self.cal <= df.index[-1])
            g = green.reindex(self.cal).ffill().fillna(0).to_numpy() > 0.5
            g[~alive] = False
            self.o[s], self.c[s] = o.to_numpy(float), c.to_numpy(float)
            self.g[s], self.alive[s] = g, alive

    def idx(self, start, end):
        a = int(np.searchsorted(self.cal, pd.Timestamp(start)))
        b = int(np.searchsorted(self.cal, pd.Timestamp(end), side="right")) - 1
        return a, b


# ---------------------------------------------------------------- basket simulation

def _settle(gst, glt, carry, st, lt):
    """Net the year's short- and long-term results; return (tax, new carry)."""
    nst, nlt = gst + carry[0], glt + carry[1]
    if nst < 0 < nlt:
        nlt += nst; nst = 0.0
    elif nlt < 0 < nst:
        nst += nlt; nlt = 0.0
    tax = st * max(nst, 0.0) + lt * max(nlt, 0.0)
    return tax, (min(nst, 0.0), min(nlt, 0.0))


def simulate_basket(P: Panel, picks, start, end, park="cash", tax=True, carry=(0.0, 0.0), per_slot=False,
                    always_in=False):
    """Equal-weight basket of signal slots over [start, end]. Returns a dict with the
    final multiple, daily value path, exposure, trades and the loss carry left over.
    always_in=True ignores the signal: equal-weight buy & hold of the same stocks."""
    a, b = P.idx(start, end)
    a = max(a, 1)                             # need the previous close
    n = len(picks)
    if n == 0 or b <= a:
        return None
    st, lt = (ST, LT) if tax else (0.0, 0.0)
    O = np.array([P.o[s][a - 1:b + 1] for s in picks]); C = np.array([P.c[s][a - 1:b + 1] for s in picks])
    G = np.array([P.g[s][a - 1:b + 1] for s in picks]); A = np.array([P.alive[s][a - 1:b + 1] for s in picks])
    so, sc = P.spy_o[a - 1:b + 1], P.spy_c[a - 1:b + 1]
    tb, dv, dtax = P.tb[a - 1:b + 1], P.spy_div[a - 1:b + 1], P.div_tax[a - 1:b + 1]
    cal = P.cal[a - 1:b + 1].values
    v = np.full(n, 1.0 / n)
    state = np.full(n, -1)                    # -1 initial cash, 0 park, 1 stock
    basis = np.zeros(n); entry_day = np.zeros(n, dtype="datetime64[ns]")
    gst = glt = 0.0
    path = np.empty(b - a + 1); expo = 0; trades = 0
    for k in range(1, b - a + 2):
        d = cal[k]
        want = (A[:, k - 1] if always_in else G[:, k - 1]) & A[:, k]   # green at the previous close, still listed
        new = want.astype(int)
        # ---- sales at the open
        sell_stock = (state == 1) & (new == 0)
        sell_park = (state == 0) & (new == 1) & (park == "spy")
        proceeds = v.copy()
        if sell_stock.any():
            proceeds[sell_stock] = v[sell_stock] * O[sell_stock, k] / C[sell_stock, k - 1] * (1 - COST)
        if sell_park.any():
            proceeds[sell_park] = v[sell_park] * so[k] / sc[k - 1] * (1 - COST)
        for mask in (sell_stock, sell_park):
            if mask.any():
                gain = proceeds[mask] - basis[mask]
                held_days = (d - entry_day[mask]) / np.timedelta64(1, "D")
                gst += gain[held_days <= 365].sum(); glt += gain[held_days > 365].sum()
                trades += int(mask.sum()) if mask is sell_stock else 0
        # ---- moves for the day
        stay_stock = (state == 1) & (new == 1)
        stay_park = (state == 0) & (new == 0)
        buy_stock = (state != 1) & (new == 1)
        to_park = (state != 0) & (new == 0)
        nv = v.copy()
        nv[stay_stock] = v[stay_stock] * C[stay_stock, k] / C[stay_stock, k - 1]
        if park == "cash":
            interest = tb[k]
            nv[stay_park] = v[stay_park] * (1 + interest)
            gst += (v[stay_park] * interest).sum()
            src = np.where(sell_stock, proceeds, v)
            nv[to_park] = src[to_park] * (1 + interest)
            gst += (src[to_park] * interest).sum()
        else:
            nv[stay_park] = v[stay_park] * sc[k] / sc[k - 1] * (1 + dv[k])
            div = v[stay_park] * sc[k] / sc[k - 1] * dv[k]
            glt += div.sum(); basis[stay_park] += div
            src = np.where(sell_stock, proceeds, v)
            basis[to_park] = src[to_park]; entry_day[to_park] = d
            nv[to_park] = src[to_park] * (1 - COST) * sc[k] / so[k]
        src = np.where(sell_park, proceeds, v)
        basis[buy_stock] = src[buy_stock]; entry_day[buy_stock] = d
        nv[buy_stock] = src[buy_stock] * (1 - COST) * C[buy_stock, k] / O[buy_stock, k]
        if dtax[k] > 0:                       # dividends inside total-return prices: taxed, added to basis
            eq = (new == 1) | ((new == 0) & (park == "spy"))
            inc = nv[eq] * dtax[k]
            glt += inc.sum(); basis[eq] += inc
        v = nv; state = new
        expo += int(state.sum())
        # ---- year end or window end: liquidate at the window end, settle tax
        last = k == b - a + 1
        if last:
            fin = v * np.where(state == 1, 1 - COST, np.where((state == 0) & (park == "spy"), 1 - COST, 1.0))
            liq = state == 1 if park == "cash" else state >= 0
            gain = fin[liq] - basis[liq]
            held_days = (d - entry_day[liq]) / np.timedelta64(1, "D")
            gst += gain[held_days <= 365].sum(); glt += gain[held_days > 365].sum()
            v = fin
        if last or cal[k].astype("datetime64[Y]") != cal[min(k + 1, len(cal) - 1)].astype("datetime64[Y]"):
            t, carry = _settle(gst, glt, carry, st, lt)
            if t > 0:
                f = max(0.0, 1 - t / v.sum())
                v *= f; basis *= f
            gst = glt = 0.0
        path[k - 1] = v.sum()
    out = {"mult": float(v.sum()), "path": pd.Series(path, index=P.cal[a:b + 1]),
           "exposure": expo / (n * (b - a + 1)), "trades": trades, "carry": carry}
    if per_slot:
        out["slot_mult"] = pd.Series(v * n, index=list(picks))
    return out


def spy_bh(P: Panel, start, end, tax=True):
    """Hold SPY over [start, end]: buy at the first open, reinvest dividends (taxed each
    year at the long-term rate), sell at the last close and pay tax on the gain."""
    a, b = P.idx(start, end)
    st, lt = (ST, LT) if tax else (0.0, 0.0)
    c, o, dv, dtax = P.spy_c, P.spy_o, P.spy_div, P.div_tax
    v = (1 - COST) * c[a] / o[a]; basis = 1.0; year_div = 0.0; path = [v]
    for k in range(a + 1, b + 1):
        div = v * c[k] / c[k - 1] * dv[k]
        v = v * c[k] / c[k - 1] + div
        div += v * dtax[k]                          # total-return prices: dividend already in v
        basis += div; year_div += div
        if k == b:
            fin = v * (1 - COST)
            gain = fin - basis
            rate = st if (P.cal[b] - P.cal[a]).days <= 365 else lt
            v = fin - rate * max(gain, 0.0) - lt * year_div
        elif P.cal[k].year != P.cal[k + 1].year:
            t = lt * year_div                       # sell a sliver of SPY to pay the dividend tax
            basis *= 1 - t / v; v -= t; year_div = 0.0
        path.append(v)
    return {"mult": float(v), "path": pd.Series(path, index=P.cal[a:b + 1])}


# ---------------------------------------------------------------- the study

def cagr(mult, start, end):
    yrs = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    return (mult ** (1 / yrs) - 1) * 100 if mult > 0 else -100.0


def maxdd(path):
    p = np.asarray(path, float)
    return float(np.min(p / np.maximum.accumulate(p)) - 1) * 100


def score_of(m, crit, rng):
    if crit in ("skill", "edge", "vol"):
        return m[crit]
    if crit == "gate":
        ok = m["edge"] > 0 and (m["pf"] or 0) >= 2 and (m["edge_ex_best"] or -1) > 0
        return m["skill"] if ok else -np.inf
    if crit == "random":
        return rng.random()
    raise ValueError(crit)


def pick(scores: pd.Series, level: str) -> list:
    fin = scores[np.isfinite(scores)].sort_values(ascending=False)
    n = len(scores)
    if level == "all":
        return list(scores.index)
    if level.startswith("top") and level.endswith("%"):
        k = max(1, int(round(float(level[3:-1]) / 100 * n)))
        return list(fin.index[:k])
    if level.startswith("top"):
        return list(fin.index[:int(level[3:])])
    if level.startswith(">"):
        return list(fin.index[fin > float(level[1:])])
    raise ValueError(level)


def eligible_at(series, test_series, members, fs, fe, ts, te, min_trades, censor=()):
    """censor: data cut-off dates (many series end together well before the data's end);
    a series ending on one is unknown afterwards, not delisted, so it can't be tested past it."""
    pool = [s for s in series if s in test_series
            and not (test_series[s].index[-1] in censor and pd.Timestamp(te) > test_series[s].index[-1])]
    if members is not None:                        # index membership on the re-pick date
        on = members[(members.start <= pd.Timestamp(ts)) & (members.end.isna() | (members.end >= pd.Timestamp(ts)))]
        pool = [s for s in pool if s in set(on.symbol)]
    fm = {s: window_metrics(series[s], fs, fe) for s in pool}
    listed = pd.Timestamp(fe) - pd.Timedelta(days=7)
    out = {}
    for s in pool:
        m = fm[s]
        if m and m["trades"] >= min_trades and series[s].index[-1] >= listed:
            w = test_series[s].loc[ts:te]
            if len(w) and (w.index[0] - pd.Timestamp(ts)).days <= 7:
                out[s] = m
    return out


def run(data, spy, members=None, form=5, test=3, until=None, holdout=False, park="cash",
        prices="split", min_trades=8, n_perm=1000, seed=0, criteria=CRITERIA, levels=LEVELS,
        windows=None, form_data=None):
    """windows: explicit [(form_start, form_end, test_start, test_end)] instead of the
    rolling splits. form_data: score the formation window on this data instead (e.g. a
    longer history when the test data is a recent download)."""
    data = {s: df for s, df in data.items() if s not in ETFS and s not in SHARE_CLASS_DUPES}
    test_series = {s: daily_returns(df) for s, df in data.items() if len(df) > 120}
    fdata = data if form_data is None else {s: df for s, df in form_data.items() if s in data}
    series = {s: daily_returns(df) for s, df in fdata.items() if len(df) > 400}
    P = Panel(data, spy, prices)
    first = spy.index[0]; last = spy.index[-1]
    if windows:
        sp = windows
    elif holdout:
        y0 = pd.Timestamp(HOLDOUT_START).year
        sp = [(f"{y0 - form}-01-01", f"{y0 - 1}-12-31", f"{y0}-01-01", f"{y0 + test - 1}-12-31")]
    else:
        sp = splits(first, until or last, form, test)
    ends = pd.Series({s: v.index[-1] for s, v in test_series.items()})
    censor = {d for d, n in ends.value_counts().items() if n >= 20 and d < ends.max() - pd.Timedelta(days=30)}
    if censor:
        print("data cut-off dates (series ending there are not tested past them): "
              + ", ".join(f"{d.date()} ({int((ends == d).sum())})" for d in sorted(censor)))
    rng = np.random.default_rng(seed)
    rows, slot_mults, scores_kept = [], [], []
    carry_state = {}                               # tax-loss carryforward chained across windows
    for fs, fe, ts, te in sp:
        te = min(pd.Timestamp(te), last).strftime("%Y-%m-%d")
        fm = eligible_at(series, test_series, members, fs, fe, ts, te, min_trades, censor)
        elig = [s for s in fm if s in P.c]
        if len(elig) < 30:
            continue
        spy_tax = spy_bh(P, ts, te, tax=True); spy_pre = spy_bh(P, ts, te, tax=False)
        allpre = simulate_basket(P, elig, ts, te, park, tax=False, per_slot=True)
        slot_mults.append(allpre["slot_mult"])
        ew_tax = simulate_basket(P, elig, ts, te, "cash", tax=True, always_in=True, carry=carry_state.get("ew", (0.0, 0.0)))
        carry_state["ew"] = ew_tax["carry"]
        ew_pre = simulate_basket(P, elig, ts, te, "cash", tax=False, always_in=True)
        sc_by = {}
        for crit in criteria:
            sc = pd.Series({s: score_of(fm[s], crit, rng) for s in elig}, dtype=float)
            sc_by[crit] = sc
            for lev in levels:
                if lev.startswith(">") and crit not in ("skill", "edge", "gate"):
                    continue
                picks = pick(sc, lev)
                if not picks:
                    rows.append({"test": f"{ts[:4]}-{te[:4]}", "criterion": crit, "level": lev, "n": 0})
                    continue
                post = simulate_basket(P, picks, ts, te, park, tax=True, carry=carry_state.get((crit, lev), (0.0, 0.0)))
                pre = simulate_basket(P, picks, ts, te, park, tax=False)
                pbh = simulate_basket(P, picks, ts, te, "cash", tax=True, always_in=True,
                                      carry=carry_state.get((crit, lev, "bh"), (0.0, 0.0)))
                carry_state[(crit, lev)], carry_state[(crit, lev, "bh")] = post["carry"], pbh["carry"]
                rows.append({
                    "test": f"{ts[:4]}-{te[:4]}", "start": ts, "end": te, "criterion": crit, "level": lev,
                    "eligible": len(elig), "n": len(picks),
                    "form_score": float(np.nanmean(np.where(np.isfinite(sc[picks]), sc[picks], np.nan))),
                    "cagr_pre": cagr(pre["mult"], ts, te), "cagr_tax": cagr(post["mult"], ts, te),
                    "spy_pre": cagr(spy_pre["mult"], ts, te), "spy_tax": cagr(spy_tax["mult"], ts, te),
                    "dd": maxdd(pre["path"]), "spy_dd": maxdd(spy_pre["path"]),
                    "exposure": pre["exposure"] * 100, "trades_per_stock_yr": pre["trades"] / len(picks) /
                    max((pd.Timestamp(te) - pd.Timestamp(ts)).days / 365.25, 1e-9),
                    "mult_pre": pre["mult"], "mult_tax": post["mult"], "spy_mult_tax": spy_tax["mult"],
                    "spy_mult_pre": spy_pre["mult"],
                    "picks_bh_mult_tax": pbh["mult"], "ew_all_mult_tax": ew_tax["mult"],
                    "ew_all_mult_pre": ew_pre["mult"], "ew_all_dd": maxdd(ew_pre["path"]),
                    "picks": " ".join(sorted(picks)) if len(picks) <= 40 else "",
                })
        scores_kept.append(sc_by)
    res = pd.DataFrame(rows)
    if not res.empty:                              # SPY held through every test window, taxed once
        t0, t1 = res.start.min(), res.end.max()
        res.attrs["spy_hold"] = {"tax": cagr(spy_bh(P, t0, t1, tax=True)["mult"], t0, t1),
                                 "pre": cagr(spy_bh(P, t0, t1, tax=False)["mult"], t0, t1),
                                 "dd": maxdd(spy_bh(P, t0, t1, tax=False)["path"])}
    if not res.empty and n_perm:
        res.attrs["p"] = perm_test(scores_kept, slot_mults, criteria, levels, n_perm, seed)
    return res


def perm_test(scores_kept, slot_mults, criteria, levels, n_perm, seed):
    """One-sided p for: mean over windows of ln(basket pre-tax multiple) - ln(all-stock
    basket multiple) is this large by chance. One permutation of stock identities is
    applied in every window."""
    syms = sorted(set().union(*(m.index for m in slot_mults)))

    canon = [[s for s in syms if s in W.index] for W in slot_mults]

    def stat(order):
        acc = {}
        for w, (sc_by, W) in enumerate(zip(scores_kept, slot_mults)):
            perm = None if order is None else [s for s in order if s in W.index]
            base = np.log(W.mean())
            for crit in criteria:
                sc = sc_by[crit]
                if perm is not None:
                    sc = pd.Series(sc[perm].to_numpy(), index=canon[w])
                for lev in levels:
                    if lev == "all" or (lev.startswith(">") and crit not in ("skill", "edge", "gate")):
                        continue
                    pk = pick(sc, lev)
                    if pk:
                        acc.setdefault((crit, lev), []).append(np.log(W[pk].mean()) - base)
        return {key: float(np.mean(v)) for key, v in acc.items()}

    obs = stat(None)
    rng = np.random.default_rng(seed + 999)
    exceed = dict.fromkeys(obs, 0)
    for _ in range(n_perm):
        null = stat(list(rng.permutation(syms)))
        for key in obs:
            exceed[key] += null.get(key, -np.inf) >= obs[key]
    return {key: (1 + exceed[key]) / (1 + n_perm) for key in obs}


def chain(res: pd.DataFrame) -> pd.DataFrame:
    """Re-pick every window and carry the money forward: one compounded result per
    (criterion, level) over all test windows, after tax, vs SPY."""
    out = []
    for (crit, lev), g in res.dropna(subset=["mult_tax"]).groupby(["criterion", "level"]):
        g = g.sort_values("start")
        yrs = sum((pd.Timestamp(e) - pd.Timestamp(s)).days / 365.25 for s, e in zip(g.start, g.end))
        m, ms = g.mult_tax.prod(), g.spy_mult_tax.prod()
        mb, me = g.picks_bh_mult_tax.prod(), g.ew_all_mult_tax.prod()
        mp, msp = g.mult_pre.prod(), g.spy_mult_pre.prod()
        beat = [(r.cagr_tax >= r.spy_tax) or (r.cagr_tax >= r.spy_tax - 2 and r.dd >= r.spy_dd + 15)
                for r in g.itertuples()]
        beat_pre = [(r.cagr_pre >= r.spy_pre) or (r.cagr_pre >= r.spy_pre - 2 and r.dd >= r.spy_dd + 15)
                    for r in g.itertuples()]
        me_pre = g.ew_all_mult_pre.prod()
        out.append({"criterion": crit, "level": lev, "windows": len(g), "avg_n": g.n.mean(),
                    "cagr_tax": (m ** (1 / yrs) - 1) * 100, "spy_tax": (ms ** (1 / yrs) - 1) * 100,
                    "excess_tax": (m ** (1 / yrs) - ms ** (1 / yrs)) * 100,
                    "cagr_pre": (mp ** (1 / yrs) - 1) * 100, "spy_pre": (msp ** (1 / yrs) - 1) * 100,
                    "picks_bh_tax": (mb ** (1 / yrs) - 1) * 100, "ew_all_bh_tax": (me ** (1 / yrs) - 1) * 100,
                    "worst_dd": g.dd.min(), "spy_worst_dd": g.spy_dd.min(),
                    "ew_all_bh_pre": (me_pre ** (1 / yrs) - 1) * 100,
                    "windows_beating_spy": f"{sum(beat)}/{len(g)}", "windows_beating_spy_pre": f"{sum(beat_pre)}/{len(g)}",
                    "exposure": g.exposure.mean()})
    out = pd.DataFrame(out)
    hold = res.attrs.get("spy_hold")
    if hold and len(out):
        out["spy_hold_tax"] = hold["tax"]
        out["excess_vs_spy_hold_tax"] = out.cagr_tax - hold["tax"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv-folder")
    src.add_argument("--synthetic", choices=["random_walk", "regime"])
    ap.add_argument("--members", help="CSV symbol,start,end (point-in-time index membership)")
    ap.add_argument("--spy", default="SPY", help="benchmark symbol in the folder")
    ap.add_argument("--park", choices=["cash", "spy"], default="cash")
    ap.add_argument("--prices", choices=["split", "total", "qlib"], default="split",
                    help="qlib = total return until 2021-09-16, price-only after (qlib US data)")
    ap.add_argument("--form", type=int, default=5)
    ap.add_argument("--test", type=int, default=3)
    ap.add_argument("--perm", type=int, default=1000)
    ap.add_argument("--until", default="2022-12-31", help="'holdout' for the one final run")
    ap.add_argument("--window", help="explicit form_start,form_end,test_start,test_end (overrides --until)")
    ap.add_argument("--form-folder", help="score formation windows on this folder's data (e.g. a longer history)")
    ap.add_argument("--levels", help="comma-separated subset of levels")
    ap.add_argument("--exclude", help="comma-separated symbols to leave out (e.g. known recycled tickers)")
    ap.add_argument("--keep-collapsed", action="store_true",
                    help="keep failed companies cut at their collapse instead of dropping them (data.quality_filter)")
    ap.add_argument("--criteria", help="comma-separated subset of criteria")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.csv_folder:
        data, dropped = quality_filter(from_csv_folder(a.csv_folder), keep_collapsed=a.keep_collapsed)
        if dropped:
            print(f"dropped {len(dropped)} broken/spliced series: " + ", ".join(f"{k} ({v})" for k, v in sorted(dropped.items())) + "\n")
        spy = data[a.spy.upper()]
        if a.exclude:
            data = {k: v for k, v in data.items() if k not in {x.strip().upper() for x in a.exclude.split(",")}}
    else:
        data = synthetic(a.synthetic)
        spy = data.pop("S000")
    members = None
    if a.members:
        members = pd.read_csv(a.members, parse_dates=["start", "end"])
        members["symbol"] = members.symbol.str.upper()
    holdout = a.until == "holdout"
    windows = [tuple(a.window.split(","))] if a.window else None
    form_data = None
    if a.form_folder:
        form_data, _ = quality_filter(from_csv_folder(a.form_folder))
    if not holdout and not windows:
        data = {s: df.loc[:a.until] for s, df in data.items()}
        spy = spy.loc[:a.until]
    if holdout or windows:
        print("OUT-OF-SAMPLE RUN: report the result whatever it is; do not re-tune and re-run.\n")
    kw = {}
    if a.levels:
        kw["levels"] = [x.strip() for x in a.levels.split(",")]
    if a.criteria:
        kw["criteria"] = [x.strip() for x in a.criteria.split(",")]
    res = run(data, spy, members, a.form, a.test, holdout=holdout, park=a.park, prices=a.prices, n_perm=a.perm,
              windows=windows, form_data=form_data, **kw)
    if res.empty:
        print("no usable windows"); return
    ch = chain(res)
    p = res.attrs.get("p", {})
    ch["p_vs_all"] = [p.get((c, l), np.nan) for c, l in zip(ch.criterion, ch.level)]
    ch["level"] = pd.Categorical(ch.level, LEVELS, ordered=True)
    ch = ch.sort_values(["criterion", "level"])
    pd.set_option("display.width", 250)
    print(f"{res.test.nunique()} test windows: {', '.join(sorted(res.test.unique()))} | park={a.park} | prices={a.prices}\n")
    print(ch.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    if a.out:
        res.to_csv(a.out, index=False)
        ch.to_csv(Path(a.out).with_name(Path(a.out).stem + "_chain.csv"), index=False)


if __name__ == "__main__":
    main()
