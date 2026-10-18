"""Tests for agentic.backtest: fractional-weight returns, mode comparison, history loading."""
import sys
import types
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import agentic  # noqa: E402
from agentic import backtest, config  # noqa: E402
from agentic.backtest import compare_modes, compare_tv_modes, load_history, weights_returns  # noqa: E402
from agentic.indicator import moneyline_confirmed, tranche_targets  # noqa: E402
from analysis_2026.flip_delay import moneyline_delay, stats, strat_returns  # noqa: E402
from analysis_2026.moneyline_ref import moneyline  # noqa: E402

TOL = 1e-12


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(tmp_path / "state"))

    def _no_net(*a, **k):
        raise AssertionError("tests must not use the network")
    monkeypatch.setattr(urllib.request, "urlopen", _no_net)


def synth(seed, n=1500, vol=0.013, crypto=False, start="2012-01-03"):
    """Random-walk OHLC with fat tails, regime drift, overnight gaps (stocks) and realistic wicks."""
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.normal(0, vol / 6, n // 60 + 1), 60)[:n]
    close = 100 * np.exp(np.cumsum(drift + rng.standard_t(4, n) * vol / np.sqrt(2)))
    prev = np.r_[100.0, close[:-1]]
    open_ = prev if crypto else prev * np.exp(rng.normal(0, vol * 0.3, n))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, vol * 0.6, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, vol * 0.6, n)))
    idx = pd.date_range(start, periods=n, freq="D") if crypto else pd.bdate_range(start, periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


SERIES = [(1, 0.013, False, 0.0002), (2, 0.02, False, 0.0003), (5, 0.04, True, 0.001), (6, 0.05, True, 0.0095)]


# ------------------------------------------------------------------ weights_returns

@pytest.mark.parametrize("seed,vol,crypto,cost", SERIES)
@pytest.mark.parametrize("n", [1, 5])
def test_equals_strat_returns_for_01_weights(seed, vol, crypto, cost, n):
    df = synth(seed, vol=vol, crypto=crypto)
    g = moneyline_delay(df, n)
    ref = strat_returns(df, g, cost)[0]
    r, changes = weights_returns(df, g.astype(float), cost)
    assert r.index.equals(df.index)
    assert np.abs(r.to_numpy() - ref.to_numpy()).max() < TOL
    held = np.r_[False, g[:-1]]
    assert changes == int((held != np.r_[False, held[:-1]]).sum()) > 4


def test_equals_strat_returns_real_data():
    from analysis_2026.flip_delay import load_crypto_daily, load_etf
    ran = 0
    for loader, sym, cost in [(load_etf, "SPY", 0.0002), (load_crypto_daily, "ETH", 0.001)]:
        try:
            df = loader(sym)
        except (FileNotFoundError, OSError, KeyError):
            continue
        g = moneyline(df)["green"].to_numpy()
        r, _ = weights_returns(df, pd.Series(g.astype(float), index=df.index), cost)
        assert np.abs(r.to_numpy() - strat_returns(df, g, cost)[0].to_numpy()).max() < TOL
        ran += 1
    if not ran:
        pytest.skip("repo data missing")


def test_half_weights_hand_example():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame({"open": [100.0, 101, 103, 106, 104], "close": [100.0, 102, 105, 104, 103]}, index=idx)
    w = [0.5, 0.5, 1.0, 0.0, 0.0]          # decided at each close, held from the next open
    cost = 0.01
    r, n = weights_returns(df, w, cost, cash_rate_annual=0.0)
    expect = [
        0.0,
        # day 1: 0 -> 0.5 at the open: pay 1% on half, half earns open->close 101->102
        0.995 * (0.5 * 102 / 101 + 0.5) - 1,                          # -0.0000742574
        # day 2: hold 0.5: half earns close->close 102->105
        0.5 * (105 / 102 - 1),                                        # +0.0147058824
        # day 3: 0.5 earns 105->106 overnight, then 0.5 -> 1.0 (1% on half), full earns 106->104
        (0.5 * 106 / 105 + 0.5) * 0.995 * (104 / 106) - 1,            # -0.0191248877
        # day 4: 1.0 earns 104->104 overnight, sell all at the open paying 1%
        0.99 - 1,
    ]
    assert np.allclose(r.to_numpy(), expect, atol=1e-15)
    assert np.allclose(r.to_numpy()[1:4], [-0.0000742574, 0.0147058824, -0.0191248877], atol=1e-10)
    assert n == 3
    # with cash interest (0.01% per calendar day) the cash share earns it for the day
    r2, _ = weights_returns(df, w, cost, cash_rate_annual=0.0365)
    d = 0.0001
    assert np.allclose(r2.to_numpy(), [0.0, 0.995 * (0.5 * 102 / 101 + 0.5 * (1 + d)) - 1,
                                       0.5 * (105 / 102 - 1) + 0.5 * d,
                                       (0.5 * 106 / 105 + 0.5) * 0.995 * (104 / 106) - 1,
                                       0.99 * (1 + d) - 1], atol=1e-15)


def test_constant_half_weight_is_average_of_full_and_cash():
    df = synth(3, n=300)
    full, _ = weights_returns(df, np.ones(len(df)), 0.0)
    cash, _ = weights_returns(df, np.zeros(len(df)), 0.0)
    half, n = weights_returns(df, np.full(len(df), 0.5), 0.0)
    assert n == 1
    assert np.allclose(half.iloc[2:], 0.5 * full.iloc[2:] + 0.5 * cash.iloc[2:], atol=1e-15)


def test_cash_uses_tbill_by_year_and_calendar_days():
    df = synth(4, n=400, crypto=False, start="2023-06-01")
    r, n = weights_returns(df, np.zeros(len(df)), 0.001)
    assert n == 0
    assert np.abs(r.to_numpy() - strat_returns(df, np.zeros(len(df), bool), 0.001)[0].to_numpy()).max() == 0
    mon = r.index.dayofweek == 0
    assert (r[mon].iloc[1:] > r[~mon].iloc[1:].max()).all()      # Monday earns 3 calendar days


def test_weight_input_checks():
    df = synth(5, n=50)
    s = pd.Series(1.0, index=df.index[10:])                        # missing dates -> 0
    r, n = weights_returns(df, s, 0.0)
    cash, _ = weights_returns(df, np.zeros(len(df)), 0.0)
    assert n == 1 and np.array_equal(r.iloc[:11], cash.iloc[:11]) and r.iloc[12] != cash.iloc[12]
    with pytest.raises(ValueError):
        weights_returns(df, np.full(len(df), 1.5), 0.0)
    with pytest.raises(ValueError):
        weights_returns(df, np.ones(10), 0.0)


# ------------------------------------------------------------------ compare_modes

@pytest.mark.parametrize("seed,vol,crypto,cost", SERIES[:3])
def test_compare_modes_table(seed, vol, crypto, cost):
    df = synth(seed, n=1200, vol=vol, crypto=crypto)
    ppy = 365 if crypto else 252
    t = compare_modes(df, config.DEFAULT_MODES, cost, ppy)
    assert list(t.index) == ["immediate", "split", "confirm5", "BUY & HOLD"]
    assert list(t.columns)[:6] == ["CAGR_%", "CAGR_tax_%", "Sharpe", "maxDD_%", "trades_per_yr", "exposure_%"]
    assert t.attrs["start"] == df.index[120] and t.attrs["end"] == df.index[-1]
    win = df.index >= df.index[120]
    yrs = win.sum() / ppy
    assert np.allclose(t["years"], yrs)
    # immediate == the flip_delay engine and stats on the same window
    g = moneyline_delay(df, 1)
    ref = strat_returns(df, g, cost)[0][win]
    s = stats(ref, ppy)
    for col in ("CAGR_%", "CAGR_tax_%", "Sharpe", "maxDD_%"):
        assert t.loc["immediate", col] == pytest.approx(s[col], rel=1e-9, abs=1e-9)
    held = np.r_[False, g[:-1]]
    changes = (held != np.r_[False, held[:-1]])[win].sum()
    assert t.loc["immediate", "trades_per_yr"] == pytest.approx(changes / yrs)
    assert t.loc["immediate", "exposure_%"] == pytest.approx(held[win].mean() * 100)
    sp = tranche_targets(df, config.DEFAULT_MODES["split"])["target_frac"].to_numpy()
    assert t.loc["split", "exposure_%"] == pytest.approx(np.r_[0.0, sp[:-1]][win].mean() * 100)
    # buy & hold: taxed once at the end at the long-term rate
    bh = df["close"].pct_change().fillna(0)[win]
    end = float((1 + bh).prod())
    after = 1 + (end - 1) * 0.8 if end > 1 else end
    assert t.loc["BUY & HOLD", "CAGR_%"] == pytest.approx((end ** (1 / yrs) - 1) * 100)
    assert t.loc["BUY & HOLD", "CAGR_tax_%"] == pytest.approx((after ** (1 / yrs) - 1) * 100)
    assert t.loc["BUY & HOLD", "exposure_%"] == 100 and t.loc["BUY & HOLD", "trades_per_yr"] == 0


def test_compare_modes_start_rates_and_custom_modes():
    df = synth(7, n=1500, vol=0.04, crypto=True)
    modes = {"_comment": "ignored", "fast_in_slow_out": [{"weight": 1.0, "n_entry": 1, "n_exit": 3}],
             "late": [{"weight": 1.0, "n_entry": 5, "n_exit": 5}]}
    t = compare_modes(df, modes, 0.001, 365, start="2014-01-01", st_rate=0.0, lt_rate=0.0)
    assert list(t.index) == ["fast_in_slow_out", "late", "BUY & HOLD"]
    assert t.attrs["start"] == pd.Timestamp("2014-01-01")
    assert np.allclose(t["CAGR_tax_%"], t["CAGR_%"])                 # zero tax rates
    early = compare_modes(df, modes, 0.001, 365, start="2000-01-01")  # start inside warm-up -> bar 120
    assert early.attrs["start"] == df.index[120]
    g = moneyline_confirmed(df, 1, 3)["green"].to_numpy()
    r = strat_returns(df, g, 0.001)[0].loc["2014-01-01":]
    assert t.loc["fast_in_slow_out", "Sharpe"] == pytest.approx(stats(r, 365)["Sharpe"])
    with pytest.raises(ValueError):
        compare_modes(df.iloc[:100], modes, 0.001, 365)


def test_compare_tv_modes_close_only():
    df = synth(8, n=600, vol=0.04, crypto=True)
    rng = np.random.default_rng(0)
    d = np.where(np.repeat(rng.random(30) > 0.5, 20)[:600], -1.0, 1.0)
    cnt = np.where(rng.random(600) > 0.8, rng.integers(1, 5, 600), 0).astype(float)
    tv = pd.DataFrame({"close": df["close"], "Direction": d, "ConfirmCount": cnt, "MoneyLine Level": df["close"]})
    t = compare_tv_modes(tv, 0.0015, 365)
    assert list(t.index) == ["immediate", "split", "confirm5", "BUY & HOLD"]
    imm = (((d == -1) & (cnt == 0)) | ((d == 1) & (cnt >= 1))).astype(float)
    px = pd.DataFrame({"open": df["close"], "close": df["close"]})   # no open: fill at the next bar's close
    r, _ = weights_returns(px, imm, 0.0015)
    win = df.index >= df.index[120]
    assert t.loc["immediate", "Sharpe"] == pytest.approx(stats(r[win], 365)["Sharpe"])
    assert t.loc["confirm5", "exposure_%"] == pytest.approx(np.r_[0.0, (d == -1)[:-1]][win].mean() * 100)


def test_compare_tv_modes_uses_the_assets_tv_confirm():
    """Regression: the tv backtest always tested the Direction variant, not what signals.py trades (review)."""
    df = synth(9, n=400, vol=0.03, crypto=True)
    d = np.where((np.arange(400) // 40) % 2 == 0, 1.0, -1.0)
    cnt = np.zeros(400)
    for k in range(40, 400, 40):                         # 5 counting closes, then Direction flips one bar later
        cnt[k - 5:k] = np.arange(1, 6)
    tv = pd.DataFrame({"close": df["close"], "Direction": d, "ConfirmCount": cnt, "MoneyLine Level": df["close"]})
    count, direction = (compare_tv_modes(tv, 0.0015, 365, modes=("confirm5",), tv_confirm=h) for h in
                        ("count", "direction"))
    assert count.attrs["tv_confirm"] == "count" and compare_tv_modes(tv, 0.0015, 365).attrs["tv_confirm"] == "count"
    assert count.loc["confirm5", "CAGR_%"] != direction.loc["confirm5", "CAGR_%"]
    early = backtest.tv_target_frac(tv, "confirm5", "count")
    late = backtest.tv_target_frac(tv, "confirm5", "direction")
    assert (early.iloc[:-1].to_numpy() == late.iloc[1:].to_numpy()).all() and not early.equals(late)   # 1 bar early
    with pytest.raises(ValueError):
        compare_tv_modes(tv, 0.0015, 365, tv_confirm="maybe")


# ------------------------------------------------------------------ load_history

def _asset(**kw):
    a = {"name": "X", "class": "equity", "signal": {"source": "computed", "feed": "robinhood", "symbol": "ZZZQ"},
         "vehicle": {"type": "equity", "symbol": "ZZZQ"}}
    a.update(kw)
    return a


def test_load_history_csv_and_tv(tmp_path):
    df = synth(9, n=30)
    p = tmp_path / "h.csv"
    df.rename(columns=str.title).rename_axis("Date").to_csv(p)
    got = load_history(_asset(), {}, csv=p)
    assert np.allclose(got["close"], df["close"]) and list(got.index) == list(df.index)
    t = pd.date_range("2026-01-01", periods=5, freq="D", tz="UTC").as_unit("s").asi8
    pd.DataFrame({"time": t, "close": 1.0, "Direction": -1, "ConfirmCount": 0, "MoneyLine Level": 0.5}).to_csv(
        tmp_path / "tv.csv", index=False)
    tv = load_history(_asset(signal={"source": "tv_export", "path": str(tmp_path / "tv*.csv")}), {})
    assert "Direction" in tv.columns and len(tv) == 5


def test_load_history_repo_data_and_live_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(backtest, "REPO", tmp_path)
    seen = []
    monkeypatch.setattr(backtest, "load_crypto_daily", lambda s: seen.append(s) or "crypto:" + s)
    monkeypatch.setattr(backtest, "load_etf", lambda s: "etf:" + s)
    eth = _asset(**{"class": "crypto", "signal": {"source": "computed", "feed": "coinbase", "symbol": "ETH-USD"}})
    assert load_history(eth, {}) == "crypto:ETH"
    (tmp_path / "data" / "etf").mkdir(parents=True)
    (tmp_path / "data" / "etf" / "O_QQQ.csv").write_text("x")
    assert load_history(_asset(signal={"source": "computed", "feed": "robinhood", "symbol": "qqq"}), {}) == "etf:QQQ"
    pit = tmp_path / "data" / "universe_pit_all"
    pit.mkdir(parents=True)
    synth(10, n=20).rename_axis("date").to_csv(pit / "ABCD.csv")
    got = load_history(_asset(signal={"source": "computed", "feed": "robinhood", "symbol": "ABCD"}), {})
    assert len(got) == 20
    calls = []
    fake = types.SimpleNamespace(get_bars=lambda asset, cfg, now, inbox: calls.append((asset["name"], inbox)) or "live")
    monkeypatch.setitem(sys.modules, "agentic.data", fake)
    monkeypatch.setattr(agentic, "data", fake, raising=False)
    assert load_history(_asset(), {"x": 1}) == "live"
    assert calls[0][0] == "X" and str(calls[0][1]).startswith(str(tmp_path / "state"))

    def missing(sym):
        raise FileNotFoundError(sym)
    monkeypatch.setattr(backtest, "load_crypto_daily", missing)
    assert load_history(eth, {}) == "live"
