"""
Daily screener for the indicator, like Ivan on Tech's site: what flipped today,
days since the flip, move since the flip, distance to the line.

Computes the exact indicator (analysis_2026/moneyline_ref.py: Wilder ATR(10) x 2.0
around hl2, reset-on-flip) on CLOSED daily bars. Make sure the last bar in the data
is a closed session - drop today's row if you run it during market hours.

    python -m screener.scan --csv-folder data/universe              # all symbols
    python -m screener.scan --csv-folder data/universe --flipped today
    python -m screener.scan --csv-folder data/universe --state green --max-days 20
    python -m screener.scan --csv-folder data/universe --whitelist screener/whitelist.txt

Output columns:
  state            GREEN / RED on the last closed bar
  flip_today       GREEN, RED or blank
  days_in_state    trading days since the last flip (0 = flipped on the last bar)
  pct_since_flip   close vs the close on the flip bar
  dist_to_line_%   (close - line) / close; for GREEN this is roughly the drop that
                   would turn it red (exits fill past the line - see HANDOFF 5.8)
  atr10_%          ATR(10) / close, a volatility gauge
  validated        on the whitelist produced by the selection procedure
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline  # noqa: E402
from screener.data import from_csv_folder, from_robinhood_json  # noqa: E402


def scan_one(sym: str, df: pd.DataFrame) -> dict | None:
    if len(df) < 250:
        return None                          # the line needs ~150-250 bars to settle
    m = moneyline(df)
    g = m.green.to_numpy(bool); line = m.line.to_numpy(float); c = df.close.to_numpy(float)
    flips = np.where(m.flip.to_numpy() != 0)[0]
    last_flip = flips[-1] if len(flips) else None
    i = len(df) - 1
    return {
        "symbol": sym,
        "date": df.index[-1].date(),
        "close": c[i],
        "state": "GREEN" if g[i] else "RED",
        "flip_today": ("GREEN" if g[i] else "RED") if last_flip == i else "",
        "days_in_state": (i - last_flip) if last_flip is not None else np.nan,
        "pct_since_flip": (c[i] / c[last_flip] - 1) * 100 if last_flip is not None else np.nan,
        "line": line[i],
        "dist_to_line_%": (c[i] - line[i]) / c[i] * 100,
        "atr10_%": m.atr.iloc[-1] / c[i] * 100,
    }


def scan(data: dict[str, pd.DataFrame], whitelist: set[str] | None = None) -> pd.DataFrame:
    rows = [r for s, df in data.items() if (r := scan_one(s, df))]
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["validated"] = out.symbol.isin(whitelist) if whitelist else False
    # freshest flips first, then by state
    return out.sort_values(["days_in_state", "symbol"]).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv-folder")
    src.add_argument("--robinhood-json", help="saved raw get_equity_historicals result")
    ap.add_argument("--flipped", choices=["today"], help="only symbols that flipped on the last bar")
    ap.add_argument("--state", choices=["green", "red"])
    ap.add_argument("--max-days", type=int, help="max trading days since the flip")
    ap.add_argument("--min-pct", type=float, help="min %% move since the flip")
    ap.add_argument("--whitelist", help="file with one validated symbol per line")
    ap.add_argument("--only-validated", action="store_true")
    ap.add_argument("--out", help="write CSV here (keep it out of the public repo)")
    a = ap.parse_args()

    data = from_csv_folder(a.csv_folder) if a.csv_folder else from_robinhood_json(a.robinhood_json)
    wl = None
    if a.whitelist:
        wl = {l.strip().upper() for l in Path(a.whitelist).read_text().splitlines() if l.strip() and not l.startswith("#")}
    res = scan(data, wl)
    if res.empty:
        print("no symbols with >= 250 bars"); return
    if a.flipped == "today":
        res = res[res.flip_today != ""]
    if a.state:
        res = res[res.state == a.state.upper()]
    if a.max_days is not None:
        res = res[res.days_in_state <= a.max_days]
    if a.min_pct is not None:
        res = res[res.pct_since_flip >= a.min_pct]
    if a.only_validated:
        res = res[res.validated]
    pd.set_option("display.width", 200)
    print(res.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    n_green = (res.state == "GREEN").sum()
    print(f"\n{len(res)} symbols | {n_green} green | {(res.flip_today != '').sum()} flipped on the last bar")
    if a.out:
        res.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
