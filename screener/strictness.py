"""Compatibility entry point for corrected continuous stock-selection research.

Historical outputs from this module's independent-window engine are superseded.
Every new run uses research.run: continuous positions, cost basis, loss carry,
SPY holding benchmark, complete horizons, causal membership, and explicit data gaps.
A holdout cannot be accessed through an unguarded ``--until holdout`` switch.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from research.config import ExperimentConfig, Window
from research.data_contract import MembershipSpell, ResearchDataset, SecurityRecord
from research.selection import daily_returns, formation_scores, pick, scores_for, synthetic, window_metrics
from research.run import run_experiment, write_result
from screener.data import from_csv_folder

COST, ST, LT = 0.0003, 0.35, 0.20
CRITERIA = ["skill", "gate", "edge", "vol", "random"]
PRIMARY = "skill"
LEVELS = ["top5", "top10", "top20", "top30", "top40", ">10", "all"]
ETFS = {"SPY", "QQQ", "IWM", "DIA", "VOO", "IVV"}


def _legacy_dataset(data, spy, members=None, prices="split"):
    frames = dict(data)
    frames["SPY"] = spy
    basis = "split_only" if prices in ("split", "split_only") else "total_return"
    metadata = {"mode": "exploratory", "price_basis": basis,
                "dividends_complete": False, "terminal_complete": False,
                "universe_complete": False, "point_in_time_ids": False,
                "price_source": "caller-supplied legacy ticker data",
                "calendar_source": "caller-supplied SPY sessions",
                "dividend_source": "unavailable", "corporate_action_source": "unavailable"}
    spells = []
    if members is not None:
        for row in members.to_dict("records"):
            sid = str(row.get("security_id", row.get("symbol")))
            begin, end = pd.Timestamp(row["start"]), pd.to_datetime(row.get("end"))
            spells.append(MembershipSpell(sid, begin, end, pd.to_datetime(row.get("known_at", begin)),
                                          str(row.get("source", "legacy effective-date assumption")),
                                          pd.to_datetime(row.get("end_known_at", end))))
    securities = tuple(SecurityRecord(sid, sid, "legacy ticker, immutable identity unverified", "unknown")
                       for sid in sorted(frames))
    return ResearchDataset(frames, pd.DatetimeIndex(spy.index), securities, tuple(spells),
                           metadata=metadata)


def eligible_at(series, test_series, members, fs, fe, ts, te, min_trades):
    """Legacy metrics adapter. ``test_series`` deliberately never affects eligibility."""
    from research.selection import active_ids
    allowed = active_ids(members, fe)
    out = {}
    for sid in sorted(series):
        if allowed is not None and sid not in allowed:
            continue
        prefix = series[sid].loc[:fe]
        if prefix.empty or prefix.index[-1] < pd.Timestamp(fe) - pd.Timedelta(days=7):
            continue
        metric = window_metrics(prefix, fs, fe)
        formation = prefix.loc[fs:fe]
        if len(formation) >= 200 and metric is not None and metric["trades"] >= min_trades:
            out[sid] = metric
    return out


def score_of(metric, criterion, rng):
    if criterion == "random":
        return rng.random()
    frame = pd.DataFrame([metric], index=["one"])
    return float(scores_for(frame, criterion).iloc[0])


def cagr(mult, start, end):
    years = max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 1 / 365.25)
    return (mult ** (1 / years) - 1) * 100 if mult > 0 else -100.0


def maxdd(path):
    values = np.r_[1.0, np.asarray(path, float)]
    return float(np.min(values / np.maximum.accumulate(values)) - 1) * 100


def run(data, spy, members=None, form=5, test=3, until=None, holdout=False, park="cash",
        prices="split", min_trades=8, n_perm=1000, seed=0, criteria=CRITERIA, levels=LEVELS,
        windows=None, form_data=None):
    """Legacy return-table adapter; new conclusions come from continuous summaries.

    A separate formation feed without verified durable IDs and aligned corporate
    actions is no longer accepted. Holdout access uses research.run holdout only.
    """
    if holdout or until == "holdout":
        raise ValueError("Use research.run holdout --frozen ARTIFACT; the legacy unguarded holdout is disabled")
    if park != "cash":
        raise ValueError("Cash is the frozen primary strategy; SPY parking is a separate unvalidated hypothesis")
    if form != 5 or test != 3:
        raise ValueError("Corrected primary experiment fixes five-year formation and three-year tests")
    if form_data is not None:
        raise ValueError("Merge feeds using durable security IDs and the data contract before research")
    data = {sid: frame.loc[:until or "2022-12-31"] for sid, frame in data.items()}
    spy = spy.loc[:until or "2022-12-31"]
    config = ExperimentConfig(criteria=tuple(criteria), levels=tuple(levels), min_closed_trades=min_trades,
                              permutations=n_perm, random_seed=seed)
    if windows is not None:
        config = replace(config, development_windows=tuple(Window(*w) for w in windows))
    result = run_experiment(_legacy_dataset(data, spy, members, prices), config)
    frame = result.windows.copy()
    frame["test"] = frame.start.str[:4] + "-" + frame.end.str[:4]
    frame.attrs["continuous_summary"] = result.summary
    frame.attrs["corrected_result"] = result
    frame.attrs["status"] = "RESEARCH_ONLY_LEGACY_OUTPUTS_SUPERSEDED"
    return frame


def chain(res):
    """Return the continuous engine summary; never multiply independently reset windows."""
    if "continuous_summary" not in res.attrs:
        raise ValueError("Independent-window legacy output is superseded and cannot be chained safely")
    return res.attrs["continuous_summary"].copy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv-folder")
    source.add_argument("--synthetic", choices=["random_walk", "regime"])
    parser.add_argument("--members")
    parser.add_argument("--spy", default="SPY")
    parser.add_argument("--prices", choices=["split", "total"], default="split")
    parser.add_argument("--park", choices=["cash", "spy"], default="cash")
    parser.add_argument("--until", default="2022-12-31")
    parser.add_argument("--form", type=int, default=5)
    parser.add_argument("--test", type=int, default=3)
    parser.add_argument("--top", type=int, help="compatibility: restrict to one top-N level")
    parser.add_argument("--step", type=int, help="overlapping tests are disabled")
    parser.add_argument("--window", help="development-only fs,fe,ts,te")
    parser.add_argument("--form-folder", help="requires verified feed merge; unsupported legacy option")
    parser.add_argument("--levels")
    parser.add_argument("--criteria", default="skill")
    parser.add_argument("--perm", type=int, default=1000)
    parser.add_argument("--out", default="private/corrected_development")
    args = parser.parse_args(argv)
    if args.until == "holdout":
        parser.error("Unguarded holdout disabled; use python -m research.run holdout --frozen ...")
    if args.step not in (None, 3):
        parser.error("Test windows may not overlap; use the declared continuous development configuration")
    if args.csv_folder:
        data = from_csv_folder(args.csv_folder)
        spy = data.pop(args.spy.upper())
    else:
        data = synthetic(args.synthetic)
        spy = data.pop("S000")
    members = pd.read_csv(args.members, parse_dates=["start", "end"]) if args.members else None
    levels = args.levels.split(",") if args.levels else ([f"top{args.top}"] if args.top else LEVELS)
    windows = [tuple(args.window.split(","))] if args.window else None
    result = run(data, spy, members, form=args.form, test=args.test, until=args.until,
                 park=args.park, prices=args.prices, n_perm=args.perm,
                 criteria=args.criteria.split(","), levels=levels, windows=windows,
                 form_data={} if args.form_folder else None)
    corrected = result.attrs["corrected_result"]
    output = Path(args.out)
    if output.suffix == ".csv":
        output = output.with_suffix("")
    write_result(corrected, output)
    print(chain(result).to_string(index=False))
    print("RESEARCH_ONLY: legacy independent-window results are superseded")


if __name__ == "__main__":
    main()
