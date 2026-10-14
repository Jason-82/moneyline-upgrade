import numpy as np
import pandas as pd

from analysis_2026.theory_lab.schedules import (GLOBAL, completed_month_ends, crypto_leadership,
                                              flip_schedule, global_momentum)


def test_partial_month_is_not_a_month_end_signal():
    dates = pd.bdate_range("2026-01-01", "2026-10-13")
    ends = completed_month_ends(dates)
    assert ends[-1] == pd.Timestamp("2026-09-30")
    assert not (ends.month == 10).any()


def test_prefix_invariance_for_completed_schedules():
    idx = pd.date_range("2018-01-01", periods=1200)
    rng = np.random.default_rng(2)
    c = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, .03, (1200, 8)), axis=0)), index=idx, columns=GLOBAL)
    for fn in (global_momentum, lambda x: crypto_leadership(x.rename(columns={"SPY":"BTC", "IWM":"ETH"}))):
        full = fn(c)
        prefix = fn(c.iloc[:700])
        pd.testing.assert_frame_equal(full.loc[prefix.index], prefix)


def test_unfilled_global_slots_are_cash():
    idx = pd.bdate_range("2000-01-01", periods=600)
    c = pd.DataFrame({s:np.exp(np.arange(600)*(.001 if i==0 else -.001)) for i,s in enumerate(GLOBAL)}, index=idx)
    w = global_momentum(c)
    assert np.allclose(w.sum(axis=1), 1/3)
    assert np.allclose(w.SPY, 1/3)


def test_moneyline_control_does_not_rebalance_daily():
    ix = pd.date_range("2020-01-01", periods=10)
    g = pd.Series([False,True,True,True,True,False,False,True,True,True], index=ix, name="BTC")
    w = flip_schedule(g, ix[2])
    assert w.index.tolist() == [ix[1],ix[5],ix[7]]


def test_combined_moneyline_pre_liquidation_nav_reconciles():
    from analysis_2026.theory_lab.run import combine_moneyline
    ix = pd.date_range("2020-01-01", periods=100)
    data = {}
    for name, growth in (("BTC",.01),("ETH",.02)):
        c = 100*np.exp(np.arange(100)*growth)
        data[name] = pd.DataFrame({"open":c,"high":c*1.01,"low":c*.99,"close":c},index=ix)
    r = combine_moneyline(data,ix[30],ix[-1],.0015,1,0)
    assert r.path.equity_before_liquidation.iloc[-1] > r.path.equity.iloc[-1]
    assert np.isclose(r.path.equity_before_liquidation.iloc[-1]-r.path.equity.iloc[-1],r.path.fees.iloc[-1])
    assert np.isclose(r.path.exposure_before_liquidation.iloc[-1],1)
