"""Causal selection, multiplicity, complete horizons, and reserved-data guards."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis_2026.moneyline_ref import moneyline
from research.calendar import nyse_schedule
from research.config import (ExperimentConfig, HOLDOUT_WINDOW, Window, claim_holdout,
                             freeze_config, read_frozen)
from research.data_contract import MembershipSpell, ResearchDataset, SecurityRecord
from research.run import require_full_calendar, run_experiment
from research.selection import (FormationResult, active_ids, daily_returns, formation_scores,
                                holm_adjust, permutation_selection_test, pick)


def bars(calendar, *, trend=False):
    n = len(calendar)
    returns = np.full(n, 0.0003) if trend else 0.006 * np.sin(np.arange(n) / 10) + 0.00005
    close = 100 * np.exp(np.cumsum(returns))
    open_ = np.r_[100, close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.003,
                         "low": np.minimum(open_, close) * 0.997, "close": close}, index=calendar)


@pytest.fixture(scope="module")
def history():
    calendar = nyse_schedule("2009-01-01", "2025-12-31").index
    return calendar, bars(calendar)


def test_future_quality_failure_does_not_change_formation(history):
    calendar, frame = history
    window = Window("2010-01-01", "2014-12-31", "2015-01-01", "2017-12-31")
    config = replace(ExperimentConfig(), min_closed_trades=0)
    future = frame.copy()
    future.loc[future.index >= "2015-01-01", "high"] *= 0.1
    past_result = formation_scores({"A": frame.loc[:"2014-12-31"]}, None, window, config, calendar=calendar)
    future_result = formation_scores({"A": future}, None, window, config, calendar=calendar)
    pd.testing.assert_frame_equal(past_result.metrics, future_result.metrics)
    assert "A" in future_result.metrics.index


def test_future_disappearance_does_not_filter_candidate(history):
    calendar, frame = history
    window = Window("2010-01-01", "2014-12-31", "2015-01-01", "2017-12-31")
    config = replace(ExperimentConfig(), min_closed_trades=0)
    members = pd.DataFrame({"security_id": ["A"], "start": ["2009-01-01"],
                            "end": ["2015-01-02"], "known_at": ["2009-01-01"]})
    result = formation_scores({"A": frame.loc[:"2014-12-31"]}, members, window, config, calendar=calendar)
    assert "A" in result.metrics.index


def test_membership_is_observed_at_formation_end_not_start(history):
    calendar, frame = history
    window = Window("2010-01-01", "2014-12-31", "2015-01-01", "2017-12-31")
    members = pd.DataFrame({"security_id": ["A"], "start": ["2013-01-01"], "end": [pd.NaT],
                            "known_at": ["2012-12-20"]})
    result = formation_scores({"A": frame}, members, window,
                              replace(ExperimentConfig(), min_closed_trades=0), calendar=calendar)
    assert "A" in result.metrics.index


def test_future_announcements_are_not_known():
    members = pd.DataFrame({"security_id": ["A", "B"], "start": ["2010-01-01"] * 2,
                            "end": ["2014-01-01", pd.NaT],
                            "known_at": ["2009-12-01", "2016-01-01"],
                            "end_known_at": ["2016-01-01", pd.NaT]})
    assert active_ids(members, "2014-12-31") == {"A"}


def test_stale_check_reads_prefix_not_final_dataset_date(history):
    calendar, frame = history
    window = Window("2010-01-01", "2014-12-31", "2015-01-01", "2017-12-31")
    # A reappearing future file cannot make an already stale security eligible.
    wrong = pd.concat([frame.loc[:"2014-10-01"], frame.loc["2015-01-01":]])
    result = formation_scores({"A": wrong}, None, window,
                              replace(ExperimentConfig(), min_closed_trades=0), calendar=calendar)
    assert "A" not in result.metrics.index
    assert "stale" in result.excluded["A"]


def test_exact_indicator_prefix_state_is_invariant(history):
    _, frame = history
    full = moneyline(frame).loc[:"2014-12-31"]
    prefix = moneyline(frame.loc[:"2014-12-31"])
    pd.testing.assert_frame_equal(full, prefix)


def test_dividend_entitlement_is_before_open():
    calendar = pd.date_range("2024-01-01", periods=30, freq="B")
    frame = bars(calendar, trend=True)
    # Green from ATR seed; entitlement on an already held position adds dividend.
    dividend = pd.Series(1.0, index=[calendar[20]])
    base, with_div = daily_returns(frame), daily_returns(frame, dividends=dividend)
    assert with_div.loc[calendar[20], "strat"] > base.loc[calendar[20], "strat"]
    assert with_div.loc[calendar[20], "bh"] > base.loc[calendar[20], "bh"]


def test_top30_exists_and_ties_are_deterministic():
    assert "top30" in ExperimentConfig().levels
    scores = pd.Series([2.0, 2.0, 1.0], index=["B", "A", "C"])
    assert pick(scores, "top1") == ["A"]
    assert pick(scores, ">10") == []


def test_holm_counts_every_tried_choice():
    result = holm_adjust({("skill", "top5"): 0.01, ("skill", "top10"): 0.02,
                          ("edge", "top5"): 0.03})
    assert result[("skill", "top5")] == pytest.approx(0.03)
    assert result[("skill", "top10")] == pytest.approx(0.04)
    assert result[("edge", "top5")] == pytest.approx(0.04)


def test_empty_windows_remain_in_permutation_statistic():
    w = Window("2010-01-01", "2014-12-31", "2015-01-01", "2017-12-31")
    first = FormationResult(w, pd.DataFrame({"skill": [20.0, 1.0], "edge": [2.0, 1.0]}, index=["A", "B"]), {}, ())
    empty = FormationResult(w, pd.DataFrame(columns=["skill", "edge"]), {}, ())
    config = replace(ExperimentConfig(), criteria=("skill", "edge"), levels=("top5", ">10", "all"), permutations=9)
    outcome = pd.Series({"A": 8.0, "B": 2.0})
    p = permutation_selection_test([first, empty], [outcome, pd.Series(dtype=float)], config)
    assert len(p) == 4
    # First threshold difference is +3; empty window is 0, so mean is 1.5.
    assert p[("skill", ">10")]["statistic"] == pytest.approx(1.5)
    assert p[("skill", ">10")]["family_size"] == 4


def test_unresolved_terminal_outcomes_do_not_count_as_cash_skill():
    w = Window("2010-01-01", "2014-12-31", "2015-01-01", "2017-12-31")
    formation = FormationResult(w, pd.DataFrame({"skill": [20.0, 1.0]}, index=["A", "B"]), {}, ())
    config = replace(ExperimentConfig(), levels=("top5", ">10", "all"), permutations=9)
    values = permutation_selection_test([formation], [pd.Series({"A": np.nan, "B": 2.0})], config)
    assert np.isnan(values[("skill", ">10")]["p_holm"])
    assert values[("skill", ">10")]["missing_outcomes"] == 1
    assert values[("skill", ">10")]["status"] == "UNIDENTIFIED_OUTCOMES_NO_PERMUTATION_CLAIM"


def test_holdout_must_cover_full_2023_through_2025():
    incomplete = nyse_schedule("2023-01-01", "2024-04-25").index
    with pytest.raises(ValueError, match="will not be shortened"):
        require_full_calendar(incomplete, [HOLDOUT_WINDOW], holdout=True)


def test_weekend_bar_is_rejected_as_calendar_session():
    window = Window("2018-01-01", "2022-12-31", "2023-01-01", "2025-12-31")
    calendar = nyse_schedule("2023-01-01", "2025-12-31").index
    invalid = calendar.union(pd.DatetimeIndex(["2023-01-07"]))
    with pytest.raises(ValueError, match="non-NYSE"):
        require_full_calendar(invalid, [window], holdout=True)


def test_freeze_hash_detects_modified_rule_and_claim_is_once(tmp_path):
    config = replace(ExperimentConfig(), chosen_criterion="skill", chosen_level="top5",
                     candidate_role="diagnostic_hypothesis")
    path = tmp_path / "frozen.json"
    artifact = freeze_config(config, path, dataset_manifest_sha256="source")
    restored, _ = read_frozen(path)
    assert restored == config
    claim_holdout(path, artifact)
    with pytest.raises(FileExistsError):
        claim_holdout(path, artifact)
    tampered = json.loads(path.read_text())
    tampered["experiment"]["chosen_level"] = "top10"
    path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="hash"):
        read_frozen(path)


def test_no_candidate_cannot_open_holdout(tmp_path):
    path = tmp_path / "unselected.json"
    freeze_config(ExperimentConfig(), path, dataset_manifest_sha256="source")
    with pytest.raises(ValueError, match="No candidate"):
        read_frozen(path)


def test_holdout_window_and_signal_are_fixed():
    with pytest.raises(ValueError, match="full 2023"):
        replace(ExperimentConfig(), holdout_window=Window("2018-01-01", "2022-12-31", "2023-01-01", "2024-04-25")).validate()
    with pytest.raises(ValueError, match="ATR"):
        replace(ExperimentConfig(), signal={"period": 10, "factor": 3.0}).validate()


def test_continuous_engine_retains_empty_selection_horizons():
    calendar = nyse_schedule("2009-01-01", "2020-12-31").index
    frame = bars(calendar, trend=True)
    metadata = {"mode": "exploratory", "price_basis": "split_only", "dividends_complete": True,
                "terminal_complete": True, "universe_complete": True, "point_in_time_ids": True,
                "price_source": "synthetic", "dividend_source": "synthetic known zero",
                "corporate_action_source": "synthetic", "calendar_source": "XNYS synthetic harness"}
    dataset = ResearchDataset({"A": frame, "SPY": frame.copy()}, calendar,
                              (SecurityRecord("A", "A", "synthetic", "known_zero"),
                               SecurityRecord("SPY", "SPY", "synthetic", "known_zero")),
                              (MembershipSpell("A", calendar[0], pd.NaT, calendar[0], "synthetic"),),
                              dividends={sid: pd.Series(0.0, index=calendar) for sid in ("A", "SPY")},
                              metadata=metadata)
    config = replace(ExperimentConfig(), min_closed_trades=0, permutations=0, levels=(">10", "all"),
                     development_windows=(Window("2010-01-01", "2014-12-31", "2015-01-01", "2017-12-31"),
                                          Window("2013-01-01", "2017-12-31", "2018-01-01", "2020-12-31")))
    result = run_experiment(dataset, config)
    cash = result.summary[result.summary.level == ">10"].iloc[0]
    assert cash.empty_windows == 2
    assert cash.cagr_pre == pytest.approx(0.0)
    assert cash.windows == 2
    windows = result.windows[result.windows.level == ">10"]
    assert len(windows) == 2
    assert (windows.n == 0).all()
    assert len(result.paths) == len(calendar[(calendar >= "2015-01-01") & (calendar <= "2020-12-31")])
    assert not cash.development_candidate
