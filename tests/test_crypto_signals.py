"""Causal signal and exact state-transition checks for the fixed crypto candidates."""
import numpy as np
import pandas as pd
import pytest

from analysis_2026.moneyline_ref import moneyline
from crypto_research import signals


def candles(close, midpoint=None):
    close = np.asarray(close, dtype=float)
    midpoint = close if midpoint is None else np.asarray(midpoint, dtype=float)
    high = np.maximum(midpoint + 3.0, close)
    low = np.minimum(midpoint - 3.0, close)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close},
        index=pd.date_range("2020-01-01", periods=len(close), freq="D", tz="UTC"),
    )


def fake_baseline(monkeypatch, green, flips=None, atr=None):
    green = np.asarray(green, dtype=bool)
    flips = np.zeros(len(green), dtype=int) if flips is None else np.asarray(flips)
    atr = np.ones(len(green)) if atr is None else np.asarray(atr, dtype=float)

    def implementation(frame):
        n = len(frame)
        return pd.DataFrame(
            {"green": green[:n], "flip": flips[:n], "atr": atr[:n], "line": np.zeros(n)},
            index=frame.index,
        )

    monkeypatch.setattr(signals, "moneyline", implementation)


def test_original_is_exact_existing_moneyline_and_unlagged():
    rng = np.random.default_rng(420)
    frame = candles(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.04, 700))))
    result = signals.target_weights(frame, "moneyline")
    pd.testing.assert_series_equal(result, moneyline(frame)["green"].astype(float).rename("moneyline"))
    assert set(result.unique()) == {0.0, 1.0}


@pytest.mark.parametrize("candidate", signals.CANDIDATES)
def test_every_prefix_matches_full_history_and_future_perturbations(candidate):
    rng = np.random.default_rng(815)
    frame = candles(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.045, 550))))
    full = signals.candidate_signals(frame, candidate)
    for length in (0, 1, 9, 10, 20, 21, 90, 91, 249, 360, 420, 550):
        prefix = signals.candidate_signals(frame.iloc[:length], candidate)
        pd.testing.assert_frame_equal(prefix, full.iloc[:length], check_exact=True)
    changed = frame.copy()
    changed.iloc[420:] *= np.linspace(0.2, 4, len(changed) - 420)[:, None]
    perturbed = signals.candidate_signals(changed, candidate)
    pd.testing.assert_frame_equal(perturbed.iloc[:420], full.iloc[:420], check_exact=True)
    assert full.index.equals(frame.index)
    assert ((full >= 0) & (full <= 1)).all().all()


def test_two_close_confirmation_delays_entry_but_has_original_red_exit(monkeypatch):
    fake_baseline(monkeypatch, [False, True, True, True, False, True, False, True, True])
    frame = candles([100] * 9)
    assert signals.target_weights(frame, "confirm2").tolist() == [0, 0, 1, 1, 0, 0, 0, 0, 1]


def test_breakout_uses_previous_twenty_closes_strictly_and_can_enter_later(monkeypatch):
    close = [100] * 20 + [100, 101, 100, 99, 102]
    fake_baseline(monkeypatch, [True] * 24 + [False])
    out = signals.explainable_signal_frame(candles(close), "breakout20")
    assert out["target"].tolist() == [0] * 21 + [1, 1, 1, 0]
    assert out.iloc[20]["previous_20_close_high"] == 100
    assert not out.iloc[20]["entry_validated"]  # Equality is insufficient.
    assert out.iloc[21]["previous_20_close_high"] == 100
    assert out.iloc[21]["entry_validated"]
    assert out.iloc[22]["previous_20_close_high"] == 101
    assert not out.iloc[22]["entry_validated"]  # Existing green position persists.
    assert not out.iloc[24]["entry_validated"]  # Higher close cannot override red.


def test_wider_exit_ratcheting_equality_and_wait_for_new_green_flip(monkeypatch):
    fake_baseline(
        monkeypatch,
        [True, True, True, True, True, False, True],
        flips=[0, 0, 0, 0, 0, -1, 1],
    )
    frame = candles([100, 101, 101, 97, 97, 99, 100], midpoint=[100, 104, 100, 100, 100, 100, 102])
    out = signals.explainable_signal_frame(frame, "wider_exit3")
    assert out["target"].tolist() == [1, 1, 1, 0, 0, 0, 1]
    np.testing.assert_allclose(out["exit_stop"].to_numpy(), [97, 101, 101, np.nan, np.nan, np.nan, 99], equal_nan=True)
    assert out.iloc[1]["target"] == 1  # Close equals current ratcheted stop.
    assert out.iloc[4]["baseline_green"]  # Remains flat despite baseline green.


def test_wider_exit_cold_enters_first_valid_current_green_state(monkeypatch):
    fake_baseline(monkeypatch, [False, False, True, True], atr=[np.nan, np.nan, 1, 1])
    assert signals.target_weights(candles([100] * 4), "wider_exit3").tolist() == [0, 0, 1, 1]


def test_wider_exit_uses_current_ratcheted_stop_for_exit(monkeypatch):
    fake_baseline(monkeypatch, [True, True])
    # Initial stop 97; the second bar raises it to 101.  A 100 close therefore
    # exits even though that close remains above yesterday's stop.
    out = signals.explainable_signal_frame(candles([100, 100], midpoint=[100, 104]), "wider_exit3")
    assert out["target"].tolist() == [1, 0]


def test_donchian_uses_current_close_and_prior_stop_exit_equality():
    component = signals.donchian_component(pd.Series([8.0, 10.0, 9.0]), 2)
    assert component["regime"].tolist() == [0, 1, 0]
    assert component.iloc[1]["upper"] == 10
    assert component.iloc[1]["midpoint"] == 9
    assert component.iloc[1]["stop"] == 9
    assert np.isnan(component.iloc[2]["stop"])


def test_donchian_upper_equality_has_priority_over_exit():
    component = signals.donchian_component(pd.Series([10.0, 10.0, 10.0]), 2)
    # Both upper and previous stop equal 10 on the third bar.  Entry takes
    # priority, so a flat channel does not generate artificial round trips.
    assert component["regime"].tolist() == [0, 1, 1]
    assert component["stop"].iloc[1:].tolist() == [10, 10]


def test_donchian_new_midpoint_applies_to_following_candle_not_today():
    component = signals.donchian_component(pd.Series([1.0, 9.0, 10.0, 8.0, 8.0]), 3)
    # First entry midpoint is 5.5. At index3 the channel midpoint rises to9;
    # close8 survives the prior5.5 stop and will be evaluated against9 next day.
    assert component["regime"].tolist() == [0, 0, 1, 1, 0]
    assert component.iloc[2]["stop"] == 5.5
    assert component.iloc[3]["stop"] == 9


def test_donchian_trailing_stop_never_falls_while_held():
    component = signals.donchian_component(pd.Series([8.0, 12.0, 11.0, 10.5, 12.0, 11.0]), 2)
    assert component["regime"].tolist() == [0, 1, 1, 0, 1, 0]
    assert component.iloc[1]["stop"] == 10
    assert component.iloc[2]["stop"] == 11.5


def test_ensemble_averages_nine_fixed_close_based_components():
    # Very large intraday highs must have no effect on a close-based channel.
    frame = candles(np.arange(100.0, 470.0))
    frame["high"] *= 10
    out = signals.explainable_signal_frame(frame, "donchianensemble_fixed")
    assert signals.DONCHIAN_LOOKBACKS == (5, 10, 20, 30, 60, 90, 150, 250, 360)
    assert out.iloc[3]["target"] == 0
    assert out.iloc[4]["target"] == pytest.approx(1 / 9)
    assert out.iloc[9]["target"] == pytest.approx(2 / 9)
    assert out.iloc[358]["target"] == pytest.approx(8 / 9)
    assert out.iloc[359]["target"] == 1
    pd.testing.assert_series_equal(out["target"], out["regime"].rename("target"))


def test_volatility_target_exact_sample_std_365_and_no_leverage():
    rng = np.random.default_rng(990)
    frame = candles(100 * np.exp(np.cumsum(rng.normal(0.002, 0.035, 420))))
    out = signals.explainable_signal_frame(frame, "donchianensemble_vol25")
    returns = frame["close"].pct_change(fill_method=None)
    expected_vol = returns.rolling(90, min_periods=90).std(ddof=1) * np.sqrt(365)
    expected_scale = (0.25 / expected_vol).clip(upper=1).fillna(0)
    pd.testing.assert_series_equal(out["annual_volatility"], expected_vol.rename("annual_volatility"))
    pd.testing.assert_series_equal(out["target"], (out["regime"] * expected_scale).rename("target"))
    assert out["target"].iloc[:90].eq(0).all()
    assert ((out["target"] >= 0) & (out["target"] <= out["regime"])).all()
    assert out["volatility_scale"].max() < 1  # This path requires a reduction.


def test_zero_volatility_uses_full_unleveraged_fraction_after_warmup():
    out = signals.explainable_signal_frame(candles([100.0] * 400), "donchianensemble_vol25")
    assert out.iloc[89]["target"] == 0
    assert out.iloc[90]["volatility_scale"] == 1
    assert out.iloc[-1]["target"] == 1


@pytest.mark.parametrize("candidate", signals.CANDIDATES)
def test_empty_frame_is_valid(candidate):
    out = signals.candidate_signals(candles([]), candidate)
    assert out.empty
    assert out.columns.tolist() == ["target", "regime"]


def test_missing_nonfinite_nonpositive_unsorted_duplicate_inputs_are_rejected():
    frame = candles([100, 101])
    for bad in (
        frame.drop(columns="open"),
        frame.assign(close=np.nan),
        frame.assign(close=0),
        frame.iloc[::-1],
        pd.concat([frame, frame.iloc[:1]]),
        frame.assign(high=1, low=2),
        frame.assign(high=99),  # Close/open outside the upper candle boundary.
        frame.assign(low=102),  # Close/open outside the lower candle boundary.
        frame.assign(open=500),  # Close may be valid while open is invalid.
        frame.assign(CLOSE=frame["close"]),
    ):
        with pytest.raises(ValueError):
            signals.candidate_signals(bad, "moneyline")
    with pytest.raises(ValueError, match="unknown candidate"):
        signals.candidate_signals(frame, "tuned_after_results")


def test_case_insensitive_ohlc_has_identical_signals():
    frame = candles(np.linspace(100, 120, 100))
    pd.testing.assert_frame_equal(
        signals.candidate_signals(frame, "moneyline"),
        signals.candidate_signals(frame.rename(columns=str.upper), "moneyline"),
    )
