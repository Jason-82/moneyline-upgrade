"""Late entries into old-MoneyLine green runs, by how far price has risen since the flip.

Evidence for the agentic entry policy defaults: entry.max_join_bars = 20 and entry.max_join_rise_frac = 0.50
(agentic/README.md section 9). HANDOFF 5.4 measured entries by bars since the flip; this adds the rise since the
flip close, the quantity max_join_rise_frac caps.

Run from the repo root in Git Bash:
    .venv/Scripts/python.exe analysis_2026/results_late_entry/late_rise.py
Takes a minute or a few. Public market data only, but it reads the gitignored downloads data/crypto_4h,
data/crypto_binance (ZEC), data/etf and data/universe_pit_all, which a clone of the public repo does not have.

Writes
    private/late_entry/entries.parquet   every entry (about 950k rows; gitignored, never committed)
    summary.txt, tables.csv              next to this file: aggregates by asset class only

Design (the main session's analysis of 2026-10-18, unchanged)
- Old MoneyLine, N = 1 (agentic.indicator.moneyline_confirmed(df, 1, 1)), daily bars; flips from bar 120 on.
- For every green run (flip at close f, first red close x) and every day d in f..x-1: decide at close d, buy at the
  open of d+1, sell at the open of x+1. One entry per (run, d). Runs still green at the end of the data are dropped.
- Cost per side: crypto 0.10%, ETFs 0.02%, stocks 0.03%.
- rise = close[d] / close[f] - 1 (what agentic/entry.py compares with max_join_rise_frac); bars = d - f (what it
  compares with max_join_bars); dist = close[d] / line[d] - 1.
- Universe: 21 coins (flip_delay.LARGE20 + ZEC), 13 ETFs (flip_delay.ETF13), 300 random S&P 500 point-in-time
  members (numpy default_rng(0) over data/universe_pit_all, kept if > 400 bars and all closes > 0).
- Statistics, per bucket of entries:
  pooled   geometric mean per trade of all entries in the bucket, exp(mean log return) - 1, with a 95% CI clustered
           by run (entries of one run share the exit, so they are not independent; no small-sample correction).
  run      average log return per run first, then the geometric mean (run_geo) and median (run_median) across runs:
           every run counts once, however many of its days fall in the bucket.
  win      share of entries with a positive return; hold = median holding days; per_day_bp = pooled log return
           per holding day, in basis points.
- Descriptive only: no parameter was fitted to these tables. The cap table shows which entries a rise cap would
  block (bars 0-20, the window max_join_bars allows); the era table splits each class's runs at the median flip date;
  the top-runs table drops the k runs that contributed most (sum of log returns in the bucket) to show how much of a
  bucket's mean rests on a few runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentic.indicator import moneyline_confirmed  # noqa: E402
from analysis_2026.flip_delay import ETF13, LARGE20, load_crypto_daily, load_etf  # noqa: E402
from screener.data import from_csv_folder  # noqa: E402

OUT = Path(__file__).resolve().parent
ENTRIES = ROOT / "private" / "late_entry" / "entries.parquet"
STOCKS = ROOT / "data" / "universe_pit_all"
WARMUP = 120
COST = {"crypto": 0.0010, "etf": 0.0002, "stock": 0.0003}
N_STOCKS, SEED = 300, 0
CLASSES = ("crypto", "etf", "stock")

RISE_EDGES = [-np.inf, 0, 0.05, 0.10, 0.20, 0.35, 0.50, np.inf]
RISE_LABELS = ["<=0", "0-5%", "5-10%", "10-20%", "20-35%", "35-50%", ">50%"]
BARS_EDGES = [-1, 0, 5, 20, 50, np.inf]
BARS_LABELS = ["flip", "1-5", "6-20", "21-50", "51+"]
DIST_EDGES = [-np.inf, 0.05, 0.10, 0.15, 0.20, 0.30, np.inf]
DIST_LABELS = ["<5%", "5-10%", "10-15%", "15-20%", "20-30%", ">30%"]
CAPS = [None, 0.50, 0.35, 0.20, 0.10]
TOP_K = [0, 1, 3, 5, 10]


# ------------------------------------------------------------------ entries

def entries(df: pd.DataFrame, cls: str, sym: str) -> pd.DataFrame:
    """One row per (green run, entry day): decide at close d, fill at open d+1, exit at the open after the red flip."""
    m = moneyline_confirmed(df, 1, 1)
    g = m["green"].to_numpy(bool)
    line = m["line"].to_numpy(float)
    o, c = df["open"].to_numpy(float), df["close"].to_numpy(float)
    n, cost = len(c), COST[cls]
    flips = np.flatnonzero(g[1:] & ~g[:-1]) + 1
    red = np.flatnonzero(~g)
    parts = []
    for f in flips[flips >= WARMUP]:
        k = np.searchsorted(red, f)
        if k >= len(red) or red[k] >= n - 1:      # still green at the end, or no open after the red flip: no exit
            break
        x = red[k]
        d = np.arange(f, x)
        parts.append(pd.DataFrame({
            "run": f"{sym}-{f}", "flip_date": df.index[f], "date": df.index[d], "bars": d - f,
            "rise": c[d] / c[f] - 1, "dist": c[d] / line[d] - 1, "hold": x - d,
            "r": o[x + 1] / o[d + 1] * (1 - cost) ** 2 - 1}))
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    out.insert(0, "sym", sym)
    out.insert(0, "cls", cls)
    return out


def stock_sample() -> list[str]:
    files = sorted(p.name for p in STOCKS.glob("*.csv") if p.name != "members.csv")
    return [f[:-4] for f in np.random.default_rng(SEED).choice(files, N_STOCKS, replace=False)]


def build() -> tuple[pd.DataFrame, dict]:
    parts, used = [], {c: 0 for c in CLASSES}
    for s in LARGE20 + ["ZEC"]:
        try:
            parts.append(entries(load_crypto_daily(s), "crypto", s))
            used["crypto"] += 1
        except Exception as e:                    # noqa: BLE001 - report and continue
            print(f"skip crypto {s}: {e}")
    for s in ETF13:
        parts.append(entries(load_etf(s), "etf", s))
        used["etf"] += 1
    for s, df in from_csv_folder(STOCKS, stock_sample()).items():
        if len(df) > 400 and (df["close"] > 0).all():
            parts.append(entries(df, "stock", s))
            used["stock"] += 1
    D = pd.concat([p for p in parts if len(p)], ignore_index=True)
    D["lr"] = np.log1p(D["r"])
    return D, used


def save_entries(D: pd.DataFrame) -> Path:
    ENTRIES.parent.mkdir(parents=True, exist_ok=True)
    try:
        D.to_parquet(ENTRIES)
        return ENTRIES
    except ImportError:                           # no pyarrow / fastparquet
        p = ENTRIES.with_suffix(".csv.gz")
        D.to_csv(p, index=False)
        return p


# ------------------------------------------------------------------ statistics

def stats(g: pd.DataFrame, total: int | None = None) -> dict:
    run = g.groupby("run", sort=False).agg(s=("lr", "sum"), n=("lr", "size"), h=("hold", "sum"))
    n = int(run["n"].sum())
    mean = run["s"].sum() / n
    se = np.sqrt(((run["s"] - mean * run["n"]) ** 2).sum()) / n      # cluster-robust SE of the pooled mean
    per_run = run["s"] / run["n"]
    pct = lambda v: (np.exp(v) - 1) * 100                            # noqa: E731
    return {"runs": len(run), "entries": n, "share_pct": 100 * n / total if total else np.nan,
            "geo_pct": pct(mean), "ci95_lo_pct": pct(mean - 1.96 * se), "ci95_hi_pct": pct(mean + 1.96 * se),
            "run_geo_pct": pct(per_run.mean()), "run_median_pct": pct(per_run.median()),
            "win_pct": 100 * (g["lr"] > 0).mean(), "hold_median_d": g["hold"].median(),
            "per_day_bp": 1e4 * run["s"].sum() / run["h"].sum()}


def by(X: pd.DataFrame, col: str) -> list[tuple[str, dict]]:
    return [(str(k), stats(v, len(X))) for k, v in X.groupby(col, observed=True, sort=True)]


def tables(D: pd.DataFrame) -> pd.DataFrame:
    D = D.copy()
    D["rise_b"] = pd.cut(D["rise"], RISE_EDGES, labels=RISE_LABELS)
    D["bars_b"] = pd.cut(D["bars"], BARS_EDGES, labels=BARS_LABELS)
    D["dist_b"] = pd.cut(D["dist"], DIST_EDGES, labels=DIST_LABELS)
    rows = []

    def add(table, cls, items):
        rows.extend({"table": table, "cls": cls, "bucket": b, **s} for b, s in items)

    for cls in CLASSES:
        X = D[D["cls"] == cls]
        early, late = X[X["bars"].between(1, 20)], X[X["bars"] >= 21]
        add("at_flip", cls, [("bars=0", stats(X[X["bars"] == 0], len(X)))])
        add("rise_bars_1_20", cls, by(early, "rise_b"))
        add("rise_bars_21_plus", cls, by(late, "rise_b"))
        add("bars", cls, by(X, "bars_b"))
        add("dist_bars_1_20", cls, by(early, "dist_b"))
        window = X[X["bars"] <= 20]                                  # what max_join_bars = 20 allows
        for cap in CAPS:
            name = "none" if cap is None else f"{cap:.2f}"
            ok = window["rise"] <= (np.inf if cap is None else cap + 1e-12)
            add("cap_bars_0_20", cls, [(f"cap {name} allowed", stats(window[ok], len(window)))])
            if (~ok).any():
                add("cap_bars_0_20", cls, [(f"cap {name} blocked", stats(window[~ok], len(window)))])
        mid = X.groupby("run")["flip_date"].first().median()
        coarse = pd.cut(early["rise"], [-np.inf, 0.20, 0.50, np.inf], labels=["<=20%", "20-50%", ">50%"])
        for era, sel in ((f"<{mid.date()}", early["flip_date"] < mid), (f">={mid.date()}", early["flip_date"] >= mid)):
            Y = early[sel]
            add("era_rise_bars_1_20", cls,
                [(f"{era} {k}", stats(v, len(Y))) for k, v in Y.groupby(coarse[sel], observed=True, sort=True)])
        for label in RISE_LABELS[3:]:
            Y = early[early["rise_b"] == label]
            if Y.empty:
                continue
            top = Y.groupby("run")["lr"].sum().sort_values(ascending=False).index
            for k in (k for k in TOP_K if k < len(top)):
                name = f"{label} " + ("all runs" if k == 0 else f"without top {k}")
                add("drop_top_runs_bars_1_20", cls, [(name, stats(Y[~Y["run"].isin(top[:k])], len(Y)))])
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ report

TITLES = {
    "at_flip": "entry on the flip bar (bars = 0)",
    "rise_bars_1_20": "entries 1-20 bars after the flip, by rise since the flip close",
    "rise_bars_21_plus": "entries 21+ bars after the flip, by rise since the flip close",
    "bars": "all entries, by bars since the flip",
    "dist_bars_1_20": "entries 1-20 bars after the flip, by distance of the close above the line",
    "cap_bars_0_20": "entries 0-20 bars after the flip (max_join_bars = 20), allowed / blocked by a rise cap",
    "era_rise_bars_1_20": "entries 1-20 bars after the flip, runs split at the class's median flip date",
    "drop_top_runs_bars_1_20": "entries 1-20 bars after the flip, by rise, without the k runs that added the most",
}
COLS = ["bucket", "runs", "entries", "share_pct", "geo_pct", "ci95_lo_pct", "ci95_hi_pct", "run_geo_pct",
        "run_median_pct", "win_pct", "hold_median_d", "per_day_bp"]


def counts(D: pd.DataFrame, used: dict) -> pd.DataFrame:
    t = D.groupby("cls").agg(entries=("r", "size"), runs=("run", "nunique"), first_flip=("flip_date", "min"),
                             last_flip=("flip_date", "max"))
    t.insert(0, "assets", pd.Series(used))
    for c in ("first_flip", "last_flip"):
        t[c] = pd.to_datetime(t[c]).dt.date
    return t


def report(T: pd.DataFrame, cnt: pd.DataFrame) -> str:
    lines = [__doc__.strip(), "", "=" * 100, "", "Assets, runs and entries (stocks: of 300 sampled, those kept)",
             cnt.to_string(), "",
             "Columns: geo = pooled geometric mean per trade, ci95 = run-clustered 95% CI of it, run_geo / "
             "run_median = per-run average first, win = % of entries > 0, hold = median days, per_day_bp = pooled "
             "log return per holding day (bp), share = % of the table's entries for that class. All returns are "
             "per trade, after cost, in %."]
    for table, title in TITLES.items():
        lines += ["", "=" * 100, f"{table}: {title}"]
        for cls in CLASSES:
            X = T[(T["table"] == table) & (T["cls"] == cls)]
            if len(X):
                lines += ["", f"--- {cls}", X[COLS].to_string(index=False, float_format=lambda v: f"{v:.2f}")]
    return "\n".join(lines) + "\n"


def main():
    D, used = build()
    path = save_entries(D)
    T = tables(D)
    T.round(4).to_csv(OUT / "tables.csv", index=False)
    text = report(T, counts(D, used))
    (OUT / "summary.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"entries: {path.relative_to(ROOT)} (gitignored); tables: {(OUT / 'tables.csv').relative_to(ROOT)}, "
          f"{(OUT / 'summary.txt').relative_to(ROOT)}")


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    main()
