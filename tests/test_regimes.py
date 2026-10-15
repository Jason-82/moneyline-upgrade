"""Accounting, causality and attribution checks for the research-only regime study."""
import numpy as np
import pandas as pd
import pytest

from analysis_2026.regimes import (attribution, conditions, drawdown_regime,
                                   simulate, sma_regime, stats, targets, validate)


def prices(close, opening=None):
    c = np.asarray(close, float)
    o = c if opening is None else np.asarray(opening, float)
    return pd.DataFrame({"open": o, "high": np.maximum(o, c), "low": np.minimum(o, c),
                         "close": c}, index=pd.date_range("2020-01-01", periods=len(c)))


def test_signal_cannot_execute_before_next_bar():
    d = prices([100, 100, 200, 400, 400])
    want = pd.Series([False, True, False, False, False], index=d.index)
    close = simulate(d, want, d.index[1], d.index[-1], 0, "close")
    opening = simulate(d, want, d.index[1], d.index[-1], 0, "open")
    assert close.equity.iloc[-1] == 2
    assert opening.equity.iloc[-1] == 2
    assert close.equity.iloc[1] == 1  # the signal-day doubling is missed


def test_actual_open_gap_and_intraday_returns():
    d = prices([100, 150, 180, 90], [100, 120, 160, 90])
    want = pd.Series([True, True, False, False], index=d.index)
    p = simulate(d, want, d.index[1], d.index[-1], .01, "open")
    expected = 90 / (120 * 1.01) * .99
    assert p.equity.iloc[-1] == pytest.approx(expected)
    assert p.equity.iloc[0] == pytest.approx(150 / (120 * 1.01))


def test_full_holding_pays_entry_and_final_exit():
    d = prices([100, 100, 200, 300])
    p = simulate(d, pd.Series(True, index=d.index), d.index[1], d.index[-1], .01)
    assert p.equity.iloc[-1] == pytest.approx(3 * .99 / 1.01)
    assert p.sides.sum() == 2
    assert p.log_return.sum() == pytest.approx(np.log(p.equity.iloc[-1]))


def test_policy_switch_while_green_does_not_trade():
    d = prices([100, 110, 120, 130, 140])
    rg = pd.Series(["bull", "bear", "transition", "bull", "bear"], index=d.index)
    t = targets(pd.Series(True, index=d.index), rg)["hold_bull_ml_other"]
    p = simulate(d, t, d.index[1], d.index[-1], .01)
    assert p.sides.sum() == 2


def test_prefix_causality_of_classifiers_and_conditions():
    d = prices(100 * np.exp(np.cumsum(np.random.default_rng(42).normal(0, .02, 700))))
    for fun in (sma_regime, drawdown_regime):
        pd.testing.assert_series_equal(fun(d.close).iloc[:500], fun(d.close.iloc[:500]))
    for k, x in conditions(d).items():
        pd.testing.assert_series_equal(x.iloc[:500], conditions(d.iloc[:500])[k])


def test_drawdown_hysteresis():
    d = prices([100, 79, 85, 89, 91, 110])
    assert drawdown_regime(d.close).tolist() == ["bull", "bear", "bear", "bear", "bull", "bull"]


def test_attribution_retains_cross_regime_returns_and_reconciles():
    d = prices([100, 110, 90, 120, 80, 150])
    labels = pd.Series(["bull", "bull", "bear", "bear", "transition", "bull"], index=d.index)
    want = targets(pd.Series([True, False, False, True, False, True], index=d.index), labels)
    p = simulate(d, want["hold_bull_ml_other"], d.index[1], d.index[-1], .01)
    b = simulate(d, want["hold"], d.index[1], d.index[-1], .01)
    a = attribution(p, b, labels)
    assert sum(x["days"] for x in a) == len(p)
    assert sum(x["active_log_wealth"] for x in a) == pytest.approx(np.log(p.equity.iloc[-1] / b.equity.iloc[-1]))


def test_first_day_loss_counts_in_drawdown():
    d = prices([100, 50, 60], [100, 100, 60])
    p = simulate(d, pd.Series(True, index=d.index), d.index[1], d.index[-1], 0, "open")
    assert stats(p)["max_dd_pct"] == -50


def test_tax_and_loss_carry():
    d = prices([100, 100, 50, 50, 100, 100])
    want = pd.Series([True, False, True, False, False, False], index=d.index)
    # Buy 100, sell 50 => lose .5. Buy 50 with .5, sell 100 => gain .5 offset fully.
    p = simulate(d, want, d.index[1], d.index[-1], 0, tax=True)
    assert p.tax.sum() == 0
    assert p.equity.iloc[-1] == 1
    hold = simulate(d, pd.Series(True, index=d.index), d.index[2], d.index[-1], 0, tax=True)
    assert hold.tax.sum() == pytest.approx(.35)
    assert hold.equity.iloc[-1] == pytest.approx(1.65)


def test_no_trades_for_cash_and_fixed_cash_yield():
    d = prices([100] * 370)
    p = simulate(d, pd.Series(False, index=d.index), d.index[1], d.index[-1], .01, cash_rate=.04)
    assert p.sides.sum() == 0
    assert p.equity.iloc[-1] == pytest.approx(1.04 ** (369 / 365.25))


def test_missing_prices_and_same_bar_fills_rejected():
    d = prices([100, 110, 90, 120])
    with pytest.raises(ValueError, match="Missing daily"):
        validate(d.drop(d.index[1]))
    with pytest.raises(ValueError, match="Invalid execution"):
        simulate(d, pd.Series(True, index=d.index), d.index[1], d.index[-1], lag=0)


def test_never_replace_unavailable_regime_with_bull():
    d = prices(np.arange(300) + 100)
    r = sma_regime(d.close)
    assert r.iloc[:219].eq("unavailable").all()
    assert r.iloc[219:].eq("bull").all()
    for k, t in targets(pd.Series(True, index=d.index), r).items():
        if k not in ("hold", "moneyline"):
            assert not t.iloc[:219].any()


@pytest.mark.parametrize("execution", ["open", "close"])
@pytest.mark.parametrize("lag", [1, 2])
def test_independent_vector_return_rebuild(execution, lag):
    rng = np.random.default_rng(123)
    c = 100 * np.exp(np.cumsum(rng.normal(0, .05, 100)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, .02, 100))
    d = prices(c, o)
    target = pd.Series(rng.random(100) > .5, index=d.index)
    fee, rate = .0095, .04
    a, b = 5, 98
    p = simulate(d, target, d.index[a], d.index[b], fee, execution, lag, rate)
    w = target.to_numpy()[np.arange(a, b + 1) - lag]
    prior = np.r_[False, w[:-1]]
    pc = c[np.arange(a, b + 1) - 1]
    cc = c[a:b + 1]
    rf = (1 + rate) ** (1 / 365.25)
    if execution == "close":
        factor = np.where(prior, cc / pc, rf)
        factor *= np.where(w & ~prior, 1 / (1 + fee), 1)
        factor *= np.where(~w & prior, 1 - fee, 1)
    else:
        oo = o[a:b + 1]
        factor = np.where(w & prior, cc / pc,
                 np.where(w & ~prior, cc / oo / (1 + fee),
                 np.where(~w & prior, oo / pc * (1 - fee) * rf, rf)))
    factor[-1] *= (1 - fee) if w[-1] else 1
    np.testing.assert_allclose(p.equity, np.cumprod(factor), rtol=2e-14)
