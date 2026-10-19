"""Tests for agentic/data.py: Coinbase candles (mocked urllib), Robinhood inbox captures, dispatch, data checks."""
import io
import json
import sys
import types
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentic import calendar as cal  # noqa: E402
from agentic import data  # noqa: E402

UTC = timezone.utc
EPOCH = pd.Timestamp("1970-01-01")


def utc(*a):
    return datetime(*a, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(tmp_path / "state"))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)


# ------------------------------------------------------------------ Coinbase

NOON = utc(2026, 10, 18, 12)


def cb_values(d: pd.Timestamp):
    """Distinct OHLCV per day so a column mix-up fails: [low, high, open, close, volume]."""
    k = (d - EPOCH).days
    c = 1000.0 + k % 97
    return [c - 30.0, c + 20.0, c - 10.0, c, 5.0 + k % 7]


class FakeCoinbase:
    """Mimics GET /products/{p}/candles: <= 300 rows of [time, low, high, open, close, volume], newest first."""

    def __init__(self, first_day="2015-07-20", fail=()):
        self.first = pd.Timestamp(first_day)
        self.fail = list(fail)
        self.requests = []
        self.sizes = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.fail:
            err = self.fail.pop(0)
            if isinstance(err, int):
                raise urllib.error.HTTPError(req.full_url, err, "error", {}, None)
            raise err
        u = urlparse(req.full_url)
        assert u.netloc == "api.exchange.coinbase.com" and u.path.endswith("/candles")
        q = parse_qs(u.query)
        assert q["granularity"] == ["86400"]
        s = pd.Timestamp(q["start"][0]).tz_convert(None)
        e = pd.Timestamp(q["end"][0]).tz_convert(None)
        if (e - s).days + 1 > 300:
            raise urllib.error.HTTPError(req.full_url, 400, "granularity too small for the requested time range",
                                         {}, None)
        days = pd.date_range(max(s, self.first), e, freq="D")
        rows = [[int((d - EPOCH).total_seconds())] + cb_values(d) for d in reversed(days)]
        self.sizes.append(len(rows))
        return io.BytesIO(json.dumps(rows).encode())


def test_coinbase_paginates_backwards_and_returns_ascending_closed_bars():
    fake, sleeps = FakeCoinbase(), []
    df = data.fetch_coinbase_daily("ETH-USD", "2025-01-01", opener=fake, now_utc=NOON, sleep=sleeps.append)
    assert len(fake.requests) == 3 and max(fake.sizes) == 300 and sleeps == []
    ends = [pd.Timestamp(parse_qs(urlparse(r.full_url).query)["end"][0]) for r in fake.requests]
    assert ends == sorted(ends, reverse=True) and ends[0].date() == date(2026, 10, 18)
    assert all(r.get_header("User-agent") == data.USER_AGENT for r in fake.requests)
    assert df.index.is_monotonic_increasing and not df.index.has_duplicates
    assert df.index[0] == pd.Timestamp("2025-01-01") and df.index[-1] == pd.Timestamp("2026-10-17")
    assert len(df) == (pd.Timestamp("2026-10-17") - pd.Timestamp("2025-01-01")).days + 1
    assert df.index.name == "date" and df.index.tz is None
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert all(df[c].dtype == float for c in df.columns)
    lo, hi, op, cl, vol = cb_values(pd.Timestamp("2026-03-15"))
    assert df.loc["2026-03-15"].tolist() == [op, hi, lo, cl, vol]


@pytest.mark.parametrize("now,last", [(utc(2026, 10, 18, 0, 0, 1), "2026-10-17"),
                                      (utc(2026, 10, 17, 23, 59, 59), "2026-10-16")])
def test_coinbase_drops_forming_bar(now, last):
    df = data.fetch_coinbase_daily("BTC-USD", "2026-10-01", opener=FakeCoinbase(), now_utc=now, sleep=lambda s: None)
    assert df.index[-1] == pd.Timestamp(last)


def test_coinbase_explicit_end_and_listing_date():
    fake = FakeCoinbase(first_day="2026-06-01")
    df = data.fetch_coinbase_daily("SOL-USD", "2024-01-01", end="2026-09-30", opener=fake,
                                   now_utc=utc(2026, 10, 18, 12), sleep=lambda s: None)
    assert len(fake.requests) == 2                              # the second page is empty: stop
    assert df.index[0] == pd.Timestamp("2026-06-01") and df.index[-1] == pd.Timestamp("2026-09-30")


def test_coinbase_retries_429_with_backoff():
    fake, sleeps = FakeCoinbase(fail=[429, 429]), []
    df = data.fetch_coinbase_daily("ETH-USD", "2026-10-10", opener=fake, now_utc=NOON, sleep=sleeps.append)
    assert len(fake.requests) == 3 and sleeps == [1.0, 2.0]
    assert df.index[-1] == pd.Timestamp("2026-10-17")


def test_coinbase_retries_5xx_and_network_errors_then_gives_up():
    fake, sleeps = FakeCoinbase(fail=[urllib.error.URLError("reset"), 502]), []
    data.fetch_coinbase_daily("ETH-USD", "2026-10-10", opener=fake, now_utc=NOON, sleep=sleeps.append)
    assert len(fake.requests) == 3
    fake, sleeps = FakeCoinbase(fail=[503] * 4), []
    with pytest.raises(urllib.error.HTTPError):
        data.fetch_coinbase_daily("ETH-USD", "2026-10-10", opener=fake, now_utc=NOON, sleep=sleeps.append)
    assert len(fake.requests) == 4 and sleeps == [1.0, 2.0, 4.0]


def test_coinbase_no_retry_on_client_error_or_bad_payload():
    fake, sleeps = FakeCoinbase(fail=[404]), []
    with pytest.raises(urllib.error.HTTPError):
        data.fetch_coinbase_daily("NOPE-USD", "2026-10-10", opener=fake, now_utc=utc(2026, 10, 18), sleep=sleeps.append)
    assert len(fake.requests) == 1 and sleeps == []
    def error_payload(req, timeout=None):
        return io.BytesIO(b'{"message": "x"}')
    with pytest.raises(data.DataError):
        data.fetch_coinbase_daily("ETH-USD", "2026-10-10", opener=error_payload, now_utc=NOON, sleep=lambda s: None)


# ------------------------------------------------------------------ Robinhood inbox

GUIDE = "Bars are left-edge labeled in UTC; convert to the user's timezone for presentation."


def px(d: date, scale=1.0):
    return scale * (100.0 + d.toordinal() % 13)


def rh_bar(d: date, scale=1.0, interpolated=False, hour="13:30"):
    c = px(d, scale)
    return {"begins_at": f"{d.isoformat()}T{hour}:00Z", "open_price": f"{c - 0.5:.4f}", "close_price": f"{c:.4f}",
            "high_price": f"{c + 1:.4f}", "low_price": f"{c - 1.5:.4f}", "volume": 0 if interpolated else 123456,
            "session": "reg", "interpolated": interpolated}


def rh_result(symbol, days, scale=1.0, interval="day", bounds="regular", interpolated=(), hour="13:30"):
    bars = [rh_bar(d, scale, hour=hour) for d in days] + [rh_bar(d, scale, True, hour) for d in interpolated]
    bars.sort(key=lambda b: b["begins_at"])
    return {"symbol": symbol, "interval": interval, "bounds": bounds, "bars": bars}


def rh_response(*results, not_found=None):
    d = {"results": list(results)}
    if not_found:
        d["not_found"] = not_found
    return {"data": d, "guide": GUIDE}


def write_capture(inbox: Path, captured_at: str, response, tool="mcp__robinhood__get_equity_historicals",
                  tool_input=None, stamp=None):
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = stamp or captured_at.replace("-", "").replace(":", "")
    short = tool.rsplit("__", 1)[-1]
    f = inbox / f"{stamp}_{short}.json"
    f.write_text(json.dumps({"captured_at": captured_at, "tool": tool, "response": response,
                             "tool_input": tool_input if tool_input is not None else
                             {"symbols": ["SPY"], "interval": "day", "adjustment_type": "split",
                              "start_time": "2024-11-16T00:00:00Z"}}))
    return f


DAYS = cal.trading_days(date(2026, 8, 3), date(2026, 10, 16))
AFTER_CLOSE = utc(2026, 10, 16, 21, 0)


def wrappers(obj):
    return {
        "structured": obj,
        "content_text": {"content": [{"type": "text", "text": json.dumps(obj)}]},
        "structured_content": {"content": [{"type": "text", "text": "SPY: 54 bars"}], "structuredContent": obj},
        "content_list": [{"type": "text", "text": json.dumps(obj)}],
        "json_string": json.dumps(obj),
    }


@pytest.mark.parametrize("kind", list(wrappers({})))
def test_rh_unwraps_mcp_wrappers(tmp_path, kind):
    resp = wrappers(rh_response(rh_result("SPY", DAYS)))[kind]
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z", resp)
    got = data.load_robinhood_bars(tmp_path, ["spy"], AFTER_CLOSE)
    df = got["SPY"]
    assert list(df.index.date) == DAYS
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert all(df[c].dtype == float for c in df.columns)
    assert df["volume"].iloc[-1] == 123456                   # shares: the stock universe's liquidity filter
    assert df.index.name == "date" and df.index.tz is None
    assert df.loc["2026-10-16", "close"] == pytest.approx(px(date(2026, 10, 16)))
    assert df.loc["2026-10-16", "low"] == pytest.approx(px(date(2026, 10, 16)) - 1.5)


@pytest.mark.parametrize("hour", ["00:00", "04:00", "05:00", "13:30", "14:30"])
def test_rh_daily_bar_label_maps_to_session_date(tmp_path, hour):
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z", rh_response(rh_result("SPY", DAYS, hour=hour)))
    assert list(data.load_robinhood_bars(tmp_path, ["SPY"], AFTER_CLOSE)["SPY"].index.date) == DAYS


def test_rh_requires_daily_interval(tmp_path):
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z",
                  rh_response(rh_result("SPY", DAYS), rh_result("QQQ", DAYS, interval="5minute"),
                              rh_result("IWM", DAYS, interval="week")))
    issues = []
    got = data.load_robinhood_bars(tmp_path, None, AFTER_CLOSE, issues)
    assert set(got) == {"SPY"}
    assert any("QQQ" in m and "5minute" in m for m in issues) and any("IWM" in m and "week" in m for m in issues)


def test_rh_drops_interpolated_bars(tmp_path):
    filled = [date(2026, 9, 7), date(2026, 10, 10)]           # Labor Day, a Saturday
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z", rh_response(rh_result("SPY", DAYS, interpolated=filled)))
    df = data.load_robinhood_bars(tmp_path, ["SPY"], AFTER_CLOSE)["SPY"]
    assert list(df.index.date) == DAYS
    assert not any(pd.Timestamp(d) in df.index for d in filled)


@pytest.mark.parametrize("now,last", [
    (utc(2026, 10, 16, 18, 0), date(2026, 10, 15)),            # 14:00 ET: today's bar is still forming
    (utc(2026, 10, 16, 20, 19), date(2026, 10, 15)),
    (utc(2026, 10, 16, 20, 20), date(2026, 10, 16)),           # 16:20 ET
    (utc(2026, 10, 17, 15, 0), date(2026, 10, 16)),
])
def test_rh_drops_unclosed_session(tmp_path, now, last):
    write_capture(tmp_path, "2026-10-16T20:30:00.000000Z", rh_response(rh_result("SPY", DAYS)))
    assert data.load_robinhood_bars(tmp_path, ["SPY"], now)["SPY"].index[-1].date() == last


def test_rh_mid_session_capture_never_passes_for_the_closed_bar(tmp_path):
    """Regression: a capture taken at 11:00 ET held a forming 10-16 bar that signals at 16:30 ET accepted as closed
    (review check_signals_time)."""
    write_capture(tmp_path, "2026-10-16T15:00:00.000000Z", rh_response(rh_result("SPY", DAYS)))
    at_1630 = utc(2026, 10, 16, 20, 30)
    issues = []
    df = data.load_robinhood_bars(tmp_path, ["SPY"], at_1630, issues)["SPY"]
    assert df.index[-1].date() == date(2026, 10, 15)
    chk = data.check_bars(df, cal.last_closed_equity_session(at_1630), 10)
    assert any("expected 2026-10-16" in e for e in chk["errors"])
    write_capture(tmp_path, "2026-10-16T20:25:00.000000Z", rh_response(rh_result("SPY", DAYS)),
                  stamp="20261016T202500.000000Z")
    assert data.load_robinhood_bars(tmp_path, ["SPY"], at_1630)["SPY"].index[-1].date() == date(2026, 10, 16)
    bad = tmp_path / "nots"
    bad.mkdir()
    write_capture(bad, "garbage", rh_response(rh_result("SPY", DAYS)), stamp="20261017T150000.000000Z")
    df = data.load_robinhood_bars(bad, ["SPY"], utc(2026, 10, 17, 15, 0), issues)["SPY"]
    assert df.index[-1].date() == date(2026, 10, 15) and any("captured_at" in i for i in issues)


def test_rh_begins_at_offsets_across_dst(tmp_path):
    """Regression: '-04:00' / '-05:00' begins_at stamps made pandas 3 raise 'Mixed timezones' (review)."""
    days = cal.trading_days(date(2026, 10, 1), date(2026, 11, 6))
    res = rh_result("SPY", days)
    for b in res["bars"]:
        d = date.fromisoformat(b["begins_at"][:10])
        b["begins_at"] = f"{d.isoformat()}T09:30:00{'-04:00' if d < date(2026, 11, 2) else '-05:00'}"
    write_capture(tmp_path, "2026-11-07T15:00:00.000000Z", rh_response(res))
    df = data.load_robinhood_bars(tmp_path, ["SPY"], utc(2026, 11, 7, 15, 0))["SPY"]
    assert list(df.index.date) == days
    for style in ("T00:00:00Z", "midnight ET", "T13:30:00Z"):
        res = rh_result("SPY", days)
        for b in res["bars"]:
            d = b["begins_at"][:10]
            b["begins_at"] = d + (style if style[0] == "T" else "T04:00:00Z" if d < "2026-11-02" else "T05:00:00Z")
        d = tmp_path / style[1:3]
        d.mkdir()
        write_capture(d, "2026-11-07T15:00:00.000000Z", rh_response(res))
        assert list(data.load_robinhood_bars(d, ["SPY"], utc(2026, 11, 7, 15, 0))["SPY"].index.date) == days


def test_yfinance_crypto_cut_at_the_utc_day(monkeypatch):
    """Regression: a crypto asset on the yfinance feed was cut at the NYSE session (review check_yf_crypto)."""
    import types
    days = pd.date_range("2024-01-01", "2026-10-18", freq="D")
    frame = pd.DataFrame({"Open": 1.0, "High": 1.1, "Low": 0.9, "Close": 1.0, "Adj Close": 1.0, "Volume": 1},
                         index=days)
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(download=lambda *a, **k: frame))
    sunday = utc(2026, 10, 18, 12, 0)
    assert data.fetch_yfinance("BTC-USD", "2024-01-01", sunday, "crypto").index[-1].date() == date(2026, 10, 17)
    assert data.fetch_yfinance("SPY", "2024-01-01", sunday).index[-1].date() == date(2026, 10, 16)


def test_rh_merges_captures_newest_bar_wins(tmp_path):
    old_days = cal.trading_days(date(2026, 3, 2), date(2026, 10, 14))
    new_days = cal.trading_days(date(2026, 9, 1), date(2026, 10, 16))
    old = rh_result("SPY", old_days)
    new = rh_result("SPY", new_days)
    for b in new["bars"]:
        if b["begins_at"].startswith("2026-10-14"):
            b["close_price"] = f"{float(b['close_price']) + 0.05:.4f}"
    # the newer capture's file name sorts first: captured_at decides, not the name
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z", rh_response(new), stamp="20261001T000000.000000Z")
    write_capture(tmp_path, "2026-10-14T21:00:00.000000Z", rh_response(old), stamp="20261014T210000.000000Z")
    df = data.load_robinhood_bars(tmp_path, ["SPY"], AFTER_CLOSE)["SPY"]
    assert list(df.index.date) == sorted(set(old_days) | set(new_days))
    assert not df.index.has_duplicates and df.index.is_monotonic_increasing
    assert df.loc["2026-10-14", "close"] == pytest.approx(px(date(2026, 10, 14)) + 0.05)


def test_rh_ignores_older_capture_after_a_split(tmp_path):
    old_days = cal.trading_days(date(2026, 3, 2), date(2026, 10, 9))
    write_capture(tmp_path, "2026-10-09T21:00:00.000000Z", rh_response(rh_result("SPY", old_days, scale=4.0)))
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z", rh_response(rh_result("SPY", DAYS)))
    issues = []
    df = data.load_robinhood_bars(tmp_path, ["SPY"], AFTER_CLOSE, issues)["SPY"]
    assert list(df.index.date) == DAYS
    assert any("split" in m for m in issues)


def test_rh_skips_non_split_adjustment_and_extended_bounds(tmp_path):
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z", rh_response(rh_result("SPY", DAYS)),
                  tool_input={"symbols": ["SPY"], "interval": "day", "adjustment_type": "none"})
    write_capture(tmp_path, "2026-10-16T21:05:00.000000Z", rh_response(rh_result("QQQ", DAYS, bounds="extended")))
    issues = []
    assert data.load_robinhood_bars(tmp_path, None, AFTER_CLOSE, issues) == {}
    assert any("adjustment_type 'none'" in m for m in issues) and any("extended" in m for m in issues)


def test_rh_symbol_filter_other_tools_and_bad_files(tmp_path):
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z",
                  rh_response(rh_result("SPY", DAYS), rh_result("QQQ", DAYS, scale=3.0), not_found=["ZZZZ"]))
    write_capture(tmp_path, "2026-10-16T21:01:00.000000Z", {"data": {"results": [{"symbol": "QQQ", "bid_price": "1"}]}},
                  tool="mcp__robinhood__get_equity_quotes")
    (tmp_path / "20261016T210200.000000Z_get_equity_historicals.json").write_text("{not json")
    write_capture(tmp_path, "2026-10-16T21:03:00.000000Z",
                  {"isError": True, "content": [{"type": "text", "text": "upstream timeout"}]})
    write_capture(tmp_path, "2026-10-16T21:04:00.000000Z", {"content": [{"type": "text", "text": "not json"}]})
    issues = []
    got = data.load_robinhood_bars(tmp_path, ["qqq"], AFTER_CLOSE, issues)
    assert set(got) == {"QQQ"}
    assert got["QQQ"].loc["2026-10-16", "close"] == pytest.approx(px(date(2026, 10, 16), 3.0))
    assert len(issues) == 3
    assert data.load_robinhood_bars(tmp_path / "missing", ["SPY"], AFTER_CLOSE) == {}


def test_unwrap_mcp_shapes():
    obj = {"data": {"results": []}}
    for resp in wrappers(obj).values():
        assert data.unwrap_mcp(resp) == obj
    with pytest.raises(ValueError):
        data.unwrap_mcp({"isError": True, "content": [{"type": "text", "text": "boom"}]})
    with pytest.raises(ValueError):
        data.unwrap_mcp({"content": [{"type": "image", "data": "..."}]})


# ------------------------------------------------------------------ get_bars, csv, yfinance

CFG = {"limits": {"min_bars": 300}}


def asset(feed, symbol=None, cls="equity", **sig):
    return {"name": "X", "class": cls, "signal": {"source": "computed", "feed": feed, "symbol": symbol, **sig},
            "vehicle": {"type": "equity", "symbol": "X"}}


def test_get_bars_coinbase_requests_enough_history(monkeypatch):
    fake = FakeCoinbase()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(data.time, "sleep", lambda s: None)
    df = data.get_bars(asset("coinbase", "ETH-USD", "crypto"), CFG, utc(2026, 10, 18, 1))
    assert df.index[-1] == pd.Timestamp("2026-10-17")
    assert len(df) >= 300 + 150 and len(df) == 730
    assert data.history_days(asset("robinhood", "SPY"), CFG) >= 700
    assert data.history_days(asset("robinhood", "SPY"), {"limits": {"min_bars": 600}}) >= 750 * 7 / 5


def test_get_bars_robinhood_from_inbox(tmp_path):
    write_capture(tmp_path, "2026-10-16T21:00:00.000000Z", rh_response(rh_result("SPY", DAYS)))
    df = data.get_bars(asset("robinhood", "SPY"), CFG, AFTER_CLOSE, tmp_path)
    assert df.index[-1] == pd.Timestamp("2026-10-16")
    with pytest.raises(data.DataError, match="QQQ"):
        data.get_bars(asset("robinhood", "QQQ"), CFG, AFTER_CLOSE, tmp_path)


def test_get_bars_robinhood_default_inbox_is_state_dir(tmp_path):
    write_capture(tmp_path / "state" / "inbox", "2026-10-16T21:00:00.000000Z", rh_response(rh_result("SPY", DAYS)))
    assert len(data.get_bars(asset("robinhood", "SPY"), CFG, AFTER_CLOSE)) == len(DAYS)


def test_load_csv_and_csv_feed(tmp_path):
    import os
    a = tmp_path / "SPY_1D_a.csv"
    b = tmp_path / "SPY_1D_b.csv"
    a.write_text("time,open,high,low,close\n2026-10-15,1,2,0.5,1.5\n2026-10-14,1,2,0.5,1.2\n")
    b.write_text("Date,Open,High,Low,Close,Volume\n2026-10-15,10,20,5,15,1\n2026-10-16,10,20,5,12,1\n")
    os.utime(a, (1, 1))
    df = data.load_csv(a)
    assert list(df.index) == [pd.Timestamp("2026-10-14"), pd.Timestamp("2026-10-15")]
    got = data.get_bars(asset("csv", path=str(tmp_path / "SPY_1D_*.csv")), CFG, AFTER_CLOSE)
    assert got.index[-1] == pd.Timestamp("2026-10-16") and got.close.iloc[-1] == 12.0
    with pytest.raises(data.DataError):
        data.get_bars(asset("csv"), CFG, AFTER_CLOSE)
    with pytest.raises(data.DataError):
        data.load_csv(tmp_path / "none_*.csv")


def test_fetch_yfinance_uses_close_not_adj_close(monkeypatch):
    idx = pd.DatetimeIndex(["2026-10-14", "2026-10-15", "2026-10-16"], name="Date")
    cols = pd.MultiIndex.from_product([["Adj Close", "Close", "High", "Low", "Open", "Volume"], ["SPY"]],
                                      names=["Price", "Ticker"])
    frame = pd.DataFrame([[9.0, 10, 11, 8, 9.5, 1], [9.1, 10.1, 11, 8, 9.5, 1], [9.2, 10.2, 11, 8, 9.5, 1]],
                         index=idx, columns=cols)
    calls = []

    def download(sym, **kw):
        calls.append((sym, kw))
        return frame
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(download=download))
    df = data.fetch_yfinance("SPY", "2026-01-01", utc(2026, 10, 16, 18))
    assert calls[0][1]["auto_adjust"] is False
    assert list(df.close) == [10.0, 10.1]                       # 10-16 still forming at 14:00 ET
    assert data.get_bars(asset("yfinance", "SPY"), CFG, AFTER_CLOSE).close.iloc[-1] == 10.2


def test_yfinance_missing_and_unknown_feed(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", None)
    with pytest.raises(data.DataError, match="yfinance"):
        data.fetch_yfinance("SPY", "2026-01-01")
    with pytest.raises(data.DataError, match="unknown feed"):
        data.get_bars(asset("bloomberg", "SPY"), CFG, AFTER_CLOSE)


# ------------------------------------------------------------------ check_bars

END = date(2026, 10, 16)


def frame(n=400, end=END, crypto=False):
    days = pd.date_range(end=end, periods=n, freq="D") if crypto else pd.DatetimeIndex(
        cal.trading_days(date(2020, 1, 1), end)[-n:])
    i = np.arange(n)
    close = 100 + 5 * np.sin(i / 10)
    open_ = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.5, "low": np.minimum(open_, close) - 0.5,
                       "close": close}, index=days)
    df.index.name = "date"
    return df


def chk(df, end=END, n=300, cls="equity"):
    return data.check_bars(df, end, n, cls)


def test_check_bars_clean():
    assert chk(frame()) == {"errors": [], "warnings": []}
    assert chk(frame(crypto=True), cls="crypto") == {"errors": [], "warnings": []}
    assert chk(frame(), end=pd.Timestamp(END)) == {"errors": [], "warnings": []}


def test_check_bars_last_date_and_count():
    r = chk(frame(), end=date(2026, 10, 19))
    assert len(r["errors"]) == 1 and "2026-10-16" in r["errors"][0] and "2026-10-19" in r["errors"][0]
    r = chk(frame(250))
    assert r["errors"] == ["only 250 bars, need 300"]
    assert chk(frame().iloc[:0])["errors"] == ["no bars"]
    assert "missing columns" in chk(frame().drop(columns="low"))["errors"][0]


@pytest.mark.parametrize("col,val", [("close", np.nan), ("low", 0.0), ("open", -1.0)])
def test_check_bars_nan_or_nonpositive(col, val):
    df = frame()
    df.iloc[200, df.columns.get_loc(col)] = val
    errs = chk(df)["errors"]
    assert any("NaN or non-positive" in e for e in errs)


def test_check_bars_high_low_consistency():
    df = frame()
    df.iloc[150, df.columns.get_loc("high")] = df[["open", "close"]].iloc[150].max() - 0.01
    assert any("high/low outside" in e for e in chk(df)["errors"])
    df = frame()
    df.iloc[150, df.columns.get_loc("low")] = df[["open", "close"]].iloc[150].min() + 0.01
    assert any("high/low outside" in e for e in chk(df)["errors"])
    df = frame()                                               # within 1e-9 relative: fine
    df.iloc[150, df.columns.get_loc("high")] = df[["open", "close"]].iloc[150].max() * (1 - 1e-12)
    assert chk(df)["errors"] == []


@pytest.mark.parametrize("factor,back,flagged", [(0.5, 100, True), (3.0, 100, True), (1 / 10, 50, True),
                                                 (0.25, 299, True), (0.5, 350, False), (0.6, 100, False),
                                                 (1.5, 100, False)])
def test_check_bars_missed_split(factor, back, flagged):
    df = frame()
    df.iloc[-back:] *= factor                                  # every price from that bar on, as an unadjusted split
    df.iloc[-back, df.columns.get_loc("open")] = df.close.iloc[-back - 1] * factor
    errs = chk(df)["errors"]
    assert any("missed split" in e for e in errs) is flagged
    assert not any("high/low" in e for e in errs)


def test_check_bars_duplicates_and_order():
    df = frame()
    dup = pd.concat([df.iloc[:200], df.iloc[199:200], df.iloc[200:]])
    errs = chk(dup)["errors"]
    assert len(errs) == 1 and "duplicate dates" in errs[0] and str(df.index[199].date()) in errs[0]
    swapped = df.iloc[list(range(150)) + [151, 150] + list(range(152, 400))]
    assert chk(swapped)["errors"] == ["dates are not ascending"]


def test_check_bars_big_wick_warning():
    df = frame()
    df.iloc[-1, df.columns.get_loc("high")] = df.close.iloc[-1] + 15
    r = chk(df)
    assert r["errors"] == [] and len(r["warnings"]) == 1 and "true range" in r["warnings"][0]
    df = frame()
    df.iloc[-2, df.columns.get_loc("high")] = df.close.iloc[-2] + 15  # not the last bar: no warning
    assert chk(df, n=300)["warnings"] == []


def test_check_bars_gap_warnings():
    df = frame()
    gap = df.drop(df.index[200:205])                           # a week of missing sessions
    r = chk(gap, n=300)
    assert r["errors"] == [] and len(r["warnings"]) == 1 and "gap of" in r["warnings"][0]
    old = df.drop(df.index[20:25])                             # older than the last 300 bars
    assert chk(old, n=300)["warnings"] == []
    c = frame(crypto=True)
    one = c.drop(c.index[300])
    assert len(chk(one, cls="crypto")["warnings"]) == 1
    assert chk(one, cls="equity")["warnings"] == []
