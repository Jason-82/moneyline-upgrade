"""
Split mode: how long should the second tranche wait? Pre-registration (binding, committed before any run):
analysis_2026/SPLIT_DELAY_PREREG.md.

    python3 -m analysis_2026.split_delay [--workers 4]      # -> analysis_2026/results_split_delay/

Tranche 1 is always 50% at N=1 (the old MoneyLine as replicated). Tranche 2 is 50% at (n_entry, n_exit) consecutive
closes beyond the trailing line for red->green / green->red: n_entry in {1,2,3,5,8,12} x n_exit in {2,3,5,8,12,20},
36 variants; the benchmark is split(5,5), the agentic default. References: immediate (100% N=1), confirm5 (100% N=5),
buy & hold. Signal: agentic.indicator.moneyline_confirmed. Engine: agentic.backtest.weights_returns (weight decided at
the close, filled at the next open, cost x |dw| per side, cash at T-bills).

Primary samples: P1 point-in-time S&P 500 basket incl. failed companies 2001-01..2026-09; P2 each year's most
volatile fifth of its members (std of daily returns over the 252 trading days before 1 January); P3 each year's
crypto top-20 incl. dead coins 2019-01..2026-09. Equal weight of each year's members, daily-rebalanced, each member on
its own signal (flip_delay.basket). Costs per side: stocks 0.03%, crypto 0.15% (0.95% as a sensitivity).
Decision (per sample): IS-best variant by Sharpe above T-bills vs split(5,5) on OOS (paired stationary bootstrap,
one-sided, Holm across P1-P3, p < 0.05), White reality check of the 36-variant grid on the full sample (p < 0.10),
gain positive in both OOS halves, OOS maxDD no more than 5 points worse. Otherwise split(5,5) stays.

Choices the pre-registration leaves open (fixed before the first full run):
  - trades_per_yr = orders per member per year: weight changes summed over member-years / member-years (bars/ppy).
    A 0.5 change of the split weight counts as one order, as agentic.backtest counts them.
  - P2 candidates: the year's members with 252 daily returns before 1 January and a close in the 7 calendar days
    before it; the top ceil(n/5) by standard deviation are held for the whole year.
  - White reality check: statistic max_k (Sharpe_k - Sharpe_split(5,5)) over the 36 variants (annualised, above
    T-bills, ddof 0 as in larsson.boot_sharpe_gain). Each bootstrap draw resamples all series with the same
    stationary-bootstrap indices; each gain is recentred on its observed value; p = share of draws whose max is at
    least the observed max. split(5,5) is itself in the grid (gain 0), so p = 1 when nothing beats it.
  - ETFs take the stock cost (0.03%): the pre-registration names two cost classes only.
  - A member-year needs more than 20 bars up to 2026-09-30 (flip_delay.basket's filter, applied after the end cut).
  - OOS halves are the first and second halves of the OOS trading days (larsson.boot_sharpe_gain).
  - Seeds: OOS tests 1/2/3, reality checks 11/12/13, secondary tests 21+; reported-only robustness: reality-check
    seed sensitivity 111-115 / 121-125 / 131-135, exploratory split(5,8) vs split(5,5) OOS tests 31/32/33.
Audit corrections (after the first full run; the design is unchanged): the reality check's benchmark column was
split(12,20) because of a duplicated pandas label (see reality_check); fixed and rerun with the same seeds. The OOS
surface reading and the exploratory split(5,8) test were added after the audit and are descriptive only.
Validation (run first; the exact checks abort the run on failure): moneyline_confirmed(N, N) equals
flip_delay.moneyline_delay(N) for N = 1 and 5; weights_returns with 0/1 weights equals flip_delay.strat_returns;
split(5,5) weights equal the agentic default split mode (tranche_targets); tranche 2 at (1,1) gives the immediate
result in every basket; the basket pipeline reproduces results_delay/baskets.csv (S&P basket N=1 / N=5) and
results_agentic_modes/split_crypto.txt (crypto basket, flip_delay's crypto costs).
"""
from __future__ import annotations

import argparse
import sys
import time
from math import ceil
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentic.backtest import weights_returns  # noqa: E402
from agentic.indicator import moneyline_confirmed, tranche_targets  # noqa: E402
from analysis_2026.flip_delay import (ETF13, LARGE20, load_crypto_daily, load_etf, moneyline_delay,  # noqa: E402
                                      strat_returns)
from analysis_2026.larsson import boot_sharpe_gain, holm, rf_daily, summarise  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis_2026" / "results_split_delay"
END = pd.Timestamp("2026-09-30")
NE = (1, 2, 3, 5, 8, 12)
NX = (2, 3, 5, 8, 12, 20)
GRID = [(a, b) for a in NE for b in NX]


def vname(a, b):
    return f"split({a},{b})"


GRIDN = [vname(a, b) for a, b in GRID]
BENCH = vname(5, 5)
CHECK = vname(1, 1)                      # validation only: tranche 2 at (1,1) must reproduce immediate
STRATS = ["immediate", "confirm5", CHECK] + GRIDN
COLS = STRATS + ["BH"]
CONFIGS = sorted({(1, 1), (5, 5), *GRID})
C_STOCK, C_CRYPTO, C_CRYPTO_HI = 0.0003, 0.0015, 0.0095
WARMUP = 120
N_BOOT = 2000
METRICS = ["Sharpe", "CAGR_%", "CAGR_tax_%", "maxDD_%", "trades_per_yr"]
SAMPLES = {
    "P1": {"label": "S&P 500 point-in-time basket incl. failed companies", "ppy": 252, "block": 250,
           "full": ("2001-01-01", "2026-09-30"), "is": ("2001-01-01", "2013-12-31"), "oos": ("2014-01-01", "2026-09-30"),
           "seed": 1, "rc_seed": 11, "group": "stocks"},
    "P2": {"label": "High-volatility fifth of the S&P 500 members (ranked on the prior 252 days)", "ppy": 252,
           "block": 250, "full": ("2001-01-01", "2026-09-30"), "is": ("2001-01-01", "2013-12-31"),
           "oos": ("2014-01-01", "2026-09-30"), "seed": 2, "rc_seed": 12, "group": "stocks"},
    "P3": {"label": "Crypto top-20 incl. dead coins", "ppy": 365, "block": 180,
           "full": ("2019-01-01", "2026-09-30"), "is": ("2019-01-01", "2022-12-31"), "oos": ("2023-01-01", "2026-09-30"),
           "seed": 3, "rc_seed": 13, "group": "crypto"},
}
SECONDARY_BOOKS = {"P3_095": "P3"}       # crypto basket at 0.95%/side, same members and windows as P3


# ------------------------------------------------------------------ per-symbol engine

def symbol_mats(df, costs):
    """Returns ({cost: T x len(COLS) daily returns}, held weights T x len(STRATS), weight-change mask T x len(STRATS)).
    held[t] is the weight earning on day t (decided at close t-1), as agentic.backtest._path."""
    g = {k: moneyline_confirmed(df, *k)["green"].to_numpy(dtype=float) for k in CONFIGS}
    g1 = g[(1, 1)]
    W = [g1, g[(5, 5)], 0.5 * g1 + 0.5 * g1] + [0.5 * g1 + 0.5 * g[k] for k in GRID]
    held = np.column_stack([np.r_[0.0, w[:-1]] for w in W])
    prev = np.vstack([np.zeros((1, len(W))), held[:-1]])
    changed = held != prev
    bh = df["close"].pct_change().fillna(0.0).to_numpy()
    R = {}
    for c in costs:
        M = np.empty((len(df), len(COLS)))
        for j, w in enumerate(W):
            r, n = weights_returns(df, w, c)
            if n != int(changed[:, j].sum()):
                raise AssertionError("weight-change count differs from weights_returns")
            M[:, j] = r.to_numpy()
        M[:, -1] = bh
        R[c] = M
    return R, held, changed


def run_chunk(task):
    """task = (items, yidx): items are (symbol, ohlc df, {book: (cost, [years])}); yidx maps (book, year) to the
    year's basket dates. Returns per (book, year) sums for the daily (S / N) and held (HS / nh) baskets, weight
    changes (CH), bars and held-weight sums (EXPO)."""
    items, yidx = task
    acc, rfc = {}, {}
    for sym, df, books in items:
        R, held, changed = symbol_mats(df, sorted({c for c, _ in books.values()}))
        ix = df.index
        for book, (cost, years) in books.items():
            M = R[cost]
            for y in years:
                a = ix.searchsorted(pd.Timestamp(f"{y}-01-01"))
                b = ix.searchsorted(min(pd.Timestamp(f"{y}-12-31"), END), side="right")
                if b - a <= 20:
                    continue
                key = (book, y)
                yi = yidx[key]
                pos = yi.get_indexer(ix[a:b])
                if (pos < 0).any():
                    raise AssertionError(f"{sym} {key}: dates missing from the year index")
                if key not in rfc:
                    rfc[key] = rf_daily(yi).to_numpy()
                rf = rfc[key]
                if key not in acc:
                    T, V, NS = len(yi), len(COLS), len(STRATS)
                    acc[key] = {"S": np.zeros((T, V)), "N": np.zeros((T, V)), "HS": np.zeros((T, V)), "nh": 0,
                                "CH": np.zeros(NS), "BARS": 0, "EXPO": np.zeros(NS)}
                A = acc[key]
                X = M[a:b]
                fin = np.isfinite(X)
                A["S"][pos] += np.where(fin, X, 0.0)
                A["N"][pos] += fin
                full = np.repeat(rf[:, None], len(COLS), axis=1)
                full[pos] = np.where(fin, X, rf[pos][:, None])        # larsson.basket 'held': gaps sit in T-bills
                A["HS"] += np.cumprod(1.0 + full, axis=0)
                A["nh"] += 1
                A["CH"] += changed[a:b].sum(axis=0)
                A["BARS"] += b - a
                A["EXPO"] += held[a:b].sum(axis=0)
    return acc


def merge(dst, src):
    for k, A in src.items():
        if k not in dst:
            dst[k] = A
            continue
        for f in ("S", "N", "HS", "CH", "EXPO"):
            dst[k][f] = dst[k][f] + A[f]
        dst[k]["nh"] += A["nh"]
        dst[k]["BARS"] += A["BARS"]


def asset_task(task):
    """Secondary per-asset run: (class, symbol, ohlc df, [costs], ppy, start) -> metric rows per cost and variant."""
    cls, sym, df, costs, ppy, start = task
    R, held, changed = symbol_mats(df, costs)
    st = max(pd.Timestamp(start), df.index[min(len(df) - 1, WARMUP)])
    win = (df.index >= st) & (df.index <= END)
    rf = rf_daily(df.index)
    yrs = win.sum() / ppy
    rows = []
    for c in costs:
        for j, v in enumerate(COLS):
            r = pd.Series(R[c][win, j], index=df.index[win])
            s = summarise(r, ppy, rf, hold=(v == "BH"))
            row = {"class": cls, "asset": sym, "cost_%": c * 100, "variant": v, "start": str(st.date()),
                   "Sharpe": s["Sharpe_xs"], "Sharpe_total": s["Sharpe"], "CAGR_%": s["CAGR_%"],
                   "CAGR_tax_%": s["CAGR_tax_%"], "maxDD_%": s["maxDD_%"], "years": s["years"]}
            if v != "BH":
                row["trades_per_yr"] = float(changed[win, j].sum() / yrs)
                row["exposure_%"] = float(held[win, j].mean() * 100)
            rows.append(row)
    return rows


# ------------------------------------------------------------------ samples

def year_index(data, members, years):
    """Per year: the members with more than 20 bars in [1 Jan, min(31 Dec, END)] and the union of their dates."""
    yidx, inc = {}, {}
    for y in years:
        a, b = pd.Timestamp(f"{y}-01-01"), min(pd.Timestamp(f"{y}-12-31"), END)
        parts, mem = [], []
        for s in dict.fromkeys(members.get(y, [])):
            if s not in data:
                continue
            ix = data[s].index
            i0, i1 = ix.searchsorted(a), ix.searchsorted(b, side="right")
            if i1 - i0 > 20:
                parts.append(ix[i0:i1].values)
                mem.append(s)
        if parts:
            yidx[y] = pd.DatetimeIndex(np.unique(np.concatenate(parts)))
            inc[y] = mem
    return yidx, inc


def high_vol_members(data, mby, years):
    """P2: per year, the top ceil(n/5) of the members by std of daily returns over the 252 trading days before
    1 January (only data before 1 January is used)."""
    out, info = {}, []
    for y in years:
        jan1 = pd.Timestamp(f"{y}-01-01")
        vols = {}
        for s in dict.fromkeys(mby.get(y, [])):
            if s not in data:
                continue
            c = data[s]["close"]
            before = c[c.index < jan1]
            if len(before) < 253 or before.index[-1] < jan1 - pd.Timedelta(days=7):
                continue
            r = before.pct_change().iloc[-252:]
            if r.notna().sum() < 252:
                continue
            vols[s] = float(r.std())
        rank = pd.Series(vols, dtype=float).sort_values(ascending=False, kind="stable")
        k = ceil(len(rank) / 5)
        out[y] = list(rank.index[:k])
        info.append({"year": y, "members": len(dict.fromkeys(mby.get(y, []))), "candidates": len(rank), "selected": k,
                     "vol_cutoff_daily_%": float(rank.iloc[k - 1] * 100) if k else np.nan,
                     "median_vol_all_%": float(rank.median() * 100) if k else np.nan,
                     "symbols": " ".join(out[y])})
    return out, pd.DataFrame(info)


# ------------------------------------------------------------------ statistics

def stationary_idx(T, m, block, rng):
    """Stationary-bootstrap index draws, generated exactly as larsson.boot_sharpe_gain does."""
    idx = np.empty((m, T), dtype=np.int64)
    idx[:, 0] = rng.integers(0, T, m)
    new = rng.random((m, T)) < 1.0 / block
    st = rng.integers(0, T, (m, T))
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], st[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def reality_check(R, rf, cands, bench, ppy, block, n=N_BOOT, seed=0):
    """White's reality check of max_k (Sharpe_k - Sharpe_bench) over cands; recentred stationary bootstrap.
    The benchmark is stacked separately as the last column. (The first run selected R[cands + [bench]] while bench
    was already in cands; pandas expands a duplicated label into every copy, so the 'benchmark' column became
    split(12,20). Fixed after the audit; the asserts below guard the layout.)"""
    cands = list(dict.fromkeys(cands))
    j = pd.concat([R[cands], R[bench].rename("_bench"), rf.rename("_rf")], axis=1).dropna()
    if not j.columns.is_unique or j.shape[1] != len(cands) + 2:
        raise AssertionError("reality check: duplicated or missing columns")
    E = np.column_stack([j[cands].to_numpy(), j["_bench"].to_numpy()]) - j["_rf"].to_numpy()[:, None]
    T, K = E.shape[0], len(cands)
    if E.shape[1] != K + 1:
        raise AssertionError("reality check: E must hold K candidates plus the benchmark")
    sh = E.mean(0) / E.std(0) * np.sqrt(ppy)
    gain = sh[:K] - sh[K]
    if bench in cands and gain[cands.index(bench)] != 0.0:
        raise AssertionError("reality check: the benchmark's own gain must be exactly 0")
    v_obs = float(gain.max())
    rng = np.random.default_rng(seed)
    vstar = np.empty(n)
    for k0 in range(0, n, 250):
        m = min(250, n - k0)
        idx = stationary_idx(T, m, block, rng)
        shs = np.empty((m, K + 1))
        for k in range(K + 1):
            X = E[:, k][idx]
            shs[:, k] = X.mean(1) / X.std(1) * np.sqrt(ppy)
        vstar[k0:k0 + m] = ((shs[:, :K] - shs[:, [K]]) - gain).max(1)
    return {"V_obs": v_obs, "argmax": cands[int(gain.argmax())], "p_rc": float(np.mean(vstar >= v_obs)),
            "boot_q95": float(np.quantile(vstar, 0.95)), "T": T}


def window_rows(R, rf, trades, ppy, a, b):
    x, f = R.loc[a:b], rf.loc[a:b]
    T = trades.loc[int(a[:4]):int(b[:4])]
    member_years = T["bars"].sum() / ppy
    rows = []
    for v in COLS:
        s = summarise(x[v], ppy, f, hold=(v == "BH"))
        ne, nx = (int(t) for t in v[6:-1].split(",")) if v.startswith("split(") else (np.nan, np.nan)
        row = {"variant": v, "n_entry": ne, "n_exit": nx, "Sharpe": s["Sharpe_xs"], "Sharpe_total": s["Sharpe"],
               "CAGR_%": s["CAGR_%"], "CAGR_tax_%": s["CAGR_tax_%"], "maxDD_%": s["maxDD_%"], "years": s["years"]}
        if v != "BH":
            row["trades_per_yr"] = float(T[f"chg|{v}"].sum() / member_years)
            row["exposure_%"] = float(T[f"exp|{v}"].sum() / T["bars"].sum() * 100)
        rows.append(row)
    return pd.DataFrame(rows)


def assemble(acc, book, yidx):
    daily, held, tr = [], [], []
    for y in sorted(yy for (bk, yy) in acc if bk == book):
        A, ix = acc[(book, y)], yidx[(book, y)]
        with np.errstate(invalid="ignore", divide="ignore"):
            daily.append(pd.DataFrame(A["S"] / A["N"], index=ix, columns=COLS))
        V = pd.DataFrame(A["HS"] / A["nh"], index=ix, columns=COLS)
        held.append(V / V.shift(1).fillna(1.0) - 1)
        tr.append({"year": y, "members": A["nh"], "bars": A["BARS"],
                   **{f"chg|{v}": A["CH"][k] for k, v in enumerate(STRATS)},
                   **{f"exp|{v}": A["EXPO"][k] for k, v in enumerate(STRATS)}})
    return (pd.concat(daily).sort_index().loc[:END], pd.concat(held).sort_index().loc[:END],
            pd.DataFrame(tr).set_index("year"))


def surface(tab, metric):
    g = tab[tab.variant.isin(GRIDN)]
    return g.pivot_table(index="n_entry", columns="n_exit", values=metric).reindex(index=list(NE), columns=list(NX))


def fmt_surface(tab, metric, title, nd=2):
    s = surface(tab, metric)
    ref = tab.set_index("variant")[metric]
    lines = [title, "  n_entry \\ n_exit " + "".join(f"{c:>8}" for c in s.columns)]
    for ne, row in s.iterrows():
        lines.append(f"  {ne:>16} " + "".join(f"{v:8.{nd}f}" for v in row.to_numpy()))
    bh = "" if metric == "trades_per_yr" else f" | buy & hold {ref['BH']:.{nd}f}"
    lines.append(f"  references: immediate {ref['immediate']:.{nd}f} | confirm5 {ref['confirm5']:.{nd}f}{bh}"
                 f" | benchmark split(5,5) {ref[BENCH]:.{nd}f}")
    return "\n".join(lines)


# ------------------------------------------------------------------ validation

def validate(say, sp_sample):
    """Exact checks; raises on failure."""
    from agentic.config import DEFAULT_MODES
    assets = [("SPY", load_etf("SPY"), C_STOCK), ("QQQ", load_etf("QQQ"), C_STOCK),
              ("BTC", load_crypto_daily("BTC"), C_CRYPTO), ("SOL", load_crypto_daily("SOL"), C_CRYPTO)]
    assets += [(s, d, C_STOCK) for s, d in sp_sample.items()]
    bad = []
    for name, d, c in assets:
        g = {}
        for n in (1, 5):
            ref = moneyline_delay(d, n)
            new = moneyline_confirmed(d, n, n)["green"].to_numpy()
            g[n] = new
            if not (ref == new).all():
                bad.append(f"{name}: moneyline_confirmed({n},{n}) != moneyline_delay({n})")
            r_ref = strat_returns(d, ref, c)[0].to_numpy()
            r_new = weights_returns(d, new.astype(float), c)[0].to_numpy()
            dmax = float(np.nanmax(np.abs(r_ref - r_new)))
            if dmax > 1e-12 or not (np.isnan(r_ref) == np.isnan(r_new)).all():
                bad.append(f"{name}: weights_returns vs strat_returns N={n} max diff {dmax:.2e}")
        g1, g5 = g[1].astype(float), g[5].astype(float)
        r_imm = weights_returns(d, g1, c)[0].to_numpy()
        r_11 = weights_returns(d, 0.5 * g1 + 0.5 * g1, c)[0].to_numpy()
        if not np.array_equal(r_imm, r_11):
            bad.append(f"{name}: tranche 2 at (1,1) != immediate")
        tt = tranche_targets(d, DEFAULT_MODES["split"])["target_frac"].to_numpy()
        if not np.array_equal(tt, 0.5 * g1 + 0.5 * g5):
            bad.append(f"{name}: split(5,5) weights != agentic default split mode")
        R, held, changed = symbol_mats(d, [c])
        for v, w in [("immediate", g1), (BENCH, tt), ("confirm5", g5)]:
            if not np.array_equal(R[c][:, COLS.index(v)], weights_returns(d, w, c)[0].to_numpy()):
                bad.append(f"{name}: symbol_mats column {v} differs")
    say(f"VALIDATION (exact, on {', '.join(a[0] for a in assets)}):")
    say("  moneyline_confirmed(N,N) == flip_delay.moneyline_delay(N) for N = 1, 5;"
        " weights_returns(0/1 weights) == flip_delay.strat_returns (max |diff| <= 1e-12);")
    say("  tranche 2 at (1,1) == immediate; split(5,5) weights == agentic DEFAULT_MODES['split'] (tranche_targets).")
    if bad:
        for b in bad:
            say("  FAIL " + b)
        raise SystemExit("validation failed")
    say("  all passed")


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--max-symbols", type=int, default=0, help="debug: only the first N stock symbols")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 60)
    t0 = time.time()
    lines = []

    def say(x=""):
        print(x, flush=True); lines.append(str(x))

    def log(x):
        print(f"[{time.time() - t0:7.1f}s] {x}", flush=True)

    say("SPLIT MODE, SECOND-TRANCHE DELAY SWEEP (pre-registration: analysis_2026/SPLIT_DELAY_PREREG.md)")
    say(f"Tranche 1: 50% at N=1. Tranche 2: 50% at (n_entry, n_exit), n_entry in {list(NE)}, n_exit in {list(NX)}."
        f" Benchmark {BENCH}.")
    say("Sharpe = annualised Sharpe of daily returns above T-bills. Costs per side: stocks/ETFs 0.03%, crypto 0.15%.")
    say("CAGR_tax_%: strategies 35% on each calendar year's growth, losses carried (flip_delay.stats); buy & hold 20%"
        " once at the end.")
    say("trades_per_yr: orders per member per year (each weight change counts once, a 0.5 split step included).")
    say("Choices the pre-registration leaves open (fixed before the first full run; see the module docstring):")
    say("  P2 candidates need 252 daily returns before 1 January and a close in the 7 days before it; top ceil(n/5) held.")
    say("  Reality check statistic: max over the 36 variants of (Sharpe - Sharpe split(5,5)), recentred, common indices.")
    say("  ETFs pay the stock cost (0.03%); crypto pays 0.15% for every coin incl. BTC/ETH (earlier studies: 0.10%).")
    say("  A member-year needs more than 20 bars up to 2026-09-30. OOS halves = first / second half of OOS days.")
    say("  Seeds: OOS tests 1/2/3, reality checks 11/12/13, secondary 21-25; reported-only: reality-check seed"
        " sensitivity 111-115/121-125/131-135, exploratory split(5,8) test 31-33.")
    say()
    say("AUDIT CORRECTIONS (after the first full run on 2026-10-19; the pre-registered design is unchanged)")
    say("  - Reality-check bug, fixed: the first run selected R[grid + ['split(5,5)']] although split(5,5) is in the grid."
        " pandas expands a")
    say("    duplicated label into every copy, so the column used as the benchmark was split(12,20) (the last grid"
        " variant) and split(12,20)")
    say("    fell out of the candidates. First-run rows, all wrong: V_obs 0.0365 / 0.0445 / 0.2172, argmax split(8,12) /"
        " split(5,12) / split(1,2),")
    say("    p 0.422 / 0.381 / 0.080 (P1 / P2 / P3); P3's c2 'pass' came from the bug. Now the benchmark is stacked"
        " separately, the column layout")
    say("    and the benchmark's own zero gain are asserted, and the check is rerun with the same seeds 11/12/13. Other"
        " numbers are unchanged (to 1e-12, float summation order).")
    say("  - Added after the audit, descriptive only: an OOS surface reading per sample, reality-check seed sensitivity,"
        " and an exploratory")
    say("    (not pre-registered) OOS test of split(5,8) vs split(5,5). None of these can change a default.")
    say()
    say("KNOWN LIMITATIONS OF THE INHERITED UNIVERSE (identical for all 36 variants; audit counts)")
    say("  - quality_filter(keep_collapsed=True) judges each whole series, later data included: a series that collapses"
        " later is cut 20 bars")
    say("    after its first fall below 10% of its running peak, which can drop earlier member-years. 33 S&P member-years"
        " (9 names, e.g. CHK")
    say("    2007-2018, GNW 2009-2015, DYN 2003-2009) are lost this way, and these names cannot enter P2 in those years.")
    say("  - A member-year needs more than 20 bars in the year, which uses data after 1 January: about 20 P1 member-years"
        " (about 10 in P2) of")
    say("    early-year acquisitions/delistings are excluded (e.g. MERQ, RBK, SEBL, BRCM, STJ, CXO).")
    say("  - altcoins.tiers_for_year needs a bar in 1-4 January; with data cut at 1 January + 3 days the crypto membership"
        " is identical in all 8 years.")
    say("  - Together about 0.2-0.3% of member-years: they move absolute basket levels slightly, not the differences"
        " between variants.")
    say()

    # ---------------- data
    from screener.data import from_csv_folder, quality_filter
    from analysis_2026.altcoins import load_crypto, tiers_for_year
    sp, _ = quality_filter(from_csv_folder(ROOT / "data" / "universe_pit_all"), keep_collapsed=True)
    sp = {k: v[["open", "high", "low", "close"]] for k, v in sp.items() if k != "SPY" and len(v) > 300}
    mem = pd.read_csv(ROOT / "data" / "universe_pit_all" / "members.csv", parse_dates=["start", "end"])
    yrs_sp = list(range(2001, 2027))
    mby = {y: list(dict.fromkeys(mem[(mem.start <= f"{y}-01-01") & (mem.end.isna() | (mem.end >= f"{y}-01-01"))]
                                 .symbol.str.upper())) for y in yrs_sp}
    if args.max_symbols:
        keep = set(sorted(sp)[:args.max_symbols])
        sp = {k: v for k, v in sp.items() if k in keep}
    log(f"S&P data: {len(sp)} series")
    validate(say, {s: sp[s] for s in ("AAPL", "GE") if s in sp})
    say()
    hv, hv_info = high_vol_members(sp, mby, yrs_sp)
    cd = load_crypto()
    cdat = {k: v[["open", "high", "low", "close"]] for k, v in cd.items()}
    yrs_c = list(range(2019, 2027))
    cby = {}
    for y in yrs_c:
        t = tiers_for_year(cd, y)
        cby[y] = t["1-10"] + t["11-30"][:10]
    log(f"crypto data: {len(cdat)} series")

    old_cr = lambda s: 0.0010 if s.split("#")[0] in ("BTC", "ETH") else 0.0015      # noqa: E731 (validation)
    books = {"P1": (sp, mby, yrs_sp, lambda s: C_STOCK), "P2": (sp, hv, yrs_sp, lambda s: C_STOCK),
             "P3": (cdat, cby, yrs_c, lambda s: C_CRYPTO), "P3_095": (cdat, cby, yrs_c, lambda s: C_CRYPTO_HI),
             "P3_val": (cdat, cby, yrs_c, old_cr)}
    yidx, inc = {}, {}
    for bk, (data, members, years, _) in books.items():
        yi, ic = year_index(data, members, years)
        for y in yi:
            yidx[(bk, y)] = yi[y]; inc[(bk, y)] = ic[y]
    # symbol -> {book: (cost, years)}
    per_sym = {}
    for (bk, y), mems in inc.items():
        data, _, _, cf = books[bk]
        for s in mems:
            src = "sp" if data is sp else "cr"
            e = per_sym.setdefault((src, s), {})
            if bk not in e:
                e[bk] = (cf(s), [])
            e[bk][1].append(y)
    syms = sorted(per_sym, key=lambda k: -len((sp if k[0] == "sp" else cdat)[k[1]]) * len({c for c, _ in per_sym[k].values()}))
    nchunks = max(1, min(8 * args.workers, len(syms)))
    chunks = [syms[i::nchunks] for i in range(nchunks)]
    tasks = []
    for ch in chunks:
        if not ch:
            continue
        items = [(s, (sp if src == "sp" else cdat)[s], per_sym[(src, s)]) for src, s in ch]
        keys = {(bk, y) for _, _, bks in items for bk, (_, ys) in bks.items() for y in ys}
        tasks.append((items, {k: yidx[k] for k in keys}))
    asset_tasks = [("etf13", s, load_etf(s), [C_STOCK], 252, "2005-01-01") for s in ETF13] + \
                  [("crypto21", s, load_crypto_daily(s), [C_CRYPTO, C_CRYPTO_HI], 365, "2018-01-01") for s in LARGE20 + ["ZEC"]]
    log(f"{len(syms)} basket symbols in {len(tasks)} chunks, {len(asset_tasks)} per-asset runs, {args.workers} workers")

    acc = {}
    with Pool(args.workers) as pool:
        for k, part in enumerate(pool.imap_unordered(run_chunk, tasks), 1):
            merge(acc, part)
            if k % max(1, len(tasks) // 20) == 0 or k == len(tasks):
                log(f"basket chunks {k}/{len(tasks)}")
        arows = [r for rows in pool.map(asset_task, asset_tasks) for r in rows]
    log("signals and returns done")

    B = {bk: assemble(acc, bk, yidx) for bk in books}

    # ---------------- pipeline reproduction checks
    say("PIPELINE CHECKS")
    for bk, (Rd, Rh, _) in B.items():
        dd = float(np.nanmax(np.abs(Rd[CHECK] - Rd["immediate"]))); dh = float(np.nanmax(np.abs(Rh[CHECK] - Rh["immediate"])))
        say(f"  {bk}: basket with tranche 2 at (1,1) minus immediate: max |diff| daily {dd:.1e}, held {dh:.1e}")
        if dd > 1e-12 or dh > 1e-12:
            raise SystemExit("tranche 2 at (1,1) does not reproduce immediate")
    old = pd.read_csv(ROOT / "analysis_2026" / "results_delay" / "baskets.csv")
    for n, v in [(1, "immediate"), (5, "confirm5")]:
        o = old[(old["class"] == "sp500 basket") & (old.N == n)].iloc[0]
        s = summarise(B["P1"][0][v], 252, rf_daily(B["P1"][0].index))
        say(f"  P1 {v} vs results_delay/baskets.csv N={n}: Sharpe(total) {s['Sharpe']:.4f} vs {o.Sharpe:.4f}, "
            f"CAGR {s['CAGR_%']:.3f} vs {o['CAGR_%']:.3f}, maxDD {s['maxDD_%']:.2f} vs {o['maxDD_%']:.2f}")
    ref_txt = {("daily", "immediate"): (48.72, 1.07), ("daily", BENCH): (42.72, 0.98), ("daily", "confirm5"): (34.59, 0.81),
               ("held", "immediate"): (53.67, 1.14), ("held", BENCH): (49.91, 1.08), ("held", "confirm5"): (42.83, 0.93)}
    for (how, v), (cg, shx) in ref_txt.items():
        R = B["P3_val"][0 if how == "daily" else 1]
        s = summarise(R[v], 365, rf_daily(R.index))
        say(f"  P3 at flip_delay's crypto costs, {how}, {v} vs results_agentic_modes/split_crypto.txt: "
            f"CAGR {s['CAGR_%']:.2f} vs {cg:.2f}, Sharpe {s['Sharpe_xs']:.2f} vs {shx:.2f}")
    say()

    # ---------------- metrics for every book, construction, window
    mrows = []
    for bk, (Rd, Rh, tr) in B.items():
        if bk == "P3_val":
            continue
        cfg = SAMPLES[SECONDARY_BOOKS.get(bk, bk)]
        for how, R in (("daily", Rd), ("held", Rh)):
            rf = rf_daily(R.index)
            for wn in ("full", "is", "oos"):
                a, b = cfg[wn]
                t = window_rows(R, rf, tr, cfg["ppy"], a, b)
                mrows.append(t.assign(book=bk, construction=how, window=wn, start=str(R.loc[a:b].index[0].date()),
                                      end=str(R.loc[a:b].index[-1].date())))
    M = pd.concat(mrows, ignore_index=True)
    M = M[M.variant != CHECK]
    lead = ["book", "construction", "window", "start", "end", "variant", "n_entry", "n_exit"]
    M = M[lead + [c for c in M.columns if c not in lead]]

    def tab(bk, how, wn):
        return M[(M.book == bk) & (M.construction == how) & (M.window == wn)]

    # ---------------- primary tests
    prim, ps, rc_seeds = {}, {}, {}
    for P, cfg in SAMPLES.items():
        Rd = B[P][0]
        rf = rf_daily(Rd.index)
        ti = tab(P, "daily", "is").set_index("variant")
        to = tab(P, "daily", "oos").set_index("variant")
        best = ti.loc[GRIDN, "Sharpe"].idxmax()
        a, b = cfg["oos"]
        t = boot_sharpe_gain(Rd.loc[a:b, best], Rd.loc[a:b, BENCH], rf.loc[a:b], cfg["ppy"], cfg["block"], n=N_BOOT,
                             seed=cfg["seed"])
        log(f"{P} OOS test done")
        rc = reality_check(Rd.loc[cfg["full"][0]:cfg["full"][1]], rf.loc[cfg["full"][0]:cfg["full"][1]], GRIDN, BENCH,
                           cfg["ppy"], cfg["block"], seed=cfg["rc_seed"])
        log(f"{P} reality check done")
        k0 = cfg["rc_seed"] * 10 + 1                                       # 111-115 / 121-125 / 131-135
        rc_alt = [reality_check(Rd.loc[cfg["full"][0]:cfg["full"][1]], rf.loc[cfg["full"][0]:cfg["full"][1]], GRIDN,
                                BENCH, cfg["ppy"], cfg["block"], seed=s)["p_rc"] for s in range(k0, k0 + 5)]
        rc_seeds[P] = (k0, rc_alt)
        prim[P] = {"sample": P, "best_IS": best, "IS_Sharpe_best": ti.loc[best, "Sharpe"], "IS_Sharpe_bench": ti.loc[BENCH, "Sharpe"],
                   "OOS_Sharpe_best": to.loc[best, "Sharpe"], "OOS_Sharpe_bench": to.loc[BENCH, "Sharpe"],
                   "OOS_dSharpe": t["dSharpe"], "p_one_sided": t["p_one_sided"], "half1": t["half1"], "half2": t["half2"],
                   "ci95_lo": t["ci95"][0], "ci95_hi": t["ci95"][1], "mde80_a05": t["mde80_a05"],
                   "OOS_maxDD_best": to.loc[best, "maxDD_%"], "OOS_maxDD_bench": to.loc[BENCH, "maxDD_%"],
                   "OOS_CAGR_best": to.loc[best, "CAGR_%"], "OOS_CAGR_bench": to.loc[BENCH, "CAGR_%"],
                   "OOS_CAGR_tax_best": to.loc[best, "CAGR_tax_%"], "OOS_CAGR_tax_bench": to.loc[BENCH, "CAGR_tax_%"],
                   "RC_V_obs": rc["V_obs"], "RC_argmax_full": rc["argmax"], "p_RC": rc["p_rc"], "RC_boot_q95": rc["boot_q95"]}
        ps[P] = t["p_one_sided"]
    adj = holm(ps)
    for P, d in prim.items():
        d["p_holm"] = adj[P]
        d["c1_OOS_gain_sig"] = bool(d["OOS_dSharpe"] > 0 and d["p_holm"] < 0.05)
        d["c2_RC"] = bool(d["p_RC"] < 0.10)
        d["c3_both_halves"] = bool(d["half1"] > 0 and d["half2"] > 0)
        d["c4_maxDD"] = bool(d["OOS_maxDD_best"] >= d["OOS_maxDD_bench"] - 5)
        d["PASS"] = bool(d["best_IS"] != BENCH and d["c1_OOS_gain_sig"] and d["c2_RC"] and d["c3_both_halves"] and d["c4_maxDD"])
    PT = pd.DataFrame(prim.values())

    # ---------------- secondary: held baskets and crypto at 0.95% (IS-best vs split(5,5) on OOS, unadjusted)
    sec = []
    seed = 21
    for bk, how in [("P1", "held"), ("P2", "held"), ("P3", "held"), ("P3_095", "daily"), ("P3_095", "held")]:
        cfg = SAMPLES[SECONDARY_BOOKS.get(bk, bk)]
        R = B[bk][0 if how == "daily" else 1]
        rf = rf_daily(R.index)
        ti = tab(bk, how, "is").set_index("variant"); to = tab(bk, how, "oos").set_index("variant")
        tf = tab(bk, how, "full").set_index("variant")
        best = ti.loc[GRIDN, "Sharpe"].idxmax()
        a, b = cfg["oos"]
        t = boot_sharpe_gain(R.loc[a:b, best], R.loc[a:b, BENCH], rf.loc[a:b], cfg["ppy"], cfg["block"], n=N_BOOT, seed=seed)
        seed += 1
        sec.append({"book": bk, "construction": how, "best_IS": best, "full_best": tf.loc[GRIDN, "Sharpe"].idxmax(),
                    "full_Sharpe_best_of_grid": tf.loc[GRIDN, "Sharpe"].max(), "full_Sharpe_bench": tf.loc[BENCH, "Sharpe"],
                    "OOS_dSharpe": t["dSharpe"], "p_one_sided": t["p_one_sided"], "half1": t["half1"], "half2": t["half2"],
                    "OOS_maxDD_best": to.loc[best, "maxDD_%"], "OOS_maxDD_bench": to.loc[BENCH, "maxDD_%"]})
    ST = pd.DataFrame(sec)
    log("secondary basket tests done")

    # ---------------- secondary: per asset
    A = pd.DataFrame(arows)
    A = A[A.variant != CHECK]
    med = []
    for (cls, cost), g in A.groupby(["class", "cost_%"]):
        base = g[g.variant == BENCH].set_index("asset")
        for v, x in g.groupby("variant", sort=False):
            x = x.set_index("asset")
            dS = (x.Sharpe - base.Sharpe.reindex(x.index)).dropna()
            med.append({"class": cls, "cost_%": cost, "variant": v, "assets": len(x), "median_Sharpe": x.Sharpe.median(),
                        "median_dSharpe_vs_bench": dS.median(), "better_than_bench": f"{int((dS > 0).sum())}/{len(dS)}",
                        "median_CAGR_%": x["CAGR_%"].median(), "median_CAGR_tax_%": x["CAGR_tax_%"].median(),
                        "median_maxDD_%": x["maxDD_%"].median(),
                        "median_trades_per_yr": x["trades_per_yr"].median() if "trades_per_yr" in x else np.nan})
    AM = pd.DataFrame(med)

    # ---------------- write tables
    M.to_csv(out / "metrics.csv", index=False)
    srows = []
    for (bk, how, wn), g in M.groupby(["book", "construction", "window"]):
        for m in METRICS:
            s = surface(g, m)
            for ne, row in s.iterrows():
                srows.append({"book": bk, "construction": how, "window": wn, "metric": m, "n_entry": ne,
                              **{f"n_exit={c}": row[c] for c in s.columns}})
    pd.DataFrame(srows).to_csv(out / "surfaces.csv", index=False)
    io = []
    for P in SAMPLES:
        ti = tab(P, "daily", "is").set_index("variant"); to = tab(P, "daily", "oos").set_index("variant")
        x = pd.DataFrame({"IS_Sharpe": ti.Sharpe, "OOS_Sharpe": to.Sharpe, "OOS_dSharpe_vs_bench": to.Sharpe - to.loc[BENCH, "Sharpe"],
                          "IS_CAGR_%": ti["CAGR_%"], "OOS_CAGR_%": to["CAGR_%"], "IS_CAGR_tax_%": ti["CAGR_tax_%"],
                          "OOS_CAGR_tax_%": to["CAGR_tax_%"], "IS_maxDD_%": ti["maxDD_%"], "OOS_maxDD_%": to["maxDD_%"],
                          "IS_trades_per_yr": ti.trades_per_yr, "OOS_trades_per_yr": to.trades_per_yr})
        x["IS_rank"] = x.loc[GRIDN, "IS_Sharpe"].rank(ascending=False)
        io.append(x.reset_index().assign(sample=P))
    IO = pd.concat(io, ignore_index=True)
    IO = IO[["sample"] + [c for c in IO.columns if c != "sample"]]
    IO.to_csv(out / "is_oos.csv", index=False)
    PT.to_csv(out / "primary_tests.csv", index=False)
    PT[["sample", "RC_V_obs", "RC_argmax_full", "p_RC", "RC_boot_q95"]].to_csv(out / "reality_check.csv", index=False)
    ST.to_csv(out / "secondary_basket_tests.csv", index=False)
    A.to_csv(out / "secondary_per_asset.csv", index=False)
    AM.to_csv(out / "secondary_per_asset_medians.csv", index=False)
    hv_info.to_csv(out / "p2_members.csv", index=False)
    mcount = pd.DataFrame([{"book": bk, "year": y, "members": B[bk][2].loc[y, "members"]} for bk in ("P1", "P2", "P3") for y in B[bk][2].index])
    mcount.to_csv(out / "members_per_year.csv", index=False)
    for P in SAMPLES:
        B[P][0][[c for c in COLS if c != CHECK]].to_csv(out / f"basket_returns_{P}.csv.gz", float_format="%.8g")

    # ---------------- summary text
    f2 = lambda x: f"{x:,.2f}"                                                        # noqa: E731
    for P, cfg in SAMPLES.items():
        tf = tab(P, "daily", "full")
        say("=" * 100)
        say(f"{P}: {cfg['label']}, {tf.start.iloc[0]}..{tf.end.iloc[0]} (daily-rebalanced equal weight; members per year "
            f"{int(B[P][2].members.min())}-{int(B[P][2].members.max())})")
        for m, nd, txt in [("Sharpe", 3, "Sharpe above T-bills"), ("CAGR_%", 2, "CAGR %"), ("CAGR_tax_%", 2, "after-tax CAGR %"),
                           ("maxDD_%", 1, "max drawdown %"), ("trades_per_yr", 1, "orders per member per year")]:
            say(fmt_surface(tf, m, f"\n{P} FULL SAMPLE, {txt} (rows n_entry, columns n_exit of tranche 2)", nd))
        for wn in ("is", "oos"):
            tw = tab(P, "daily", wn)
            say(fmt_surface(tw, "Sharpe", f"\n{P} {wn.upper()} {tw.start.iloc[0]}..{tw.end.iloc[0]}, Sharpe above T-bills", 3))
        s = surface(tf, "Sharpe")
        say(f"\n{P} surface shape (full sample Sharpe): grid range {s.min().min():.3f}..{s.max().max():.3f}; "
            f"{BENCH} {s.loc[5, 5]:.3f}; variants within 0.03 of it: {int((s.sub(s.loc[5, 5]).abs() <= 0.03).sum().sum())}/36")
        say("  mean by n_entry: " + ", ".join(f"{k}: {v:.3f}" for k, v in s.mean(axis=1).items()))
        say("  mean by n_exit:  " + ", ".join(f"{k}: {v:.3f}" for k, v in s.mean(axis=0).items()))
        rf_ = tf.set_index("variant")["Sharpe"]
        say(f"  references (not candidates): confirm5 {rf_['confirm5']:.3f}, immediate {rf_['immediate']:.3f}, "
            f"buy & hold {rf_['BH']:.3f}; best grid variant {vname(*s.stack().idxmax())} {s.max().max():.3f}")
        say(f"\n{P} IS / OOS (daily), IS-best variant, benchmark and references:")
        x = IO[IO["sample"] == P].set_index("variant")
        best = prim[P]["best_IS"]
        keep = list(dict.fromkeys([best, BENCH, "immediate", "confirm5", "BH"]))
        say(x.loc[keep].drop(columns=["sample"]).to_string(float_format=f2))
        top = x.loc[GRIDN].sort_values("IS_Sharpe", ascending=False).head(5)
        say(f"  IS top 5 by Sharpe: " + "; ".join(f"{v} IS {r.IS_Sharpe:.3f} / OOS {r.OOS_Sharpe:.3f}" for v, r in top.iterrows()))
        say()

    say("=" * 100)
    say("PRIMARY TESTS: IS-best variant vs split(5,5) on OOS (Sharpe gain above T-bills; paired stationary bootstrap,"
        f" {N_BOOT} draws, mean block 250 trading / 180 calendar days, null-centred, one-sided; Holm across P1-P3)")
    cols_pt = ["sample", "best_IS", "IS_Sharpe_best", "IS_Sharpe_bench", "OOS_Sharpe_best", "OOS_Sharpe_bench", "OOS_dSharpe",
               "p_one_sided", "p_holm", "half1", "half2", "ci95_lo", "ci95_hi", "OOS_maxDD_best", "OOS_maxDD_bench"]
    say(PT[cols_pt].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    say("\nWHITE REALITY CHECK, full sample, 36-variant grid vs split(5,5) (max Sharpe gain; recentred stationary"
        f" bootstrap, {N_BOOT} draws, same blocks)")
    say(PT[["sample", "RC_V_obs", "RC_argmax_full", "p_RC", "RC_boot_q95"]].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    say("  seed sensitivity (reported only; the decision uses seeds 11/12/13): "
        + "; ".join(f"{P} seeds {k0}-{k0 + 4}: p {min(ps_):.3f}..{max(ps_):.3f}" for P, (k0, ps_) in rc_seeds.items()))
    say("\nDECISION CRITERIA (all must hold): c1 OOS gain > 0 with Holm p < 0.05; c2 reality-check p < 0.10;"
        " c3 gain > 0 in both OOS halves; c4 OOS maxDD no more than 5 points worse")
    say(PT[["sample", "best_IS", "c1_OOS_gain_sig", "c2_RC", "c3_both_halves", "c4_maxDD", "PASS"]].to_string(index=False))
    say("\nVERDICTS")
    for P, d in prim.items():
        if d["PASS"]:
            say(f"  {P}: PASS - {d['best_IS']} beats {BENCH} on every criterion.")
        else:
            why = [n for n, k in [(f"OOS gain {d['OOS_dSharpe']:+.3f} with Holm p {d['p_holm']:.3f} (needs > 0 and < 0.05)", "c1_OOS_gain_sig"),
                                  (f"reality check p {d['p_RC']:.3f} (needs < 0.10)", "c2_RC"),
                                  (f"OOS halves {d['half1']:+.3f} / {d['half2']:+.3f} (both must be > 0)", "c3_both_halves"),
                                  (f"OOS maxDD {d['OOS_maxDD_best']:.1f}% vs {d['OOS_maxDD_bench']:.1f}% (at most 5 pts worse)", "c4_maxDD")]
                   if not d[k]]
            if d["best_IS"] == BENCH:
                why = [f"the IS-best variant is {BENCH} itself"]
            say(f"  {P}: no change - {'; '.join(why)}.")
    stock = [P for P in ("P1", "P2") if prim[P]["PASS"]]
    say(f"  Stock default: {'CHANGES to ' + ', '.join(prim[P]['best_IS'] + ' (' + P + ')' for P in stock) if stock else BENCH + ' stays'}.")
    say(f"  Crypto default: {'CHANGES to ' + prim['P3']['best_IS'] if prim['P3']['PASS'] else BENCH + ' stays'}.")

    # ---------------- descriptive OOS reading and one exploratory test (added after the audit; never decides)
    say("\n" + "=" * 100)
    say("OOS SURFACE READING (descriptive, added after the audit; selection is IS-only, so picking a variant from"
        " these OOS numbers would")
    say("be OOS selection, not a test)")
    for P in SAMPLES:
        x = IO[IO["sample"] == P].set_index("variant").loc[GRIDN]
        bo = x.loc[BENCH, "OOS_Sharpe"]
        beat = x[x.OOS_Sharpe > bo].sort_values("OOS_Sharpe", ascending=False)
        best = prim[P]["best_IS"]
        so, si = surface(tab(P, "daily", "oos"), "Sharpe"), surface(tab(P, "daily", "is"), "Sharpe")
        say(f"  {P}: {len(beat)}/35 other variants beat {BENCH} OOS ({bo:.3f}), so its OOS rank is {len(beat) + 1}/36;"
            " best OOS: " + ", ".join(f"{v} {r.OOS_Sharpe:.3f}" for v, r in beat.head(3).iterrows())
            + f". IS-best {best} OOS {x.loc[best, 'OOS_Sharpe']:.3f}, OOS rank {int((x.OOS_Sharpe > x.loc[best, 'OOS_Sharpe']).sum()) + 1}/36.")
        say("      OOS mean by n_entry: " + ", ".join(f"{k}: {v:.3f}" for k, v in so.mean(axis=1).items()))
        say("      OOS mean by n_exit:  " + ", ".join(f"{k}: {v:.3f}" for k, v in so.mean(axis=0).items()))
        for nm, s_ in (("IS", si), ("OOS", so)):
            d8, d12 = s_[8] - s_[5], s_[12] - s_[5]
            say(f"      {nm:>3} exit 8 minus exit 5 by n_entry: " + " ".join(f"{v:+.3f}" for v in d8)
                + f" ({int((d8 > 0).sum())}/6 > 0); exit 12 minus exit 5: " + " ".join(f"{v:+.3f}" for v in d12)
                + f" ({int((d12 > 0).sum())}/6 > 0)")
    say("\nEXPLORATORY (not pre-registered, chosen after seeing the surfaces): split(5,8) vs split(5,5) on OOS, same"
        f" paired stationary bootstrap, {N_BOOT} draws, seeds 31-33, one-sided, unadjusted")
    for k, (P, cfg) in enumerate(SAMPLES.items()):
        Rd = B[P][0]
        rf = rf_daily(Rd.index)
        a, b = cfg["oos"]
        t = boot_sharpe_gain(Rd.loc[a:b, vname(5, 8)], Rd.loc[a:b, BENCH], rf.loc[a:b], cfg["ppy"], cfg["block"], n=N_BOOT,
                             seed=31 + k)
        tf_ = tab(P, "daily", "full").set_index("variant")
        say(f"  {P}: OOS dSharpe {t['dSharpe']:+.4f}, p {t['p_one_sided']:.4f}, halves {t['half1']:+.3f} / {t['half2']:+.3f},"
            f" 95% CI {t['ci95'][0]:+.3f}..{t['ci95'][1]:+.3f}, MDE80 {t['mde80_a05']:.3f}; full-sample maxDD"
            f" {tf_.loc[vname(5, 8), 'maxDD_%']:.1f}% vs {tf_.loc[BENCH, 'maxDD_%']:.1f}%")

    say("\n" + "=" * 100)
    say("SECONDARY (reported only, never decides anything)")
    say("\nHeld baskets (equal money per member on 1 January, then drifting) and the crypto basket at 0.95%/side:"
        " IS-best vs split(5,5) on OOS, unadjusted")
    say(ST.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    for bk, how in [("P1", "held"), ("P2", "held"), ("P3", "held"), ("P3_095", "daily"), ("P3_095", "held")]:
        say(fmt_surface(tab(bk, how, "full"), "Sharpe", f"\n{bk} {how}, full sample, Sharpe above T-bills", 3))
    say(fmt_surface(tab("P3_095", "daily", "full"), "CAGR_tax_%", "\nP3_095 daily, full sample, after-tax CAGR %", 2))
    for (cls, cost), g in AM.groupby(["class", "cost_%"]):
        gg = g.set_index("variant")
        sv = gg.loc[GRIDN, "median_Sharpe"]
        say(f"\nPer asset, {cls} at {cost:.2f}%/side ({int(gg.assets.max())} assets, 120-bar warm-up, to 2026-09):"
            f" median Sharpe surface; best median {sv.idxmax()} {sv.max():.3f}, {BENCH} {sv[BENCH]:.3f}")
        tmp = gg.reset_index().rename(columns={"median_Sharpe": "Sharpe"})
        tmp["n_entry"] = tmp.variant.map(lambda v: int(v[6:-1].split(",")[0]) if v.startswith("split(") else np.nan)
        tmp["n_exit"] = tmp.variant.map(lambda v: int(v[6:-1].split(",")[1]) if v.startswith("split(") else np.nan)
        say(fmt_surface(tmp, "Sharpe", "  median Sharpe above T-bills", 3))
        tmp["dS"] = tmp["median_dSharpe_vs_bench"]
        tmp["nb"] = tmp.better_than_bench.map(lambda s: int(s.split("/")[0]))
        say(fmt_surface(tmp.assign(Sharpe=tmp["dS"]), "Sharpe", "  median per-asset Sharpe change vs split(5,5)", 3)
            .replace("references:", "references (vs split(5,5)):"))
        nb = tmp[tmp.variant.isin(GRIDN)].pivot_table(index="n_entry", columns="n_exit", values="nb").reindex(index=list(NE), columns=list(NX))
        say("  assets better than split(5,5):\n" + nb.astype(int).to_string())
        say(fmt_surface(tmp.rename(columns={"Sharpe": "_s", "median_CAGR_tax_%": "Sharpe"}), "Sharpe", "  median after-tax CAGR %", 2))
    say(f"\nRuntime {time.time() - t0:.0f} s with {args.workers} workers.")
    (out / "summary.txt").write_text("\n".join(lines) + "\n")
    log("done")


if __name__ == "__main__":
    main()
