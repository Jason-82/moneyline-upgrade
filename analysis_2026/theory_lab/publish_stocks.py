"""Publish only reproducible aggregate stock research outputs.

Example:
  python -m analysis_2026.theory_lab.publish_stocks --source private/stock_results \
      --output analysis_2026/results_theory_lab

This never runs a strategy or exports individual stock price observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


COPY_NAMES = ("stock_metrics.csv", "stock_coverage.csv", "stock_calendar_years.csv", "stock_receipt.json")
PUBLISH_NAMES = (*COPY_NAMES, "stock_monthly_primary.csv", "stock_unknown_events.csv")
UNKNOWN_COLUMNS = ("date", "event", "ticker", "gap_type", "period", "strategy", "delay_sessions", "missing_policy")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_stock_outputs(source: str | Path, output: str | Path) -> dict:
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("Publication output must differ from the full source folder")
    receipt_path = source / "stock_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    # Verify the exact source inputs to this transform before producing files.
    for name in (*COPY_NAMES[:-1], "stock_monthly.csv", "stock_events.csv"):
        if sha256(source / name) != receipt["output_sha256"][name]:
            raise ValueError(f"Source output hash mismatch: {name}")
    output.mkdir(parents=True, exist_ok=True)
    for name in COPY_NAMES:
        shutil.copy2(source / name, output / name)
    monthly = pd.read_csv(source / "stock_monthly.csv")
    primary = monthly[
        np.isclose(monthly.cost_per_side_bps, 3)
        & (monthly.delay_sessions == 1)
        & (monthly.annual_gain_levy_rate == 0)
        & (monthly.terminal_gain_levy_rate == 0)
        & (monthly.cash_yield == 0)
    ]
    primary.to_csv(output / "stock_monthly_primary.csv", index=False)
    events = pd.read_csv(source / "stock_events.csv")
    unknown = events[events.event.isin(["unpriced_exposure", "selected_allocation_zero_writeoff"])]
    unknown = unknown[list(UNKNOWN_COLUMNS)].drop_duplicates()
    unknown.to_csv(output / "stock_unknown_events.csv", index=False)
    manifest = {
        "prereg_commit": "f496b9d",
        "implementation_sha256": receipt["implementation_sha256"],
        "source_receipt_sha256": sha256(output / "stock_receipt.json"),
        "publication_transform": {
            "stock_monthly_primary.csv": "cost_per_side_bps approximately3,delay_sessions1,annual_gain_levy_rate0,terminal_gain_levy_rate0,cash_yield0; both policies; status column retained; unidentified partial histories not evidence",
            "stock_unknown_events.csv": "unpriced_exposure or selected_allocation_zero_writeoff; unique date,event,ticker,gap_type,period,strategy,delay_sessions,missing_policy, combining fees/tax/cash stress",
        },
        "published_sha256": {name: sha256(output / name) for name in PUBLISH_NAMES},
        "qualification": "C1 and C2 full/later strict histories UNIDENTIFIED; no significance calculation is valid for primary hypotheses",
    }
    (output / "stock_public_receipt.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Full, receipt-verified private stock_results folder")
    parser.add_argument("--output", required=True, help="Public aggregate output folder")
    args = parser.parse_args()
    manifest = publish_stock_outputs(args.source, args.output)
    print(json.dumps({"published_files": list(manifest["published_sha256"]), "source_receipt_sha256": manifest["source_receipt_sha256"]}))


if __name__ == "__main__":
    main()
