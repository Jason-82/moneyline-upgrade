"""Tests for agentic.indicator: N-confirmed MoneyLine, tranche targets, TradingView export reader."""
import glob
import json
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import config, indicator  # noqa: E402
from agentic.indicator import moneyline_confirmed, read_tv_export, tranche_targets, tv_export_targets  # noqa: E402
from analysis_2026.flip_delay import moneyline_delay  # noqa: E402
from analysis_2026.moneyline_ref import moneyline  # noqa: E402

TV_DIR = os.environ.get("AGENTIC_TV_EXPORT_DIR")          # optional: a folder of your own TradingView exports
TV_FILES = sorted(glob.glob(os.path.join(TV_DIR, "*_1D*.csv"))) if TV_DIR else []


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
    ret = drift + rng.standard_t(4, n) * vol / np.sqrt(2)
    close = 100 * np.exp(np.cumsum(ret))
    prev = np.r_[100.0, close[:-1]]
    open_ = prev if crypto else prev * np.exp(rng.normal(0, vol * 0.3, n))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, vol * 0.6, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, vol * 0.6, n)))
    idx = pd.date_range(start, periods=n, freq="D") if crypto else pd.bdate_range(start, periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


SERIES = [(1, 0.013, False), (2, 0.013, False), (3, 0.009, False), (4, 0.02, False),     # stock-like (IWM ~1.3%)
          (5, 0.04, True), (6, 0.035, True), (7, 0.05, True)]                            # crypto-like


def _real(loader, *args):
    try:
        d = loader(*args)
    except (FileNotFoundError, OSError, KeyError) as exc:
        pytest.skip(f"repo data missing: {exc}")
    if len(d) < 300:
        pytest.skip("repo data too short")
    return d


def _spy():
    from analysis_2026.flip_delay import load_etf
    return _real(load_etf, "SPY")


def _eth():
    from analysis_2026.flip_delay import load_crypto_daily
    return _real(load_crypto_daily, "ETH")


def _iwm():
    p = REPO / "IWM_historical_data.csv"
    if not p.exists():
        pytest.skip("IWM_historical_data.csv missing")
    d = pd.read_csv(p, skiprows=[1, 2], index_col=0, parse_dates=True)[["Open", "High", "Low", "Close"]].astype(float)
    return d.dropna()


# ------------------------------------------------------------------ moneyline_confirmed

def _assert_matches_ref(df):
    got, ref = moneyline_confirmed(df), moneyline(df)
    assert list(got.columns) == ["green", "line", "pending", "flip", "atr"]
    assert np.array_equal(got["green"].to_numpy(), ref["green"].to_numpy())
    assert np.array_equal(got["line"].to_numpy(), ref["line"].to_numpy(), equal_nan=True)
    assert np.array_equal(got["flip"].to_numpy(), ref["flip"].to_numpy())
    assert np.array_equal(got["atr"].to_numpy(), ref["atr"].to_numpy(), equal_nan=True)
    assert (got["pending"] == 0).all()
    assert (ref["flip"] != 0).sum() > 5


@pytest.mark.parametrize("seed,vol,crypto", SERIES)
def test_n1_equals_moneyline_ref(seed, vol, crypto):
    _assert_matches_ref(synth(seed, vol=vol, crypto=crypto))


@pytest.mark.parametrize("seed,vol,crypto", SERIES)
@pytest.mark.parametrize("n", [2, 3, 5, 7, 10])
def test_symmetric_n_equals_flip_delay(seed, vol, crypto, n):
    df = synth(seed, vol=vol, crypto=crypto)
    got = moneyline_confirmed(df, n, n)
    assert np.array_equal(got["green"].to_numpy(), moneyline_delay(df, n))
    assert got["pending"].between(0, n - 1).all()


def test_any_case_columns():
    df = synth(11)
    up = df.rename(columns=str.upper)
    pd.testing.assert_frame_equal(moneyline_confirmed(up, 3, 2), moneyline_confirmed(df, 3, 2))


def test_warmup_and_flip_consistency():
    df = synth(12)
    out = moneyline_confirmed(df, 5, 2)
    assert out["line"].iloc[:9].isna().all() and out["line"].iloc[9:].notna().all()
    assert not out["green"].iloc[:9].any()
    g = out["green"].to_numpy().astype(int)
    expect = np.r_[0, np.diff(g)]
    expect[:10] = 0                                    # first valid bar seeds the state, no flip
    assert np.array_equal(out["flip"].to_numpy(), expect)


@pytest.mark.parametrize("seed,vol,crypto", SERIES)
def test_asymmetric_entry5_exit1(seed, vol, crypto):
    df = synth(seed, vol=vol, crypto=crypto)
    out = moneyline_confirmed(df, n_entry=5, n_exit=1)
    green, pend, flip = out["green"].to_numpy(), out["pending"].to_numpy(), out["flip"].to_numpy()
    assert (pend[green] == 0).all()                    # exits are immediate: nothing ever pending while green
    assert pend[~green].max() == 4
    entries = np.flatnonzero(flip == 1)
    assert len(entries) > 3 and (flip == -1).sum() > 3
    for i in entries:                                  # every entry follows 4 consecutive pending closes
        assert list(pend[i - 4:i]) == [1, 2, 3, 4] and not green[i - 1]
    line, close = out["line"].to_numpy(), df["close"].to_numpy()
    lo = (df["high"] + df["low"]).to_numpy() / 2.0 - 2.0 * out["atr"].to_numpy()
    for i in np.flatnonzero(green[:-1] & (np.arange(len(df) - 1) >= 10)) + 1:
        stop = max(line[i - 1], lo[i])                 # green: the line trails up
        if flip[i] == -1:                              # exit on the first close below it
            assert close[i] < stop
        else:
            assert green[i] and line[i] == stop and close[i] >= stop
    sym1, sym5 = moneyline_confirmed(df, 1, 1)["green"], moneyline_confirmed(df, 5, 5)["green"]
    assert (out["green"] != sym1).any() and (out["green"] != sym5).any()


@pytest.mark.parametrize("seed,vol,crypto", SERIES[:4])
@pytest.mark.parametrize("ne,nx", [(5, 1), (1, 5), (3, 2)])
def test_asymmetric_mirror(seed, vol, crypto, ne, nx):
    """Mirroring prices (p -> K - p) swaps green/red, so n_entry and n_exit must swap roles."""
    df = synth(seed, vol=vol, crypto=crypto)
    k = 2 * df.to_numpy().max()
    mir = pd.DataFrame({"open": k - df["open"], "high": k - df["low"], "low": k - df["high"], "close": k - df["close"]})
    a = moneyline_confirmed(df, ne, nx)
    b = moneyline_confirmed(mir, nx, ne)
    valid = a["line"].notna().to_numpy()
    assert np.array_equal(a["green"].to_numpy()[valid], ~b["green"].to_numpy()[valid])
    assert np.array_equal(a["pending"].to_numpy(), b["pending"].to_numpy())


def test_bad_n():
    with pytest.raises(ValueError):
        moneyline_confirmed(synth(1, n=50), 0, 1)


def test_real_spy():
    df = _spy()
    _assert_matches_ref(df)
    assert np.array_equal(moneyline_confirmed(df, 5, 5)["green"].to_numpy(), moneyline_delay(df, 5))


def test_real_eth():
    df = _eth()
    _assert_matches_ref(df)
    assert np.array_equal(moneyline_confirmed(df, 5, 5)["green"].to_numpy(), moneyline_delay(df, 5))


def test_real_iwm_uppercase():
    _assert_matches_ref(_iwm())


# ------------------------------------------------------------------ tranche_targets

def test_tranche_targets_split():
    df = synth(21, vol=0.04, crypto=True)
    tt = tranche_targets(df, config.DEFAULT_MODES["split"])
    assert {"g0", "g1", "target_frac", "pending0", "pending1", "line0", "line1"} <= set(tt.columns)
    a, b = moneyline_confirmed(df, 1, 1), moneyline_confirmed(df, 5, 5)
    assert np.array_equal(tt["g0"].to_numpy(), a["green"].to_numpy())
    assert np.array_equal(tt["g1"].to_numpy(), b["green"].to_numpy())
    assert np.array_equal(tt["pending1"].to_numpy(), b["pending"].to_numpy())
    assert np.array_equal(tt["line1"].to_numpy(), b["line"].to_numpy(), equal_nan=True)
    assert np.allclose(tt["target_frac"], 0.5 * a["green"] + 0.5 * b["green"])
    assert set(np.unique(tt["target_frac"])) == {0.0, 0.5, 1.0}


def test_tranche_targets_tuples_and_config():
    df = synth(22)
    cfg = config.validate(json.loads(config.EXAMPLE.read_text()))
    eth = next(a for a in cfg["assets"] if a["name"] == "ETH")
    imm = tranche_targets(df, config.tranches_for(eth, cfg))
    assert np.array_equal(imm["target_frac"].to_numpy(), moneyline_confirmed(df)["green"].to_numpy().astype(float))
    tup = tranche_targets(df, [(0.25, 1, 1), (0.75, 5, 1)])
    exp = 0.25 * moneyline_confirmed(df)["green"] + 0.75 * moneyline_confirmed(df, 5, 1)["green"]
    assert np.allclose(tup["target_frac"], exp)


@pytest.mark.parametrize("bad", [[], [(0.5, 1, 1)], [(0.7, 1, 1), (0.7, 5, 5)], [(1.5, 1, 1), (-0.5, 5, 5)]])
def test_tranche_targets_bad_weights(bad):
    with pytest.raises(ValueError):
        tranche_targets(synth(1, n=100), bad)


# ------------------------------------------------------------------ tv_export

def _write(path, frame, mtime=None):
    frame.to_csv(path, index=False)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _tv_frame(times):
    d = [1, 1, 1, -1, -1, -1, -1, 1, 1, np.nan]
    c = [0, 1, 0, 0, 2, 5, 0, 0, 3, np.nan]
    return pd.DataFrame({"time": times, "close": np.linspace(10, 19, 10), "Direction": d, "ConfirmCount": c,
                         "MoneyLine Level": np.linspace(9, 18, 10)})


def test_read_tv_export_crypto_unix(tmp_path):
    t = pd.date_range("2026-01-01", periods=10, freq="D", tz="UTC").as_unit("s").asi8
    _write(tmp_path / "COINBASE_ETHUSD_1D_a.csv", _tv_frame(t))
    out = read_tv_export(str(tmp_path / "COINBASE_ETHUSD_1D*.csv"))
    assert list(out.index) == list(pd.date_range("2026-01-01", periods=10, freq="D"))
    assert list(out.columns) == ["close", "Direction", "ConfirmCount", "MoneyLine Level"]
    assert out.index.tz is None and out.index.name == "date"
    assert out.attrs["path"].endswith("COINBASE_ETHUSD_1D_a.csv")


def test_read_tv_export_stock_dates(tmp_path):
    # NYSE opens at 09:30 ET: 14:30 UTC in winter, 13:30 UTC in summer (DST began 2026-03-08)
    days = pd.bdate_range("2026-03-03", periods=10)
    utc = [pd.Timestamp(f"{d.date()} 09:30", tz="America/New_York").tz_convert("UTC") for d in days]
    _write(tmp_path / "BATS_SPY_1D.csv", _tv_frame([int(x.timestamp()) for x in utc]))
    out = read_tv_export(tmp_path / "BATS_SPY_1D.csv")
    assert list(out.index) == list(days)
    iso = _tv_frame([x.tz_convert("America/New_York").isoformat() for x in utc])
    _write(tmp_path / "iso.csv", iso)
    assert list(read_tv_export(tmp_path / "iso.csv").index) == list(days)
    assert list(read_tv_export(tmp_path / "iso.csv", tz="UTC").index) == list(days)


def test_read_tv_export_iso_crypto_and_ohlc(tmp_path):
    f = _tv_frame([f"2026-02-{d:02d}T00:00:00Z" for d in range(1, 11)])
    f.insert(1, "open", f["close"] - 0.5)
    f.insert(2, "High", f["close"] + 1)
    f.insert(3, "low", f["close"] - 1)
    _write(tmp_path / "x.csv", f)
    out = read_tv_export(tmp_path / "x.csv")
    assert out.index[0] == pd.Timestamp("2026-02-01") and out.index[-1] == pd.Timestamp("2026-02-10")
    assert {"open", "high", "low", "close"} <= set(out.columns)
    assert out["high"].iloc[0] == f["High"].iloc[0]


def test_read_tv_export_prefix_suffix_and_case(tmp_path):
    t = pd.date_range("2026-01-01", periods=10, freq="D", tz="UTC").as_unit("s").asi8
    base = _tv_frame(t)
    lines = ["time,close,Daily Dir (-1=Bull 1=Bear),confirmcount (debug),Direction (-1=Bull 1=Bear),"
             "MoneyLine Level.1,Direction (-1=Bull 1=Bear),ATR,ATR"]           # 2nd Direction is read as '...).1'
    for i in range(10):
        r = base.iloc[i]
        lines.append(f"{t[i]},{r.close},7,{r.ConfirmCount},{r.Direction},{r['MoneyLine Level']},99,1,2")
    (tmp_path / "s.csv").write_text("\n".join(lines).replace("nan", "") + "\n")
    out = read_tv_export(tmp_path / "s.csv")
    assert np.array_equal(out["Direction"].to_numpy(), base["Direction"].to_numpy(), equal_nan=True)
    assert np.array_equal(out["ConfirmCount"].to_numpy(), base["ConfirmCount"].to_numpy(), equal_nan=True)
    assert np.allclose(out["MoneyLine Level"], base["MoneyLine Level"])


def test_read_tv_export_newest_dupes_and_errors(tmp_path, monkeypatch):
    t = pd.date_range("2026-01-01", periods=10, freq="D", tz="UTC").as_unit("s").asi8
    old, new = _tv_frame(t), _tv_frame(t)
    new["close"] += 100
    new = pd.concat([new, new.iloc[[4]].assign(close=999.0), new.iloc[[0]].assign(close=np.nan)], ignore_index=True)
    _write(tmp_path / "E_1D_old.csv", old, mtime=1_700_000_000)
    _write(tmp_path / "E_1D_new.csv", new, mtime=1_800_000_000)
    out = read_tv_export(str(tmp_path / "E_1D_*.csv"))
    assert out.attrs["path"].endswith("E_1D_new.csv")
    assert len(out) == 10 and out.index.is_monotonic_increasing and out.index.is_unique
    assert out["close"].iloc[4] == 999.0 and out["close"].iloc[0] == 110.0
    monkeypatch.setattr(indicator, "REPO", tmp_path)        # relative globs resolve against the repo root
    assert read_tv_export("E_1D_old.csv")["close"].iloc[0] == 10.0
    with pytest.raises(FileNotFoundError):
        read_tv_export(str(tmp_path / "nothing*.csv"))
    _write(tmp_path / "bad.csv", old.drop(columns=["ConfirmCount"]))
    with pytest.raises(ValueError, match="ConfirmCount"):
        read_tv_export(tmp_path / "bad.csv")


def test_tv_export_targets_rules(tmp_path):
    t = pd.date_range("2026-01-01", periods=10, freq="D", tz="UTC").as_unit("s").asi8
    _write(tmp_path / "x.csv", _tv_frame(t))
    df = read_tv_export(tmp_path / "x.csv")
    # D:   1  1  1 -1 -1 -1 -1  1  1 nan
    # cnt: 0  1  0  0  2  5  0  0  3 nan
    imm = [False, True, False, True, False, False, True, False, True, False]
    conf = [False, False, False, True, True, True, True, False, False, False]
    early = [False, False, False, True, True, False, True, False, False, False]
    for mode, exp in [("immediate", imm), ("confirm5", conf),
                      ("split", [0.5 * a + 0.5 * b for a, b in zip(imm, conf)])]:
        out = tv_export_targets(df, mode)
        assert list(out["immediate_green"]) == imm and list(out["confirm_green"]) == conf
        assert list(out["confirm_green_early"]) == early
        assert np.allclose(out["target_frac"].iloc[:9], np.array(exp, float)[:9])
        assert np.isnan(out["target_frac"].iloc[9])
        assert {"level", "pending", "direction"} <= set(out.columns)
        assert out["pending"].iloc[5] == 5 and out["level"].iloc[0] == 9 and out["direction"].iloc[3] == -1
    with pytest.raises(ValueError):
        tv_export_targets(df, "aggressive")


@pytest.mark.skipif(not TV_FILES, reason="set AGENTIC_TV_EXPORT_DIR to a folder of TradingView *_1D*.csv exports")
@pytest.mark.parametrize("path", TV_FILES or [None], ids=lambda p: "export" if p is None else f"export{TV_FILES.index(p)}")
def test_real_tv_export(path):
    df = read_tv_export(path)
    assert df.index.is_unique and df.index.is_monotonic_increasing and len(df) > 50
    out = tv_export_targets(df, "split")
    prev = df["MoneyLine Level"].shift(1)
    both = (prev.notna() & df["Direction"].notna() & df["ConfirmCount"].notna()).to_numpy()
    agree = (out["immediate_green"] == (df["close"] > prev)).to_numpy()[both]
    print(f"immediate_green == close > previous level on {agree.mean():.2%} of {both.sum()} bars")
    assert both.sum() > 50 and agree.all(), f"agreement {agree.mean():.4%}"
    assert set(np.unique(out["target_frac"].dropna())) <= {0.0, 0.5, 1.0}
