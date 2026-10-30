"""Mechanics of analysis_2026/megacap_dip.py on synthetic prices with known answers."""
import numpy as np
import pandas as pd
import pytest

from analysis_2026 import megacap_dip as M


def make_D(stocks, spy_close=None, start="1995-01-02", end="1999-12-31"):
    days = pd.bdate_range(start, end)
    if spy_close is None:
        spy_close = np.full(len(days), 100.0)
    spy = pd.DataFrame({"open": spy_close, "close": spy_close}, index=days)
    data = {}
    for s, (o, c) in stocks.items():
        data[s] = pd.DataFrame({"open": o, "close": c}, index=days[:len(c)])
    cal = days[days >= M.START]
    return {"data": data, "spy": spy, "cal": cal, "rc": pd.Series(0.0, cal), "end": days[-1]}


def test_crossings_one_event_per_decline_and_rearm():
    dd = np.array([np.nan, 0, -0.1, -0.26, -0.3, -0.2, -0.27, 0.0, -0.1, -0.25, -0.4])
    assert M.crossings(dd, 0.25) == [3, 9]          # -0.27 at 6 is the same decline; re-armed at the new high (7)


def test_crossings_first_valid_bar_never_triggers():
    dd = np.array([np.nan, np.nan, -0.3, -0.35, 0.0, -0.26])
    assert M.crossings(dd, 0.25) == [5]


def test_drawdown_needs_252_bars():
    c = pd.Series(np.linspace(100, 50, 300))
    dd, peak = M.drawdown(c, "52w")
    assert np.isnan(dd[:251]).all() and not np.isnan(dd[251])
    assert dd[299] == pytest.approx(50 / c.iloc[299 - 251] - 1)


def flat_then_drop(n, drop_at, level=100.0, low=70.0):
    c = np.full(n, level)
    c[drop_at:] = low
    return c.copy(), c.copy()


def test_event_position_and_book():
    n = 1300
    o, c = flat_then_drop(n, 400)
    c2 = c.copy(); o2 = o.copy()
    o2[401] = 71.0                                   # entry open
    c2[401:] = np.linspace(72, 80, n - 401)          # rises after entry
    D = make_D({"AAA": (o2, c2)})
    U = M.Universe("always", syms=["AAA"])
    ev = M.find_events(D, U)
    assert len(ev) == 1 and ev[0]["i"] == 400 and ev[0]["dd"] == pytest.approx(-0.30)
    dates, r, j, k = M.position(D, ev[0])
    df = D["data"]["AAA"]
    assert j == 401
    assert df.index[k] >= df.index[j] + pd.Timedelta(days=366) and df.index[k - 1] < df.index[j] + pd.Timedelta(days=366)
    gross = np.prod(1 + r)
    assert gross == pytest.approx(c2[k] / o2[401] * (1 - M.COST) ** 2)
    ex, br, cnt = M.book(D, ev)
    cal = D["cal"]
    on = (cal >= df.index[j]) & (cal <= df.index[k])
    assert (cnt[on] == 1).all() and (cnt[~on] == 0).all()
    assert np.prod(1 + br[on]) == pytest.approx(gross)
    assert (ex[~on] == 0).all()                      # SPY on every other day


def test_universe_mask_blocks_event_and_still_disarms():
    n = 1300
    o, c = flat_then_drop(n, 400)
    c[405] = 74.0; c[406:] = 70.0                     # wiggles below -25% without a new high
    D = make_D({"AAA": (o, c)})
    yr = D["data"]["AAA"].index[400].year
    U = M.Universe("year", by_year={yr + 1: ["AAA"]})   # not a member when it crossed
    assert M.find_events(D, U) == []


def test_entry_day_includes_spy_overnight_move():
    n = 1300
    o, c = flat_then_drop(n, 400)
    D = make_D({"AAA": (o, c)})
    D["spy"].loc[D["spy"].index[401], "open"] = 102.0          # SPY gaps up 2% overnight before the entry open
    U = M.Universe("always", syms=["AAA"])
    ev = M.find_events(D, U)
    _, r, _, _ = M.position(D, ev[0])
    assert 1 + r[0] == pytest.approx(1.02 * (c[401] / o[401]) * (1 - M.COST))


def test_series_ending_early_exits_at_last_close():
    n = 600
    o, c = flat_then_drop(n, 400)
    D = make_D({"AAA": (o, c)}, end="1999-12-31")
    U = M.Universe("always", syms=["AAA"])
    ev = M.find_events(D, U)
    _, _, j, k = M.position(D, ev[0])
    assert k == n - 1
    T = M.event_table(D, ev)
    assert bool(T.series_ended.iloc[0]) and bool(T.complete.iloc[0])


def test_slot_portfolio_no_tax_matches_hand_calc():
    n = 1300
    o, c = flat_then_drop(n, 400)
    c2 = c.copy(); c2[401:] = 84.0                  # +20% from the 70 entry open
    D = make_D({"AAA": (o, c2)})
    U = M.Universe("always", syms=["AAA"])
    ev = M.find_events(D, U)
    v, after, skipped, taken = M.slot_portfolio(D, ev, tax=False)
    assert taken == 1 and skipped == 0
    expect = 0.9 + 0.1 * (1 - M.COST) * (84.0 / 70.0) * (1 - M.COST)
    assert v.iloc[-1] == pytest.approx(expect)
    assert after == pytest.approx(expect)


def test_slot_portfolio_tax_long_term_gain():
    n = 1300
    o, c = flat_then_drop(n, 400)
    c2 = c.copy(); c2[401:] = 84.0
    D = make_D({"AAA": (o, c2)})
    U = M.Universe("always", syms=["AAA"])
    ev = M.find_events(D, U)
    _, after, _, _ = M.slot_portfolio(D, ev, tax=True)
    proceeds = 0.1 * (1 - M.COST) * (84.0 / 70.0) * (1 - M.COST)
    gain = proceeds - 0.1                            # held 366+ days: long-term
    assert after == pytest.approx(0.9 + proceeds - M.LT_RATE * gain)


def test_slot_cap_skips_beyond_slots():
    n = 1300
    stocks = {f"S{i:02d}": flat_then_drop(n, 400) for i in range(12)}
    D = make_D(stocks)
    U = M.Universe("always", syms=list(stocks))
    ev = M.find_events(D, U)
    assert len(ev) == 12
    _, _, skipped, taken = M.slot_portfolio(D, ev, tax=False)
    assert taken == 10 and skipped == 2


def test_reality_check_and_boot_null():
    rng = np.random.default_rng(0)
    E = rng.normal(0, 0.01, (3000, 5))
    r = M.reality_check(E, n=200, block=20)
    assert 0.05 < r["p_rc"] <= 1.0
    b = M.boot_mean(rng.normal(0.002, 0.01, 3000), n=500, block=20)
    assert b["p"] < 0.01


def test_tax_netting_and_carry():
    # loss year then gain year: the carried loss offsets the gain
    n = 1300
    o, c = flat_then_drop(n, 400)
    c2 = c.copy(); c2[401:] = 56.0                  # -20% loss on the first position
    D = make_D({"AAA": (o, c2)})
    U = M.Universe("always", syms=["AAA"])
    ev = M.find_events(D, U)
    v, after, _, _ = M.slot_portfolio(D, ev, tax=True)
    assert after == pytest.approx(v.iloc[-1])        # only losses: no tax at all
