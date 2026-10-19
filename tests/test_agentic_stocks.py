"""Tests for the stock universe (agentic/stocks.py), the yfinance and Robinhood bar caches (agentic/data.py), the
cross-check against Robinhood's previous close, too-large MCP results, the favorites tie-break, init --update's nested
merge, the scheduler's automatic time, the digest's SIGNAL column, and an end-to-end offline dry run of 10 coins and 15
placeholder stocks (AAA..OOO) through the real hooks. Every ticker, price and account number is synthetic; no network
(urllib and yfinance are mocked); state only under tmp_path."""
import io
import json
import os
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import calendar as cal  # noqa: E402
from agentic import cli, doctor, ledger, planner, stocks, universe  # noqa: E402
from agentic import config as cfgmod  # noqa: E402
from agentic import data as feeds  # noqa: E402
from agentic import signals as sg  # noqa: E402
from agentic import snapshot as snapmod  # noqa: E402
from agentic.config import ConfigError, paths, validate  # noqa: E402
from agentic.hooks import TOO_LARGE_HELP, capture_problem  # noqa: E402
from tests.test_agentic_e2e import POST, PRE, hook, mcp_call, real_now, trend  # noqa: E402
from tests.test_agentic_snapshot import write_cap  # noqa: E402

UTC = timezone.utc
ACCT, RHS = "STKACCT7Q1", "918273645"          # synthetic account numbers
NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)          # Monday 11:00 ET: stock bar 2026-10-16, crypto bar 10-18
EQ_END = date(2026, 10, 16)
EPOCH = pd.Timestamp("1970-01-01")
WIN = REPO / "agentic" / "windows"
TICKERS = [c * 3 for c in "ABCDEFGHIJKLMNO"]            # AAA .. OOO: placeholders only, never real watchlists


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(d))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(feeds, "PACER", feeds.Pacer(clock=lambda: 0.0, sleep=lambda s: None))
    monkeypatch.setattr(feeds, "YF_BACKOFF_S", 0.0)
    monkeypatch.setitem(sys.modules, "yfinance", None)            # not installed unless a test installs a fake
    return d


# ------------------------------------------------------------------ the synthetic world

# ticker: (pattern, last close, median daily dollar volume[, sessions]). fresh = green again ~12 bars ago (every fresh
# ticker flips the same day: ties), old = green all along (too late to join), red = downtrend.
STOCKS = {
    "AAA": ("fresh", 50.0, 9e8), "BBB": ("fresh", 64.0, 5e8), "CCC": ("old", 30.0, 4e8), "DDD": ("red", 80.0, 3e8),
    "EEE": ("fresh", 15.0, 2e8), "FFF": ("fresh", 85.0, 1.5e8), "GGG": ("fresh", 40.0, 1e8), "HHH": ("old", 60.0, 9e7),
    "III": ("fresh", 8.0, 5e5), "JJJ": ("fresh", 25.0, 6e7, 100), "KKK": ("fresh", 12.0, 5e7),
    "LLL": ("fresh", 33.0, 4e7), "MMM": ("fresh", 70.0, 3e7), "NNN": ("fresh", 45.0, 2e7), "OOO": ("fresh", 9.0, 1.5e7),
}
NOT_FOUND, INACTIVE, WHOLE = {"LLL"}, {"MMM"}, {"NNN"}
# coin: (pattern, last close, median daily dollar volume): all traded directly (etf_map {} in these tests)
COINS = {"AAVE": ("fresh", 150.0, 9e7), "LINK": ("fresh", 14.0, 8e7), "DOGE": ("fresh", 0.12, 1.5e8),
         "AVAX": ("fresh", 30.0, 7e7), "ADA": ("old", 0.4, 9e7), "DOT": ("red", 6.0, 4e7), "UNI": ("fresh", 8.0, 3e7),
         "XLM": ("old", 0.1, 2.5e7), "ATOM": ("red", 7.0, 1.3e7), "HBAR": ("red", 0.07, 2e7)}


def stock_frame(t, last=EQ_END, forming=True, n=None):
    """Daily bars with volume over NYSE sessions ending on `last` (plus the forming next session, as yfinance returns
    it during the day)."""
    pattern, px, dv, *k = STOCKS[t]
    n = n or (k[0] if k else 520)
    days = cal.trading_days(last - timedelta(days=2 * n + 30), last)[-n:]
    if forming:
        days.append(cal.next_trading_day(last))
    f = trend(days, px, drift=-0.003) if pattern == "red" else trend(days, px, dip=20 if pattern == "fresh" else None)
    f["volume"] = dv / f["close"]
    return f


def coin_frame(code, last, forming=True):
    pattern, px, dv = COINS[code]
    days = pd.date_range(end=pd.Timestamp(last) + pd.Timedelta(days=1 if forming else 0), periods=800, freq="D")
    f = trend(days, px, drift=-0.003) if pattern == "red" else trend(days, px, dip=20 if pattern == "fresh" else None)
    f["volume"] = dv / f["close"]
    return f


class FakeYF:
    """yfinance stand-in: download(tickers, start=..., auto_adjust=False, ...) returns a (Price, Ticker) MultiIndex
    frame like yfinance 0.2.5x, aligned on the union of dates, NaN columns for a ticker it has no data for."""

    def __init__(self, frames):
        self.frames, self.calls, self.fail, self.down, self.missing = frames, [], 0, False, set()

    def download(self, tickers, start=None, **kw):
        assert kw.get("auto_adjust") is False and kw.get("actions") is False
        tickers = [tickers] if isinstance(tickers, str) else list(tickers)
        self.calls.append((tickers, start))
        if self.down or self.fail:
            self.fail = max(self.fail - 1, 0)
            raise ConnectionError("Failed to perform, curl: (6) Could not resolve host: query2.finance.yahoo.com")
        parts = {}
        for t in tickers:
            if t in self.frames and t not in self.missing:
                f = self.frames[t]
                f = f[f.index >= pd.Timestamp(start)]
                parts[t] = pd.DataFrame({"Adj Close": f.close * 0.97, "Close": f.close, "High": f.high, "Low": f.low,
                                         "Open": f.open, "Volume": f.volume})
        if not parts:
            return pd.DataFrame()
        df = pd.concat(parts, axis=1).swaplevel(0, 1, axis=1).sort_index(axis=1)
        for t in tickers:
            if t not in parts:
                for col in ("Adj Close", "Close", "High", "Low", "Open", "Volume"):
                    df[(col, t)] = np.nan
        df.columns.names = ["Price", "Ticker"]
        return df

    def tickers_downloaded(self):
        return [t for tickers, _ in self.calls for t in tickers]


def install_yf(monkeypatch, frames=None, last=EQ_END):
    fake = FakeYF(frames if frames is not None else {t: stock_frame(t, last) for t in STOCKS})
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    return fake


class FakeCoinbase:
    """GET /products and /products/{p}/candles for COINS."""

    def __init__(self, last):
        self.frames = {f"{c}-USD": coin_frame(c, last) for c in COINS}
        self.urls = []

    def __call__(self, req, timeout=None):
        u = urlparse(req.full_url)
        assert u.netloc == "api.exchange.coinbase.com", req.full_url
        self.urls.append(req.full_url)
        if u.path == "/products":
            return io.BytesIO(json.dumps([{"id": p, "base_currency": p[:-4], "quote_currency": "USD",
                                           "status": "online", "trading_disabled": False}
                                          for p in self.frames]).encode())
        product = u.path.split("/")[2]
        if product not in self.frames:
            raise urllib.error.HTTPError(req.full_url, 404, "NotFound", {}, None)
        q = parse_qs(u.query)
        s, e = (pd.Timestamp(q[k][0]).tz_convert(None) for k in ("start", "end"))
        f = self.frames[product]
        f = f[(f.index >= s) & (f.index <= e)]
        rows = [[int((d - EPOCH).total_seconds()), r.low, r.high, r.open, r.close, r.volume]
                for d, r in f.iloc[::-1].iterrows()]
        return io.BytesIO(json.dumps(rows).encode())


def env(data):
    return {"data": data, "guide": "synthetic guide text"}


def tradability_response(symbols):
    res = []
    for s in symbols:
        if s in NOT_FOUND or s not in STOCKS:
            continue
        ok = s not in INACTIVE                     # delisted: state inactive (tradeable is still true here)
        res.append({"symbol": s, "name": f"{s} Placeholder Inc. - Common Stock", "simple_name": s,
                    "state": "active" if ok else "inactive", "country": "US", "tradeable": True,
                    "fractional_tradability": "untradable" if s in WHOLE else "tradable",
                    "account_type_tradabilities": [{"account_type": "individual",
                                                    "account_type_tradability": "tradable" if ok else "untradable"}]})
    return env({"results": res, "not_found": [s for s in symbols if s in NOT_FOUND or s not in STOCKS]})


def stock_cfg(**over):
    """A slots config (10 x 10%) with the stock universe on (feed yfinance) and a disabled explicit SPY."""
    u = {"enabled": True, "symbols": list(TICKERS), **over.pop("equity", {})}
    raw = {"account": {"account_number": ACCT, "rhs_account_number": RHS, "approvals_required": True},
           "live": over.pop("live", True), "capital": {"max_usd": 10000},
           "limits": {"max_order_usd": 2000, "max_day_usd": 20000, "max_asset_frac": 0.30, "min_order_usd": 5},
           "allocation": {"method": "slots", "slot_frac": 0.10, "priority": "crypto_first",
                          "favorites": over.pop("favorites", []), "class_max_frac": {"crypto": 0.60, "equity": 1.0}},
           "sleeve_initial_qty": over.pop("sleeve", {}),
           "universe": {"equity": u, "crypto": over.pop("crypto", {"enabled": False})},
           "assets": over.pop("assets", [
               {"name": "SPY", "class": "equity", "enabled": False, "alloc_frac": 0.2, "mode": "split",
                "signal": {"source": "computed", "feed": "robinhood", "symbol": "SPY"},
                "vehicle": {"type": "equity", "symbol": "SPY", "fractional": True}}])}
    raw.update(over)
    return raw


def write_tradability(inbox, at=None, symbols=None, account=ACCT):
    syms = list(symbols or TICKERS)
    for i in range(0, len(syms), 10):
        write_cap(inbox, "get_equity_tradability", tradability_response(syms[i:i + 10]),
                  {"account_number": account, "symbols": syms[i:i + 10]}, at or NOW - timedelta(minutes=5))


def frames_fetch(last=EQ_END, frames=None):
    """build_equity_universe's `fetch`: closed bars from the synthetic frames."""
    fr = frames or {t: stock_frame(t, last, forming=False) for t in STOCKS}

    def fetch(syms, start, now):
        return {s: fr[s][fr[s].index >= pd.Timestamp(start)] if s in fr else feeds.DataError(f"no rows for {s}")
                for s in syms}
    return fetch


def build(raw=None, held=None, **kw):
    cfg = validate(raw or stock_cfg())
    return stocks.build_equity_universe(cfg, NOW, paths()["inbox"], fetch=kw.pop("fetch", frames_fetch()),
                                        held=held or {"equity": set(), "crypto": set()}, **kw)


def by_ticker(report):
    return {e["ticker"]: e for e in report["tickers"]}


# ------------------------------------------------------------------ config

def test_config_equity_universe_defaults_validation_and_favorites():
    c = validate({"capital": {"max_usd": 100}})
    assert cfgmod.equity_universe(c) == {**cfgmod.DEFAULT_UNIVERSE_EQUITY, "symbols": [], "exclude": []}
    assert c["allocation"]["favorites"] == []
    c = validate(stock_cfg(equity={"symbols": ["aaa", " bbb", "AAA", "BRK.B"], "feed": "robinhood"},
                           favorites=["eth", "AAA", "ETH"]))
    u = cfgmod.equity_universe(c)
    assert u["symbols"] == ["AAA", "BBB", "BRK.B"] and u["feed"] == "robinhood" and u["min_history_bars"] == 150
    assert c["allocation"]["favorites"] == ["ETH", "AAA"]
    for bad, msg in (({"symbols": ["A B"]}, "not a ticker"), ({"feed": "coinbase"}, "feed must be one of"),
                     ({"min_history_bars": 10}, "min_history_bars"), ({"max_assets": 0}, "max_assets"),
                     ({"min_dollar_volume_usd": -1}, "min_dollar_volume_usd"), ({"wat": 1}, "unknown keys"),
                     ({"enabled": "true"}, "true or false"), ({"mode": "nope"}, "unknown mode")):
        with pytest.raises(ConfigError, match=msg):
            validate(stock_cfg(equity=bad))
    with pytest.raises(ConfigError, match="favorites"):
        validate(stock_cfg(favorites="AAA"))
    ex = validate(json.loads(cfgmod.EXAMPLE.read_text()))
    assert cfgmod.equity_universe(ex)["enabled"] is False and cfgmod.equity_universe(ex)["symbols"] == []
    assert ex["allocation"]["slot_frac"] == 0.10 <= ex["limits"]["max_asset_frac"]


def test_example_and_docs_carry_no_private_tickers():
    """The repo is public: the committed example has no tickers, and no ticker of the user's own private config (read
    from the gitignored private/agentic/config.json when it exists; never printed) appears in a committed file this
    feature touches."""
    ex = json.loads(cfgmod.EXAMPLE.read_text())
    assert ex["universe"]["equity"]["symbols"] == [] and ex["allocation"]["favorites"] == []
    mine = REPO / "private" / "agentic" / "config.json"
    if not mine.exists():
        return
    try:
        c = json.loads(mine.read_text(encoding="utf-8-sig"))
        private = {str(x).upper() for x in ((c.get("universe") or {}).get("equity") or {}).get("symbols") or []}
        private |= {str(x).upper() for x in (c.get("allocation") or {}).get("favorites") or []}
    except (OSError, ValueError, AttributeError):
        return
    private -= set(TICKERS) | {"SPY", "QQQ", "IWM", "ETH", "BTC", "SOL"}
    for f in [cfgmod.EXAMPLE, REPO / "agentic" / "README.md", REPO / "agentic" / "SPEC.md", Path(__file__),
              REPO / "agentic" / "stocks.py", REPO / ".claude" / "commands" / "moneyline.md"]:
        words = {w.strip(".,;:()[]{}'`\"") for w in f.read_text(encoding="utf-8").split()}
        n = len(words & private)
        assert n == 0, f"{f.name} contains {n} ticker(s) of the private config"


# ------------------------------------------------------------------ the builder

def test_build_tradability_filters_ranking_and_fractional(state):
    write_tradability(paths()["inbox"])
    assets, rep = build(stock_cfg(equity={"max_assets": 9}))
    t = by_ticker(rep)
    assert t["LLL"]["outcome"] == "excluded" and t["LLL"]["category"] == "not found on Robinhood"
    assert "check the ticker" in t["LLL"]["reason"]
    assert t["MMM"]["category"] == "not tradable on Robinhood" and "'inactive'" in t["MMM"]["reason"]
    assert t["III"]["category"] == "illiquid" and "need $1,000,000" in t["III"]["reason"]
    assert t["JJJ"]["outcome"] == "watch" and "too little history (100 bars, need 150)" in t["JJJ"]["reason"]
    ranked = [e["ticker"] for e in sorted(rep["tickers"], key=lambda e: e["rank"] or 99) if e["rank"]]
    assert ranked[:3] == ["AAA", "BBB", "CCC"]                                  # by median dollar volume
    assert t["NNN"]["category"] == "beyond max_assets" and t["OOO"]["category"] == "beyond max_assets"
    by = {a["name"]: a for a in assets}
    assert set(by) == {"AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "JJJ"}
    assert by["AAA"]["enabled"] and by["AAA"]["vehicle"] == {"type": "equity", "symbol": "AAA", "fractional": True}
    assert by["AAA"]["signal"] == {"source": "computed", "feed": "yfinance", "symbol": "AAA"}
    assert by["AAA"]["class"] == "equity" and by["AAA"]["universe"]["kind"] == "equity"
    assert by["JJJ"]["enabled"] is False and by["JJJ"]["min_bars"] == 100 and by["AAA"]["min_bars"] == 150
    assert by["AAA"]["universe"]["dollar_volume_usd"] == pytest.approx(9e8, rel=1e-6)
    assets, rep = build()
    assert {a["name"]: a for a in assets}["NNN"]["vehicle"]["fractional"] is False              # whole shares only
    assert "whole shares only" in by_ticker(rep)["NNN"]["reason"]
    lines = stocks.summary_lines(rep)
    assert lines[0].startswith("UNIVERSE stocks (feed yfinance, tradability captured ") and "15 tickers considered" in \
        lines[0]
    assert "11 tradable: 10 fractional, 1 whole shares only; 1 watch-only" in lines[0]
    assert "excluded: 1 not found on Robinhood, 1 not tradable on Robinhood, 1 illiquid" in lines[0]
    assert any(x.startswith("    JJJ: too little history") for x in lines)
    full = stocks.summary_lines(rep, full=True)
    assert len(full) == 1 + 15


def test_build_without_tradability_is_watch_only_and_unknown_tickers_never_break(state):
    raw = stock_cfg(equity={"symbols": ["AAA", "ZZZ", "QQQQ"]})
    assets, rep = build(raw)
    t = by_ticker(rep)
    assert t["AAA"]["outcome"] == "watch" and "no get_equity_tradability capture" in t["AAA"]["reason"]
    assert t["ZZZ"]["category"] == "data error" and t["QQQQ"]["category"] == "data error"
    write_tradability(paths()["inbox"], symbols=["AAA", "ZZZ", "QQQQ"])
    _, rep = build(raw)
    assert by_ticker(rep)["ZZZ"]["category"] == "not found on Robinhood"
    old = NOW - timedelta(days=8)                                                  # older than 7 days: confirms nothing
    for f in paths()["inbox"].glob("*.json"):
        f.unlink()
    write_tradability(paths()["inbox"], at=old, symbols=["AAA"])
    assert by_ticker(build(raw)[1])["AAA"]["outcome"] == "watch"


def test_build_explicit_precedence_crypto_collisions_and_names(state):
    write_tradability(paths()["inbox"])
    explicit = [{"name": "EEE", "class": "equity", "enabled": False, "alloc_frac": 0.1, "mode": "split",
                 "signal": {"source": "computed", "feed": "robinhood", "symbol": "EEE"},
                 "vehicle": {"type": "equity", "symbol": "EEE"}},
                {"name": "MY-F", "class": "equity", "enabled": True, "alloc_frac": 0.1, "mode": "split",
                 "signal": {"source": "computed", "feed": "robinhood", "symbol": "FFF"},
                 "vehicle": {"type": "equity", "symbol": "FFF"}}]
    coin = {"name": "CCC", "class": "crypto", "enabled": True, "vehicle": {"type": "crypto", "symbol": "CCC"},
            "signal": {"feed": "coinbase", "symbol": "CCC-USD"}, "universe": {"outcome": "direct"}}
    etf_coin = {"name": "XYZ", "class": "crypto", "enabled": False, "vehicle": {"type": "equity", "symbol": "DDD"},
                "signal": {"feed": "coinbase", "symbol": "XYZ-USD"}, "universe": {"outcome": "watch"}}
    raw = stock_cfg(assets=explicit)
    assets, rep = build(raw, crypto_assets=[coin, etf_coin])
    t = by_ticker(rep)
    assert t["EEE"]["outcome"] == "explicit" and "(disabled)" in t["EEE"]["reason"]
    assert t["FFF"]["outcome"] == "explicit" and "MY-F trades it" in t["FFF"]["reason"]
    assert t["DDD"]["category"] == "covered by the crypto universe" and "for XYZ" in t["DDD"]["reason"]
    by = {a["name"]: a for a in assets}
    assert "CCC" not in by and by["CCC-STOCK"]["vehicle"]["symbol"] == "CCC"           # names stay unique
    assert "the crypto universe has the coin CCC" in t["CCC"]["reason"]
    sig = {"universe_equity": {"assets": assets}}
    eff, warns = stocks.with_equity_universe(validate(raw), sig)
    assert warns == [] and len({a["name"] for a in eff["assets"]}) == len(eff["assets"])
    # a coin named like a stock ticker and the duplicate-vehicle check: two enabled assets on one vehicle still error
    eff["assets"].append({**eff["assets"][-1], "name": "AAA-TWIN"})
    p = planner.make_plan({"assets": []}, {"total_value": 1000.0, "cash": 1000.0, "buying_power": 1000.0,
                                           "quotes": {}, "errors": [], "warnings": []}, eff, NOW, flags={},
                          placed_today_usd=0.0, journal=[], sleeve={"baseline": True, "sleeve": {}, "mismatches": []})
    assert any("trade the same vehicle" in e for e in p["errors"])
    both = [{"name": "ZZZ-STOCK", "class": "equity", "enabled": False, "alloc_frac": 0.1, "mode": "split",
             "signal": {"source": "computed", "feed": "robinhood", "symbol": "ZZZ"},
             "vehicle": {"type": "equity", "symbol": "ZZZ"}}]
    zcoin = dict(coin, name="ZZZ", vehicle={"type": "crypto", "symbol": "ZZZ"})
    STOCKS["ZZZ"] = ("fresh", 20.0, 9e7)
    try:
        write_tradability(paths()["inbox"], symbols=["ZZZ"])
        _, rep = build(stock_cfg(assets=both, equity={"symbols": ["ZZZ"]}), crypto_assets=[zcoin],
                       fetch=frames_fetch(frames={"ZZZ": stock_frame("ZZZ", forming=False)}))
        assert by_ticker(rep)["ZZZ"]["category"] == "name collision"
    finally:
        del STOCKS["ZZZ"]


def test_held_tickers_are_never_dropped(state):
    write_tradability(paths()["inbox"])
    held = {"equity": {"LLL", "III", "CCC"}, "crypto": set()}
    sg.write_signals({"signals_file": "signals/signals_2026-10-18.json",
                      "universe_equity": {"assets": [{"name": t, "vehicle": {"symbol": t}} for t in ("LLL", "III",
                                                                                                    "CCC")]}})
    raw = stock_cfg(equity={"symbols": [t for t in TICKERS if t != "CCC"], "exclude": []})
    assets, rep = build(raw, held=held)
    by = {a["name"]: a for a in assets}
    assert by["III"]["enabled"] and "illiquid" in by["III"]["universe"]["hold_only"]
    assert by["LLL"]["enabled"] and "not found on Robinhood" in by["LLL"]["universe"]["hold_only"]
    assert "no longer in universe.equity.symbols" in by["CCC"]["universe"]["hold_only"]
    raw["universe"]["equity"]["enabled"] = False                  # off: only the held tickers of the last scan
    assets, rep = build(raw, held=held)
    assert sorted(a["name"] for a in assets) == ["CCC", "III", "LLL"]
    assert all("universe.equity is off" in a["universe"]["hold_only"] for a in assets)
    eff, warns = stocks.with_equity_universe(validate(raw), {"universe_equity": {"assets": assets}})
    assert warns == [] and len(eff["assets"]) == 1 + 3
    assert "off: held tickers only" in stocks.summary_lines(rep)[0]
    assert build(raw, held={"equity": set(), "crypto": set()}) == ([], build(raw, held={"equity": set(),
                                                                                      "crypto": set()})[1])


def test_held_young_stock_is_hold_only_with_a_usable_exit_signal(state, monkeypatch):
    """Regression: a held ticker with fewer than min_history_bars bars got min_bars 150, so its signal failed and the
    planner could never sell it."""
    install_yf(monkeypatch)
    write_tradability(paths()["inbox"])
    cfg = validate(stock_cfg())
    assets, _ = build(held={"equity": {"JJJ"}, "crypto": set()})
    j = next(a for a in assets if a["name"] == "JJJ")
    assert j["enabled"] and j["min_bars"] == 100
    assert j["universe"]["hold_only"] == "too little history (100 bars, need 150); held, so kept for exits only"
    s = sg.asset_signal(j, cfg, NOW, paths()["inbox"], "")
    assert s["errors"] == [] and s["target_frac"] is not None
    w = next(a for a in build()[0] if a["name"] == "JJJ")                         # not held: watch-only, as before
    assert not w["enabled"] and w["min_bars"] == 100 and w["universe"]["outcome"] == "watch"
    assert next(a for a in assets if a["name"] == "AAA")["min_bars"] == 150
    fr = {t: stock_frame(t, forming=False) for t in STOCKS}
    fr["III"] = stock_frame("III", forming=False, n=90)                          # illiquid and young, held
    iii = next(a for a in build(held={"equity": {"III"}, "crypto": set()}, fetch=frames_fetch(frames=fr))[0]
               if a["name"] == "III")
    assert iii["min_bars"] == 90 and "illiquid" in iii["universe"]["hold_only"]
    pcfg, sig, snap, sleeve = mini([j], [sigrec("JJJ", "equity", 0.0, close=25.0)], {"JJJ": quote(25.0)},
                                   positions={"JJJ": 4.0})
    kw = dict(placed_today_usd=0.0, journal=[], sleeve=sleeve, crosscheck={"JJJ": None})
    assert [o["key"] for o in planner.make_plan(sig, snap, pcfg, NOW, 1, {}, **kw)["orders"]] == ["JJJ|JJJ|sell|0"]
    pcfg, sig, snap, sleeve = mini([j], [sigrec("JJJ", "equity", 1.0, close=25.0)], {"JJJ": quote(25.0)})
    p = planner.make_plan(sig, snap, pcfg, NOW, 1, {}, **dict(kw, sleeve=sleeve))
    assert p["orders"] == [] and "hold only" in {x["asset"]: x["reason"] for x in p["skipped"]}["JJJ"]


def test_stock_favorites_past_the_liquidity_and_max_assets_cuts(state):
    """allocation.favorites (any case) are scanned past min_dollar_volume_usd and max_assets; max_assets keeps the
    most liquid non-favorites, so no other ticker is displaced."""
    write_tradability(paths()["inbox"])
    base = [a["name"] for a in build(stock_cfg(equity={"max_assets": 9}))[0]]
    assets, rep = build(stock_cfg(equity={"max_assets": 9}, favorites=["iii", "OOO"]))
    t = by_ticker(rep)
    assert t["III"]["outcome"] == "stock" and t["III"]["favorite"] and t["III"]["hold_only"] is None
    assert "included (favorite; below the liquidity cut $500,000/day, need $1,000,000" in t["III"]["reason"]
    assert t["OOO"]["outcome"] == "stock" and "included (favorite; beyond max_assets 9 (rank" in t["OOO"]["reason"]
    assert "favorites do not count against it)" in t["OOO"]["reason"]
    for k in ("KKK", "NNN"):
        assert t[k]["category"] == "beyond max_assets" and "not counting 2 favorites" in t[k]["reason"], k
    assert [a["name"] for a in assets if a["name"] not in ("III", "OOO")] == base
    assert sorted(a["name"] for a in assets) == sorted(base + ["III", "OOO"])
    iii = next(a for a in assets if a["name"] == "III")
    assert iii["enabled"] and iii["vehicle"] == {"type": "equity", "symbol": "III", "fractional": True}
    eff, warns = stocks.with_equity_universe(validate(stock_cfg()), {"universe_equity": {"assets": assets}})
    assert warns == [] and {"III", "OOO"} <= {a["name"] for a in eff["assets"]}
    lines = stocks.summary_lines(rep)
    assert "incl. 2 favorites kept past the liquidity or max_assets cut" in lines[0]
    assert any(x.startswith("    III: tradable on the account") and "included (favorite;" in x for x in lines)
    assert any(x.startswith("    OOO: ") for x in lines)
    _, rep = build(stock_cfg(equity={"max_assets": 9}))                          # without favorites, as before
    assert by_ticker(rep)["III"]["category"] == "illiquid" and by_ticker(rep)["OOO"]["category"] == "beyond max_assets"
    assert not any(e["favorite"] for e in rep["tickers"])


def test_stock_favorites_still_need_every_other_filter(state):
    """A favorite ticker skips only the liquidity and max_assets cuts: explicit precedence, a disabled entry, the
    crypto universe's ETFs, exclude, Robinhood tradability, data, current bars and the history rule (watch-only)
    still apply."""
    write_tradability(paths()["inbox"])
    fr = {t: stock_frame(t, forming=False) for t in STOCKS}
    fr["HHH"] = stock_frame("HHH", last=cal.previous_trading_day(cal.previous_trading_day(EQ_END)), forming=False)
    disabled = {"name": "EEE", "class": "equity", "enabled": False, "alloc_frac": 0.1, "mode": "split",
                "signal": {"source": "computed", "feed": "robinhood", "symbol": "EEE"},
                "vehicle": {"type": "equity", "symbol": "EEE"}}
    etf_coin = {"name": "XYZ", "class": "crypto", "enabled": False, "vehicle": {"type": "equity", "symbol": "DDD"},
                "signal": {"feed": "coinbase", "symbol": "XYZ-USD"}, "universe": {"outcome": "watch"}}
    favs = ["LLL", "mmm", "KKK", "JJJ", "ZZZ", "EEE", "DDD", "HHH"]
    raw = stock_cfg(equity={"symbols": TICKERS + ["ZZZ"], "exclude": ["KKK"]}, favorites=favs, assets=[disabled])
    assets, rep = build(raw, crypto_assets=[etf_coin], fetch=frames_fetch(frames=fr))
    t = by_ticker(rep)
    for k, cat, why in (("LLL", "not found on Robinhood", "check the ticker"),
                        ("MMM", "not tradable on Robinhood", "'inactive'"),
                        ("KKK", "excluded by config", "in universe.equity.exclude"),
                        ("ZZZ", "data error", "no rows for ZZZ"),
                        ("DDD", "covered by the crypto universe", "for XYZ"),
                        ("HHH", "stale data", "stale data")):
        assert t[k]["outcome"] == "excluded" and t[k]["category"] == cat and why in t[k]["reason"], k
        assert t[k]["favorite"] and t[k]["favorite_kept"] is None, k
    assert t["EEE"]["outcome"] == "explicit" and "(disabled)" in t["EEE"]["reason"]
    assert t["JJJ"]["outcome"] == "watch" and "too little history (100 bars, need 150)" in t["JJJ"]["reason"]
    assert "favorite" not in t["JJJ"]["reason"]
    by = {a["name"]: a for a in assets}
    assert not set(by) & {"LLL", "MMM", "KKK", "ZZZ", "EEE", "DDD", "HHH"} and by["JJJ"]["enabled"] is False
    # no tradability capture: a favorite is watch-only like any ticker
    for f in paths()["inbox"].glob("*.json"):
        f.unlink()
    t = by_ticker(build(stock_cfg(favorites=["III"]))[1])
    assert t["III"]["outcome"] == "watch" and "no get_equity_tradability capture" in t["III"]["reason"]
    assert "included (favorite; below the liquidity cut" in t["III"]["reason"]


def test_stock_favorite_named_like_a_coin_accepts_either_name(state):
    """A ticker that equals a crypto universe coin's code is named TICKER-STOCK; as a favorite either name counts in the
    scan. The planner's tie-break matches TICKER-STOCK under either name, a bare name only as the asset's name
    (test_ticker_stock_favorite_wins_ties_under_either_name)."""
    write_tradability(paths()["inbox"])
    coin = {"name": "III", "class": "crypto", "enabled": True, "vehicle": {"type": "crypto", "symbol": "III"},
            "signal": {"feed": "coinbase", "symbol": "III-USD"}, "universe": {"outcome": "direct"}}
    for favs in (["III-STOCK"], ["iii-stock"], ["III"]):
        assets, rep = build(stock_cfg(favorites=favs), crypto_assets=[coin])
        t = by_ticker(rep)["III"]
        assert t["name"] == "III-STOCK" and t["outcome"] == "stock" and t["favorite"], favs
        assert "included (favorite; below the liquidity cut" in t["reason"] and "named III-STOCK" in t["reason"]
        assert next(a for a in assets if a["name"] == "III-STOCK")["vehicle"]["symbol"] == "III"
    assert by_ticker(build(stock_cfg(favorites=["III-COIN"]), crypto_assets=[coin])[1])["III"]["category"] == \
        "illiquid"
    assert planner._favorites(validate(stock_cfg(favorites=["iii", "AAA-STOCK"]))) == {"III": 1, "AAA-STOCK": 2}


def test_with_equity_universe_rechecks_stored_assets(state):
    write_tradability(paths()["inbox"])
    raw = stock_cfg()
    assets, _ = build(raw)
    good = {"universe_equity": {"assets": assets}}
    eff, warns = stocks.with_equity_universe(validate(raw), good)
    assert warns == [] and len(eff["assets"]) == 1 + len(assets)
    bad = [dict(assets[0], name="OTHER"), dict(assets[1], signal={"source": "computed", "feed": "robinhood",
                                                                  "symbol": assets[1]["vehicle"]["symbol"]}),
           dict(assets[2], vehicle={"type": "crypto", "symbol": "X"})]
    eff, warns = stocks.with_equity_universe(validate(raw), {"universe_equity": {"assets": bad}})
    assert len(eff["assets"]) == 1 and len(warns) == 3 and all("re-run signals" in w for w in warns)


# ------------------------------------------------------------------ yfinance cache

def test_yfinance_batch_incremental_unclosed_and_split(state, monkeypatch):
    fake = install_yf(monkeypatch)
    syms = ["AAA", "BBB", "CCC"]
    r = feeds.yfinance_daily_cached(syms, "2024-11-01", NOW)
    assert len(fake.calls) == 1 and fake.calls[0][0] == syms                    # one batch for every ticker
    assert r["errors"] == {} and r["down"] is None
    for s in syms:
        assert r["bars"][s].index[-1].date() == EQ_END                          # the forming 10-19 session dropped
        assert list(r["bars"][s].columns) == ["open", "high", "low", "close", "volume"]
        assert r["bars"][s]["close"].iloc[-1] == pytest.approx(fake.frames[s]["close"].iloc[-2])
        assert (feeds.yfinance_cache_dir() / f"{s}.csv").exists()
    assert feeds.yfinance_daily_cached(syms, "2024-11-01", NOW + timedelta(hours=2))["bars"]["AAA"].equals(
        r["bars"]["AAA"]) and len(fake.calls) == 1                                 # current: no download
    nxt = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)                                # Tuesday: one new session
    for s in syms:
        fake.frames[s] = stock_frame(s, date(2026, 10, 19))
    r2 = feeds.yfinance_daily_cached(syms, "2024-11-01", nxt)
    assert len(fake.calls) == 2 and fake.calls[1][0] == syms
    assert fake.calls[1][1] == "2026-10-09"                                     # 5 sessions before the last cached bar
    assert r2["bars"]["AAA"].index[-1].date() == date(2026, 10, 19)
    assert len(r2["bars"]["AAA"]) == len(r["bars"]["AAA"]) + 1 or r2["bars"]["AAA"].index[0] >= pd.Timestamp(
        "2024-11-01")
    nxt2 = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)
    f = stock_frame("BBB", date(2026, 10, 20))
    f[["open", "high", "low", "close"]] /= 2.0                                     # a 2:1 split: history adjusted
    fake.frames["BBB"] = f
    for s in ("AAA", "CCC"):
        fake.frames[s] = stock_frame(s, date(2026, 10, 20))
    issues = []
    r3 = feeds.yfinance_daily_cached(syms, "2024-11-01", nxt2, issues=issues)
    assert [c[0] for c in fake.calls[2:]] == [syms, ["BBB"]]                       # the split one fetched again in full
    assert fake.calls[3][1] == "2024-11-01" and any("a split since the last download" in x for x in issues)
    d0 = r3["bars"]["BBB"].index[0]
    assert r3["bars"]["BBB"].loc[d0, "close"] == pytest.approx(f.loc[d0, "close"])          # the adjusted history


def test_yfinance_outage_breaker_missing_ticker_and_missing_package(state, monkeypatch):
    fake = install_yf(monkeypatch)
    feeds.yfinance_daily_cached(["AAA"], "2024-11-01", NOW)
    fake.down = True
    nxt = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
    issues = []
    r = feeds.yfinance_daily_cached(["AAA", "BBB"], "2024-11-01", nxt, issues=issues, sleep=lambda s: None)
    # AAA's incremental batch (cached) first: 1 + 2 retries, then the breaker: BBB (no cache) is not tried
    assert len(fake.calls) == 1 + 3 and r["down"].startswith("yfinance download failed (ConnectionError")
    assert [c[0] for c in fake.calls[1:]] == [["AAA"]] * 3
    assert any("no further downloads this run" in x for x in issues)
    assert r["bars"]["AAA"].index[-1].date() == EQ_END                          # stale cache returned as it is
    assert "BBB" not in r["bars"] and "download failed" in r["errors"]["BBB"]
    fake.down = False
    fake.missing = {"BBB"}
    r = feeds.yfinance_daily_cached(["BBB", "CCC"], "2024-11-01", NOW)
    assert "wrong ticker, not listed yet, or delisted" in r["errors"]["BBB"] and "CCC" in r["bars"]
    assert fake.calls[-1][0] == ["BBB"]                                         # the missing one retried once alone
    monkeypatch.setitem(sys.modules, "yfinance", None)
    r = feeds.yfinance_daily_cached(["DDD"], "2024-11-01", NOW)
    assert "yfinance is not installed" in r["errors"]["DDD"] and "-m pip install yfinance" in r["errors"]["DDD"]
    a = {"name": "DDD", "class": "equity", "mode": "split", "enabled": True, "alloc_frac": 0.1,
         "signal": {"source": "computed", "feed": "yfinance", "symbol": "DDD"}, "vehicle": {"type": "equity",
                                                                                          "symbol": "DDD"}}
    s = sg.asset_signal(a, validate(stock_cfg()), NOW, paths()["inbox"], "")
    assert any("pip install yfinance" in e for e in s["errors"])
    rep = doctor.Report()
    doctor.check_stocks(rep, validate(stock_cfg()), paths())
    assert any(st == "FAIL" and n == "yfinance" and "-m pip install yfinance" in d for st, n, d in rep.rows)
    rep = doctor.Report()
    doctor.check_stocks(rep, validate(stock_cfg(equity={"enabled": False})), paths())
    assert not any(st == "FAIL" for st, n, d in rep.rows)


def test_yfinance_ticker_yahoo_does_not_know_never_trips_the_breaker(state, monkeypatch):
    """Regression: a new ticker Yahoo returns nothing for (renamed, not trading yet, another spelling) is an error for
    that ticker only; the cached tickers still get their new bars, so a held one can still be sold."""
    fake = install_yf(monkeypatch, last=date(2026, 10, 19))            # one history: day 1 sees it up to 10-16
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: {"equity": {"DDD"}, "crypto": set()})
    syms = ["AAA", "BBB", "DDD", "EEE"]
    write_tradability(paths()["inbox"], symbols=syms)
    sg.compute_signals(validate(stock_cfg(equity={"symbols": syms})), NOW, paths()["inbox"])
    nxt = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
    tr = tradability_response(syms)
    tr["data"]["results"].append(dict(tr["data"]["results"][0], symbol="ZZZ", name="ZZZ Placeholder Inc."))
    write_cap(paths()["inbox"], "get_equity_tradability", tr, {"account_number": ACCT, "symbols": syms + ["ZZZ"]},
              nxt - timedelta(minutes=5))
    n0 = len(fake.calls)
    sig = sg.compute_signals(validate(stock_cfg(equity={"symbols": syms + ["ZZZ"]})), nxt, paths()["inbox"])
    assert [c[0] for c in fake.calls[n0:]] == [syms, ["ZZZ"]]          # cached first; ZZZ once (yfinance answered)
    rep = sig["universe_equity"]["report"]
    assert rep["data_down"] is None
    by = by_ticker(rep)
    assert by["ZZZ"]["category"] == "data error" and "no rows for ZZZ" in by["ZZZ"]["reason"]
    assert all(by[t]["outcome"] == "stock" for t in ("AAA", "BBB", "EEE"))
    ddd = next(a for a in sig["assets"] if a["name"] == "DDD")
    assert ddd["errors"] == [] and ddd["bar_date"] == "2026-10-19" and ddd["held"]
    fake.down = True                                                     # a real outage still trips it
    issues = []
    r = feeds.yfinance_daily_cached(syms + ["ZZZ"], "2024-11-01", datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
                                    issues=issues)
    assert r["down"].startswith("yfinance download failed") and set(r["bars"]) == set(syms)
    fake.down, fake.missing = False, set(syms)                           # no rows for cached tickers: an outage
    r = feeds.yfinance_daily_cached(syms, "2024-11-01", datetime(2026, 10, 21, 15, 0, tzinfo=UTC), sleep=lambda s: 0)
    assert r["down"] == f"yfinance download failed ({feeds.YF_EMPTY})"


def test_signals_batch_yfinance_once_and_digest_covers_stocks(state, monkeypatch):
    fake = install_yf(monkeypatch)
    write_tradability(paths()["inbox"])
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: {"equity": set(), "crypto": set()})
    sig = sg.compute_signals(validate(stock_cfg()), NOW, paths()["inbox"])
    assert len(fake.calls) == 1 and set(fake.calls[0][0]) == set(STOCKS) - NOT_FOUND - INACTIVE
    by = {a["name"]: a for a in sig["assets"]}
    assert len(sig["universe_equity"]["assets"]) == 12 and sig["universe"] is None
    assert by["AAA"]["errors"] == [] and by["AAA"]["target_frac"] == 1.0 and by["AAA"]["entry_frac"] == 1.0
    assert by["AAA"]["dollar_volume_usd"] == pytest.approx(9e8, rel=1e-6)
    assert by["CCC"]["entry_frac"] == 0.0 and by["DDD"]["target_frac"] == 0.0
    assert by["AAA"]["crosscheck"].startswith("not checked yet")              # no quote captured yet
    assert by["JJJ"]["enabled"] is False and by["JJJ"]["errors"] == [] and by["JJJ"]["bars"] == 100    # watch-only
    assert not sg._eligible(by["JJJ"]) and "(watch: too little history (100 bars, need 150))" in sg._signal(by["JJJ"])
    fresh = {t for t, v in STOCKS.items() if v[0] == "fresh"} - NOT_FOUND - INACTIVE - {"III", "JJJ"}
    assert {last for last in by if sg._eligible(by[last])} == fresh
    text = sg.format_digest(sig)
    assert "UNIVERSE stocks (feed yfinance" in text and "SCAN 12 assets (0 explicit, 12 universe)" in text
    assert "ACTION" not in text and "  SIGNAL" in text and sg.SIGNAL_NOTE in text
    sig2 = sg.compute_signals(validate(stock_cfg()), NOW + timedelta(hours=1), paths()["inbox"])
    assert len(fake.calls) == 1 and len(sig2["assets"]) == 12                       # cached: no second download


def test_yfinance_batch_never_makes_coinbase_offline(state, monkeypatch):
    """Regression: the yfinance batch marks only yfinance as cache-only; an explicit Coinbase asset still fetches."""
    install_yf(monkeypatch)
    write_tradability(paths()["inbox"])
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: {"equity": set(), "crypto": set()})
    cb = FakeCoinbase(date(2026, 10, 18))
    monkeypatch.setattr(urllib.request, "urlopen", cb)
    eth = {"name": "LINK", "class": "crypto", "enabled": True, "alloc_frac": 0.1, "mode": "split",
           "signal": {"source": "computed", "feed": "coinbase", "symbol": "LINK-USD"},
           "vehicle": {"type": "crypto", "symbol": "LINK"}}
    old = coin_frame("LINK", date(2026, 10, 10), forming=False)                 # a stale cache
    feeds._write_atomic(feeds.coinbase_cache_dir() / "LINK-USD.csv",
                        old.to_csv(index_label="date", date_format="%Y-%m-%d"))
    sig = sg.compute_signals(validate(stock_cfg(assets=[eth])), NOW, paths()["inbox"])
    link = next(a for a in sig["assets"] if a["name"] == "LINK")
    assert link["errors"] == [] and link["bar_date"] == "2026-10-18" and cb.urls


# ------------------------------------------------------------------ Robinhood cache and fetch-list windows

def rh_bars(frame):
    return [{"begins_at": f"{d.date().isoformat()}T13:30:00Z", "open_price": f"{r.open:.4f}",
             "close_price": f"{r.close:.4f}", "high_price": f"{r.high:.4f}", "low_price": f"{r.low:.4f}",
             "volume": int(r.volume), "session": "reg", "interpolated": False} for d, r in frame.iterrows()]


def hist_response(params, frames):
    """What get_equity_historicals returns for these params (synthetic frames), bars in [start, end)."""
    s = pd.Timestamp(params["start_time"]).tz_convert(None).normalize()
    e = pd.Timestamp(params["end_time"]).tz_convert(None).normalize() if params.get("end_time") else None
    res = []
    for sym in params["symbols"]:
        f = frames[sym]
        f = f[(f.index >= s) & ((f.index < e) if e is not None else True)]
        res.append({"symbol": sym, "interval": "day", "bounds": "regular", "bars": rh_bars(f)})
    return env({"results": res})


def capture_calls(calls, frames, at):
    for k, c in enumerate(calls):
        write_cap(paths()["inbox"], c["tool"], hist_response(c["params"], frames), c["params"],
                  at + timedelta(seconds=k))


def test_robinhood_history_windows_incremental_groups_and_split_refetch(state):
    syms = [f"S{k:02d}" for k in range(12)]
    starts = {s: date(2024, 11, 18) for s in syms}
    frames = {s: trend(cal.trading_days(date(2024, 6, 3), date(2026, 10, 27)), 50.0 + k) for k, s in
              enumerate(syms)}                                                   # later bars are cut at capture time
    for f in frames.values():
        f["volume"] = 1e6
    calls = stocks.history_calls(starts, NOW)
    sessions = cal.trading_days(date(2024, 11, 18), EQ_END)
    per = -(-len(sessions) // stocks.RH_BACKFILL_SESSIONS)
    assert len(calls) == 12 * per and all(len(c["params"]["symbols"]) == 1 for c in calls)
    w = [c["params"] for c in calls if c["params"]["symbols"] == ["S00"]]
    assert w[0]["start_time"] == "2024-11-18T00:00:00Z" and "end_time" not in w[-1]
    assert all(a["end_time"] == b["start_time"] for a, b in zip(w, w[1:]))       # windows touch, never overlap
    for a, b in zip(w, w[1:]):
        n = len(cal.trading_days(date.fromisoformat(a["start_time"][:10]),
                                 date.fromisoformat(b["start_time"][:10]) - timedelta(days=1)))
        assert n <= stocks.RH_BACKFILL_SESSIONS
    capture_calls(calls, frames, NOW - timedelta(minutes=5))
    got = feeds.load_robinhood_bars(paths()["inbox"], syms, NOW, cache_dir=feeds.robinhood_cache_dir())
    assert got["S03"].index[-1].date() == EQ_END and len(got["S03"]) == len(sessions)
    assert (feeds.robinhood_cache_dir() / "S03.csv").exists()
    assert stocks.history_calls(starts, NOW + timedelta(hours=1)) == []           # covered: nothing to ask
    # a week later: one incremental call per <= 10 symbols, from 5 sessions before the last cached bar
    later = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)                           # Tuesday: 10-19 .. 10-26 missing
    calls = stocks.history_calls(starts, later)
    assert [len(c["params"]["symbols"]) for c in calls] == [10, 2]
    p = calls[0]["params"]
    assert p["start_time"] == "2026-10-09T00:00:00Z" and "end_time" not in p and p["adjustment_type"] == "split"
    n = len(cal.trading_days(date(2026, 10, 9), date(2026, 10, 26)))
    assert 10 * n <= stocks.RH_MAX_BARS_PER_CALL
    frames["S05"][["open", "high", "low", "close"]] /= 3.0                         # a 3:1 split in S05
    capture_calls(calls, frames, later - timedelta(minutes=5))
    issues = []
    got = feeds.load_robinhood_bars(paths()["inbox"], syms, later, issues, cache_dir=feeds.robinhood_cache_dir())
    assert got["S01"].index[-1].date() == date(2026, 10, 26) and len(got["S01"]) > 400
    assert len(got["S05"]) < 20 and any("S05" in x and "split" in x for x in issues)
    again = stocks.history_calls(starts, later + timedelta(minutes=30))
    assert again and all(c["params"]["symbols"] == ["S05"] for c in again)       # the split one: full backfill
    assert again[0]["params"]["start_time"] == "2024-11-18T00:00:00Z"


def rh_cache(syms, last, frames):
    """A Robinhood cache for `syms` ending on `last` (as merged from earlier captures)."""
    cdir = feeds.robinhood_cache_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    meta = {}
    for s in syms:
        f = frames[s]
        f = f[(f.index >= pd.Timestamp("2024-11-18")) & (f.index <= pd.Timestamp(last))]
        feeds._write_bars(cdir / f"{s}.csv", f)
        meta[s] = {"covered": [["2024-11-18", last.isoformat()]], "merged": ["", ""]}
    (cdir / "meta.json").write_text(json.dumps(meta))


def result_chars(params, frames):
    """Characters of the get_equity_historicals result as Claude Code sees it (6-decimal prices, a long volume)."""
    r = hist_response(params, frames)
    for it in r["data"]["results"]:
        for b in it["bars"]:
            b.update({k: f"{float(b[k]):.6f}" for k in ("open_price", "close_price", "high_price", "low_price")},
                     volume=987654321)
    return len(json.dumps(r))


NOTICE = ("Error: MCP tool \"get_equity_historicals\" response (31544 tokens) exceeds maximum allowed tokens (25000).")


def too_large(params, at):
    f = write_cap(paths()["inbox"], "get_equity_historicals", NOTICE, params, at)
    raw = json.loads(f.read_text())
    raw.update(capture_error="response_too_large", response_head=NOTICE)          # as the PostToolUse hook saves it
    f.write_text(json.dumps(raw))


def test_robinhood_calls_stay_under_claude_codes_50k_characters_and_too_large_ones_get_smaller(state):
    """Regression: incremental groups of up to 400 bars came to 52-70k characters (Claude Code saves any result over
    50,000 to a file), and a call that came back too large was asked for again unchanged."""
    syms = [f"T{k:02d}" for k in range(20)]
    frames = {s: trend(cal.trading_days(date(2024, 6, 3), EQ_END), 300.0 + k) for k, s in enumerate(syms)}
    for f in frames.values():
        f["volume"] = 1e8
    starts = {s: date(2024, 11, 18) for s in syms}
    sessions = cal.trading_days(date(2024, 11, 18), EQ_END)
    for gap in (1, 5, 25, 30, 35, 40, 60, 100, 119, 121, 160):
        rh_cache(syms, sessions[-1 - gap], frames)
        calls = stocks.history_calls(starts, NOW)
        assert calls and {s for c in calls for s in c["params"]["symbols"]} == set(syms)
        big = max(result_chars(c["params"], frames) for c in calls)
        assert big < stocks.RH_MAX_RESULT_CHARS + 5000 < 50_000, (gap, big)
    rh_cache(syms[:10], sessions[-36], frames)                       # 5 weeks without a run, 10 tickers
    starts = {s: date(2024, 11, 18) for s in syms[:10]}
    first = stocks.history_calls(starts, NOW)
    assert all(len(c["params"]["symbols"]) > 1 for c in first)
    for k, c in enumerate(first):
        too_large(c["params"], NOW - timedelta(minutes=9) + timedelta(seconds=k))
    again = stocks.history_calls(starts, NOW + timedelta(minutes=10))
    assert all(len(c["params"]["symbols"]) == 1 for c in again) and len(again) == 10    # one symbol per call
    assert {c["params"]["start_time"] for c in again} == {c["params"]["start_time"] for c in first}
    assert "too large for Claude Code last time" in again[0]["why"]
    too_large(again[0]["params"], NOW + timedelta(minutes=11))      # still too large: halves of its window
    third = stocks.history_calls(starts, NOW + timedelta(minutes=12))
    t0 = again[0]["params"]["symbols"]
    halves = [c["params"] for c in third if c["params"]["symbols"] == t0]
    assert len(halves) == 2 and halves[0]["start_time"] == again[0]["params"]["start_time"]
    assert halves[0]["end_time"] == halves[1]["start_time"] and "end_time" not in halves[1]
    assert [c["params"] for c in third if c["params"]["symbols"] != t0] == [c["params"] for c in again[1:]]
    capture_calls(third, frames, NOW + timedelta(minutes=13))
    assert stocks.history_calls(starts, NOW + timedelta(minutes=14)) == []
    got = feeds.load_robinhood_bars(paths()["inbox"], syms[:10], NOW, cache_dir=feeds.robinhood_cache_dir())
    assert all(got[s].index[-1].date() == EQ_END and len(got[s]) == len(sessions) for s in syms[:10])


def test_robinhood_long_gap_backfill_overlaps_the_cache_so_a_split_is_caught(state):
    """Regression: a cache ending more than 120 sessions back was filled with windows that never overlapped it, so a
    split in the gap went unseen and the asset failed for good ('close ratio 0.501 is near 0.5')."""
    sessions = cal.trading_days(date(2024, 6, 3), EQ_END)
    full = trend(sessions, 50.0)
    full["volume"] = 1e6
    starts = {"AAA": date(2024, 11, 18)}
    old_end = sessions[-151]
    then = datetime.combine(cal.next_trading_day(old_end), datetime.min.time(), UTC) + timedelta(hours=15)
    capture_calls(stocks.history_calls(starts, then), {"AAA": full}, then - timedelta(minutes=5))
    feeds.load_robinhood_bars(paths()["inbox"], ["AAA"], then, cache_dir=feeds.robinhood_cache_dir())
    adj = full.copy()
    adj[["open", "high", "low", "close"]] /= 2.0                     # a 2:1 split since: the history re-adjusted
    calls = stocks.history_calls(starts, NOW)
    first = date.fromisoformat(calls[0]["params"]["start_time"][:10])
    assert len(cal.trading_days(first, old_end)) == 1 + feeds.OVERLAP_SESSIONS + 1 - 1   # 5 sessions of overlap
    capture_calls(calls, {"AAA": adj}, NOW - timedelta(minutes=5))
    issues = []
    feeds.load_robinhood_bars(paths()["inbox"], ["AAA"], NOW, issues, cache_dir=feeds.robinhood_cache_dir())
    assert any(x.startswith(feeds.SPLIT_NOTE) for x in issues)
    rest = stocks.history_calls(starts, NOW + timedelta(minutes=5))
    assert rest and rest[0]["params"]["start_time"] == "2024-11-18T00:00:00Z"   # the older history again
    capture_calls(rest, {"AAA": adj}, NOW + timedelta(minutes=6))
    a = {"name": "AAA", "class": "equity", "mode": "split", "enabled": True, "alloc_frac": 0.1, "min_bars": 150,
         "signal": {"source": "computed", "feed": "robinhood", "symbol": "AAA"}, "vehicle": {"type": "equity",
                                                                                           "symbol": "AAA"}}
    s = sg.asset_signal(a, validate(stock_cfg()), NOW + timedelta(minutes=7), paths()["inbox"], "")
    assert s["errors"] == [] and not any(feeds.SPLIT_NOTE in w for w in s["warnings"])
    assert s["close"] == pytest.approx(float(adj["close"].iloc[-1]), rel=1e-4)


def test_robinhood_split_is_reported_until_the_history_is_back(state, monkeypatch, capsys):
    """Regression: after a split the asset only said 'only 8 bars, need 150'; now the signal says a split was found
    and `signals` tells Claude to run fetch-list again (once per run)."""
    frames = {"AAA": stock_frame("AAA", forming=False)}
    inbox = paths()["inbox"]
    starts = {"AAA": date(2024, 11, 18)}
    capture_calls(stocks.history_calls(starts, NOW), frames, NOW - timedelta(minutes=5))
    later = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)
    f = stock_frame("AAA", date(2026, 10, 20), forming=False)
    f[["open", "high", "low", "close"]] /= 2.0
    frames["AAA"] = f
    capture_calls(stocks.history_calls(starts, later), frames, later - timedelta(minutes=5))
    a = {"name": "AAA", "class": "equity", "mode": "split", "enabled": True, "alloc_frac": 0.1, "min_bars": 150,
         "signal": {"source": "computed", "feed": "robinhood", "symbol": "AAA"}, "vehicle": {"type": "equity",
                                                                                           "symbol": "AAA"}}
    cfg = validate(stock_cfg(equity={"enabled": False}, assets=[a]))
    for _ in range(2):                                               # the second load reads the cache's meta
        s = sg.asset_signal(a, cfg, later, inbox, "")
        assert any("bars, need 150" in e for e in s["errors"])
        assert [w for w in s["warnings"] if w.startswith(feeds.SPLIT_NOTE)] and "run fetch-list again" in \
            s["warnings"][0]
    paths()["base"].mkdir(parents=True, exist_ok=True)
    paths()["config"].write_text(json.dumps(stock_cfg(equity={"enabled": False}, assets=[a])))
    monkeypatch.setattr(cli, "_now", lambda: later)
    capsys.readouterr()
    assert cli.main(["signals"]) == 1
    err = capsys.readouterr().err
    assert "ACTION: split detected for AAA" in err and "fetch-list` again" in err
    again = stocks.history_calls(starts, later + timedelta(minutes=1))
    assert again[0]["params"]["start_time"] == "2024-11-18T00:00:00Z"
    capture_calls(again, frames, later + timedelta(minutes=2))
    s = sg.asset_signal(a, cfg, later + timedelta(minutes=3), inbox, "")
    assert s["errors"] == [] and not any(feeds.SPLIT_NOTE in w for w in s["warnings"])
    assert cli.main(["signals"]) == 0 and "ACTION" not in capsys.readouterr().err


def test_robinhood_loader_skips_merged_captures_without_parsing_them(state, monkeypatch):
    """Regression: every capture in the never-pruned inbox was parsed again on each load (once per asset)."""
    frames = {"AAA": stock_frame("AAA", forming=False), "BBB": stock_frame("BBB", forming=False)}
    starts = {"AAA": date(2024, 11, 18), "BBB": date(2024, 11, 18)}
    capture_calls(stocks.history_calls(starts, NOW), frames, NOW - timedelta(minutes=9))
    old = {"symbols": ["AAA"], "start_time": "2026-10-01T00:00:00Z", "interval": "day", "bounds": "regular",
           "adjustment_type": "split"}
    too_large(old, NOW - timedelta(minutes=8))
    cdir = feeds.robinhood_cache_dir()
    first = feeds.load_robinhood_bars(paths()["inbox"], ["AAA", "BBB"], NOW, cache_dir=cdir)
    seen = []
    real = json.loads
    monkeypatch.setattr(feeds.json, "loads", lambda t, *a, **k: seen.append(1) or real(t, *a, **k))
    got = feeds.load_robinhood_bars(paths()["inbox"], ["BBB"], NOW, cache_dir=cdir)
    assert len(seen) == 2                                            # meta.json and the too-large notice only
    assert got["BBB"].equals(first["BBB"]) and got["BBB"].attrs["notes"] == []
    seen.clear()
    got = feeds.load_robinhood_bars(paths()["inbox"], ["AAA"], NOW, cache_dir=cdir)       # + BBB's newer windows
    assert len(seen) == 2 + len(list(paths()["inbox"].glob("*historicals*.json"))) // 2
    assert got["AAA"].equals(first["AAA"]) and len(got["AAA"].attrs["notes"]) == 1      # the newer too-large notice
    capture_calls(stocks.history_calls(starts, datetime(2026, 10, 20, 15, 0, tzinfo=UTC)),
                  {s: stock_frame(s, date(2026, 10, 19), forming=False) for s in frames},
                  datetime(2026, 10, 20, 14, 55, tzinfo=UTC))
    nxt = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
    got = feeds.load_robinhood_bars(paths()["inbox"], ["AAA"], nxt, cache_dir=cdir)
    assert got["AAA"].index[-1].date() == date(2026, 10, 19)                               # the new capture is read
    seen.clear()
    assert feeds.load_robinhood_bars(paths()["inbox"], ["AAA"], nxt, cache_dir=cdir)["AAA"].equals(got["AAA"])
    assert len(seen) == 2                                            # every older capture skipped by its file name


def test_robinhood_unparsable_and_too_large_captures_are_skipped(state):
    frames = {"AAA": stock_frame("AAA", forming=False)}
    inbox = paths()["inbox"]
    good = {"symbols": ["AAA"], "start_time": "2024-11-18T00:00:00Z", "interval": "day", "bounds": "regular",
            "adjustment_type": "split"}
    write_cap(inbox, "get_equity_historicals", hist_response(good, frames), good, NOW - timedelta(minutes=9))
    notice = ("Error: MCP tool \"get_equity_historicals\" response (84213 tokens) exceeds maximum allowed tokens "
              "(25000). Please use pagination, filtering, or limit parameters to reduce the response size.")
    f = write_cap(inbox, "get_equity_historicals", notice, good, NOW - timedelta(minutes=5))
    raw = json.loads(f.read_text())
    raw.update(capture_error="response_too_large", response_head=notice[:300])
    f.write_text(json.dumps(raw))
    write_cap(inbox, "get_equity_historicals", {"content": [{"type": "text", "text": "Output too large; saved to "
                                                                               "file /tmp/x.txt"}]}, good,
              NOW - timedelta(minutes=4))
    issues = []
    got = feeds.load_robinhood_bars(inbox, ["AAA"], NOW, issues, cache_dir=feeds.robinhood_cache_dir())
    assert got["AAA"].index[-1].date() == EQ_END                                  # the good capture still counts
    assert sum(TOO_LARGE_HELP in x for x in issues) == 2 and all("JSONDecodeError" not in x for x in issues)
    assert len(got["AAA"].attrs["notes"]) == 2
    a = {"name": "AAA", "class": "equity", "mode": "immediate", "enabled": True, "alloc_frac": 0.1, "min_bars": 150,
         "signal": {"source": "computed", "feed": "robinhood", "symbol": "AAA"}, "vehicle": {"type": "equity",
                                                                                           "symbol": "AAA"}}
    s = sg.asset_signal(a, validate(stock_cfg()), NOW, inbox, "")
    assert s["errors"] == [] and any(TOO_LARGE_HELP in w for w in s["warnings"])
    for x in inbox.glob("*.json"):                                                # only the notice: a clear error
        x.unlink()
    for d in (feeds.robinhood_cache_dir(),):
        for x in d.glob("*"):
            x.unlink()
    write_cap(inbox, "get_equity_historicals", notice, good, NOW - timedelta(minutes=5))
    s = sg.asset_signal(a, validate(stock_cfg()), NOW, inbox, "")
    assert any(TOO_LARGE_HELP in e for e in s["errors"]) and not any("Expecting value" in e for e in s["errors"])


def test_robinhood_cache_survives_a_cleaned_inbox_and_a_bad_timestamp(state):
    frames = {"AAA": stock_frame("AAA", forming=False)}
    inbox, cdir = paths()["inbox"], feeds.robinhood_cache_dir()
    good = {"symbols": ["AAA"], "start_time": "2024-11-18T00:00:00Z", "interval": "day", "bounds": "regular",
            "adjustment_type": "split"}
    f = write_cap(inbox, "get_equity_historicals", hist_response(good, frames), good, NOW - timedelta(minutes=9))
    raw = json.loads(f.read_text())
    raw["captured_at"] = "not a time"                                  # unreadable: its last bar is dropped
    f.write_text(json.dumps(raw))
    issues = []
    got = feeds.load_robinhood_bars(inbox, ["AAA"], NOW, issues, cache_dir=cdir)
    assert got["AAA"].index[-1].date() == date(2026, 10, 15) and any("captured_at" in x for x in issues)
    write_cap(inbox, "get_equity_historicals", hist_response(good, frames), good, NOW - timedelta(minutes=5))
    got = feeds.load_robinhood_bars(inbox, ["AAA"], NOW, cache_dir=cdir)
    assert got["AAA"].index[-1].date() == EQ_END                      # a later capture still merges
    for x in inbox.glob("*.json"):
        x.unlink()
    got = feeds.load_robinhood_bars(inbox, ["AAA"], NOW, cache_dir=cdir)
    assert got["AAA"].index[-1].date() == EQ_END and got["AAA"]["volume"].iloc[-1] > 0     # from the cache alone
    a = {"name": "AAA", "class": "equity", "mode": "immediate", "enabled": True, "alloc_frac": 0.1, "min_bars": 150,
         "signal": {"source": "computed", "feed": "robinhood", "symbol": "AAA"}, "vehicle": {"type": "equity",
                                                                                           "symbol": "AAA"}}
    df = feeds.get_bars(a, validate(stock_cfg()), NOW, inbox)
    assert df.index[0] >= pd.Timestamp(NOW.date() - timedelta(days=700)) and df.index[-1].date() == EQ_END


def test_post_hook_records_too_large_results_and_never_blocks(state):
    validate(stock_cfg())
    paths()["base"].mkdir(parents=True, exist_ok=True)
    paths()["config"].write_text(json.dumps(stock_cfg()))
    ti = {"symbols": ["SPY"], "start_time": "2024-11-18T00:00:00Z", "interval": "day", "bounds": "regular",
          "adjustment_type": "split"}
    notice = "Error: MCP tool response (85432 tokens) exceeds maximum allowed tokens (25000)."
    for resp, code in ((notice, "response_too_large"),
                       ([{"type": "text", "text": "Output too large. Full output saved to: C:/Users/x/out.txt"}],
                        "response_too_large"),
                       ({"content": [{"type": "text", "text": "SPY: 502 bars"}]}, "not_json"),
                       (env({"results": []}), None)):
        for f in paths()["inbox"].glob("*.json"):
            f.unlink()
        r = hook(POST, state, "get_equity_historicals", ti, resp)
        assert r.returncode == 0
        (cap,) = [json.loads(f.read_text()) for f in paths()["inbox"].glob("*.json")]
        assert cap["response"] == resp and cap.get("capture_error") == code
        if code:
            assert cap["response_head"] == capture_problem(resp)[1] and len(cap["response_head"]) <= 300
        assert (TOO_LARGE_HELP in r.stderr.decode()) == (code == "response_too_large")
        caps = snapmod.load_captures(paths()["inbox"])
        assert (caps[0]["error"] == TOO_LARGE_HELP) == (code == "response_too_large")
    assert capture_problem({"isError": True, "content": [{"type": "text", "text": "upstream timeout"}]}) is None
    assert capture_problem(json.dumps(env({"x": 1}))) is None


# ------------------------------------------------------------------ cross-check and the planner

def sigrec(name, cls, tf, flip="2026-10-14", close=50.0, dv=1e8, bars_since=3, bar=None):
    green = tf > 0
    return {"name": name, "class": cls, "enabled": True, "target_frac": tf, "prev_target_frac": tf, "changed": False,
            "bar_date": bar or (EQ_END.isoformat() if cls == "equity" else "2026-10-18"), "close": close,
            "errors": [], "warnings": [], "dollar_volume_usd": dv, "entry_frac": tf,
            "tranches": [{"weight": 1.0, "n_entry": 1, "n_exit": 1, "green": green, "pending": 0, "line": close * 0.9,
                          "last_flip_date": flip, "last_green_flip_date": flip if green else None,
                          "bars_since_green_flip": bars_since if green else None,
                          "flip_close": close * 0.98 if green else None}]}


def uasset(name, cls="equity", feed="yfinance", vsym=None, held=False, hold_only=None):
    vsym = vsym or name
    vt = "crypto" if cls == "crypto" and feed == "coinbase" else "equity"
    return {"name": name, "class": cls, "enabled": True, "alloc_frac": 0.0, "mode": "immediate",
            "signal": {"source": "computed", "feed": feed, "symbol": f"{vsym}-USD" if vt == "crypto" else vsym},
            "vehicle": {"type": vt, "symbol": vsym, "fractional": False},
            "universe": {"outcome": "stock" if cls == "equity" else "direct", "held": held, "hold_only": hold_only}}


def quote(px, t=None, pc=None, pcd=EQ_END.isoformat()):
    t = t or (NOW - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"bid": px * 0.999, "ask": px * 1.001, "last": px, "ts": t, "captured_at": t, "kind": "equity",
            "problem": None, "previous_close": px if pc is None else pc, "previous_close_date": pcd}


def mini(assets, sigs, quotes, positions=None, favorites=(), cash=10000.0, cap=None, slot_frac=0.10):
    raw = stock_cfg(assets=[], favorites=list(favorites))
    raw["allocation"]["slot_frac"] = slot_frac
    if cap:
        raw["allocation"]["class_max_frac"] = cap
    cfg = validate(raw)
    cfg["assets"] = assets
    pos = positions or {}
    snap = dict(as_of=NOW.isoformat(), total_value=cash + sum(q * quotes[s]["last"] for s, q in pos.items()),
                cash=cash, buying_power=cash, crypto_buying_power=cash,
                equity_positions={s: {"qty": q, "sellable": q} for s, q in pos.items() if "-" not in s},
                crypto_positions={}, quotes=quotes, open_orders=[], orders=[],
                pairs={f"{a['vehicle']['symbol']}-USD": {"min_order_size": "0.01", "asset_increment": "0.01",
                                                         "quote_increment": "0.0001", "tradability": "tradable"}
                       for a in assets if a["vehicle"]["type"] == "crypto"},
                account_number=ACCT, rhs_account_number=RHS, errors=[], warnings=[])
    sleeve = {"baseline": True, "sleeve": {"equity": dict(pos), "crypto": {}}, "mismatches": []}
    return cfg, {"date": "2026-10-19", "assets": sigs}, snap, sleeve


def test_crosscheck_problem_and_cross_check(state, monkeypatch):
    bars = stock_frame("AAA", forming=False)
    c = float(bars["close"].iloc[-1])
    assert stocks.crosscheck_problem("AAA", quote(c), bars) is None
    assert stocks.crosscheck_problem("AAA", quote(c, pc=c * 1.004), bars) is None                    # within 0.5%
    assert "differs from Robinhood's previous_close" in stocks.crosscheck_problem("AAA", quote(c, pc=c * 2), bars)
    assert "no cached yfinance bar for AAA on 2026-10-19" in stocks.crosscheck_problem(
        "AAA", quote(c, pcd="2026-10-19"), bars)
    assert "no previous_close" in stocks.crosscheck_problem("AAA", quote(c, pcd=None), bars)
    assert "no get_equity_quotes capture" in stocks.crosscheck_problem("AAA", None, bars)
    install_yf(monkeypatch)
    feeds.yfinance_daily_cached(["AAA", "DDD"], "2024-11-01", NOW)
    cfg = {"assets": [uasset("AAA"), uasset("DDD"), uasset("SPYX", feed="robinhood"), dict(uasset("OFF"),
                                                                                         enabled=False)]}
    cc = stocks.cross_check(cfg, {"quotes": {"AAA": quote(c), "DDD": quote(80.0, pc=1.0)}})
    assert set(cc) == {"AAA", "DDD"} and cc["AAA"] is None and "differs" in cc["DDD"]


def test_digest_crosscheck_skips_a_quote_older_than_the_bars(state):
    """Regression: the evening job compared the morning quote (previous_close 10-19, raw, before a split effective
    10-20) with the history downloaded after the split, and warned of a mismatch that the plan never saw."""
    f = stock_frame("AAA", date(2026, 10, 20), forming=False)
    raw_1019 = float(f.loc[pd.Timestamp("2026-10-19"), "close"])
    f[["open", "high", "low", "close"]] /= 2.0                                   # split-adjusted after 10-20
    feeds._write_bars(feeds.yfinance_cache_dir() / "AAA.csv", f)
    a = uasset("AAA")
    rec = {"warnings": []}
    stocks.signal_crosscheck(rec, a, {"AAA": quote(raw_1019 / 2, pc=raw_1019, pcd="2026-10-19")})
    assert rec["crosscheck"].startswith("not checked (the newest quote's previous_close_date 2026-10-19 is before "
                                        "the last bar 2026-10-20)") and rec["warnings"] == []
    c = float(f["close"].iloc[-1])
    rec = {"warnings": []}
    stocks.signal_crosscheck(rec, a, {"AAA": quote(c, pc=c, pcd="2026-10-20")})
    assert rec["crosscheck"] == "ok" and rec["warnings"] == []
    stocks.signal_crosscheck(rec, a, {"AAA": quote(c, pc=2 * c, pcd="2026-10-20")})       # same date: still caught
    assert "differs from Robinhood's previous_close" in rec["crosscheck"] and len(rec["warnings"]) == 1


def test_planner_crosscheck_blocks_buys_and_allows_exits(state):
    assets = [uasset("AAA"), uasset("DDD", held=True)]
    sigs = [sigrec("AAA", "equity", 1.0), sigrec("DDD", "equity", 0.0, close=80.0)]
    quotes = {"AAA": quote(50.0), "DDD": quote(80.0)}
    cfg, sig, snap, sleeve = mini(assets, sigs, quotes, positions={"DDD": 10.0})
    kw = dict(placed_today_usd=0.0, journal=[], sleeve=sleeve)
    ok = planner.make_plan(sig, snap, cfg, NOW, 1, {}, crosscheck={"AAA": None, "DDD": None}, **kw)
    assert sorted(o["key"] for o in ok["orders"]) == ["AAA|AAA|buy|0", "DDD|DDD|sell|0"]
    bad = {"AAA": "yfinance close 50.0000 for AAA differs", "DDD": "yfinance close 80.0000 for DDD differs"}
    p = planner.make_plan(sig, snap, cfg, NOW, 1, {}, crosscheck=bad, **kw)
    assert [o["key"] for o in p["orders"]] == ["DDD|DDD|sell|0"]                     # the exit still goes through
    sk = {x["asset"]: x["reason"] for x in p["skipped"]}
    assert "cross-check failed: yfinance close 50.0000 for AAA differs: no buys" in sk["AAA"]
    assert any(w.startswith("ALERT AAA: cross-check failed") and "buys blocked, exits allowed" in w
               for w in p["warnings"])
    assert p["errors"] == [] and "AAA" not in [x["asset"] for x in p["allocation"]["new"]]
    p = planner.make_plan(sig, snap, cfg, NOW, 1, {}, **kw)                          # never checked: no buys
    assert [o["key"] for o in p["orders"]] == ["DDD|DDD|sell|0"]
    assert "not cross-checked" in {x["asset"]: x["reason"] for x in p["skipped"]}["AAA"]


def test_favorites_order_ties_without_overriding_eligibility_or_caps(state):
    names = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    assets = [uasset(n) for n in names] + [uasset("LINK", "crypto", "coinbase"), uasset("UNI", "crypto", "coinbase")]
    dvs = {"AAA": 9e8, "BBB": 5e8, "CCC": 4e8, "DDD": 3e8, "EEE": 2e8, "LINK": 8e7, "UNI": 3e7}
    sigs = [sigrec(n, "equity", 1.0, dv=dvs[n]) for n in names]
    sigs[3] = sigrec("DDD", "equity", 1.0, dv=dvs["DDD"], bars_since=30)            # green too long: not eligible
    sigs += [sigrec(n, "crypto", 1.0, flip="2026-10-14", dv=dvs[n], close=10.0) for n in ("LINK", "UNI")]
    quotes = {n: quote(20.0) for n in names}
    quotes.update({f"{n}-USD": dict(quote(10.0), kind="crypto") for n in ("LINK", "UNI")})
    cc = {n: None for n in names}
    cfg, sig, snap, sleeve = mini(assets, sigs, quotes, cash=5000.0, slot_frac=0.20)            # 5 slots
    kw = dict(placed_today_usd=0.0, journal=[], sleeve=sleeve, crosscheck=cc)
    p = planner.make_plan(sig, snap, cfg, NOW, 1, {}, **kw)
    assert [x["asset"] for x in p["allocation"]["new"]] == ["LINK", "UNI", "AAA", "BBB", "CCC"]   # liquidity ties
    cfg, sig, snap, sleeve = mini(assets, sigs, quotes, cash=5000.0, favorites=["DDD", "UNI", "EEE", "ZZZ"],
                                  slot_frac=0.20)
    p = planner.make_plan(sig, snap, cfg, NOW, 1, {}, **dict(kw, sleeve=sleeve))
    new = [x["asset"] for x in p["allocation"]["new"]]
    assert new == ["UNI", "LINK", "EEE", "AAA", "BBB"]               # crypto_first, then favorites, then liquidity
    assert "DDD" not in new and "too late to join" in {x["asset"]: x["reason"] for x in p["skipped"]}["DDD"]
    reasons = {o["asset"]: o["reason"] for o in p["orders"]}
    assert "(#1 by crypto_first; favorite #2)" in reasons["UNI"] and "(#3 by crypto_first; favorite #3)" in \
        reasons["EEE"]
    assert "favorite" not in reasons["AAA"]
    assert [x["asset"] for x in p["allocation"]["waiting"]] == ["CCC"]
    # a newer flip still beats a favorite; the class cap still holds
    sigs2 = [dict(s) for s in sigs]
    sigs2[1] = sigrec("BBB", "equity", 1.0, flip="2026-10-15", dv=dvs["BBB"])
    cfg, sig, snap, sleeve = mini(assets, sigs2, quotes, cash=5000.0, favorites=["EEE"],
                                  cap={"crypto": 0.10, "equity": 1.0}, slot_frac=0.20)
    p = planner.make_plan(sig, snap, cfg, NOW, 1, {}, **dict(kw, sleeve=sleeve))
    assert [x["asset"] for x in p["allocation"]["new"]][:3] == ["LINK", "BBB", "EEE"]
    assert "UNI" in [x["asset"] for x in p["allocation"]["waiting"]]
    order = {a["name"]: i for i, a in enumerate(assets)}
    its = [{"name": n, "asset": a, "flip": "2026-10-14", "sig": {"dollar_volume_usd": dvs[n]}}
           for n, a in zip([a["name"] for a in assets], assets)]
    assert [x["name"] for x in planner._ranked(its, "config_order", order, {"EEE": 1})][:2] == ["AAA", "BBB"]


def test_ticker_stock_favorite_wins_ties_under_either_name(state):
    """Regression (review): a stock universe stock is named TICKER on runs where the crypto universe has no coin TICKER,
    and the tie-break matched the asset name only, so the documented `TICKER-STOCK` spelling won no tie on those runs
    (while the scan already counted it). It now matches the stock under either name; a bare name still matches only
    the asset of that name, and an explicit asset or a coin only by its name."""
    def ustock(name, t):
        a = uasset(name, vsym=t)
        a["universe"]["kind"] = "equity"
        return a

    def first(name, favorites):
        assets = [ustock(name, "AAA"), ustock("BBB", "BBB")]
        sigs = [sigrec(name, "equity", 1.0, dv=1e8), sigrec("BBB", "equity", 1.0, dv=5e8)]       # BBB more liquid
        cfg, sig, snap, sleeve = mini(assets, sigs, {"AAA": quote(20.0), "BBB": quote(20.0)}, cash=5000.0,
                                      favorites=favorites, cap={"crypto": 0.60, "equity": 0.20}, slot_frac=0.20)
        p = planner.make_plan(sig, snap, cfg, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve,
                              crosscheck={name: None, "BBB": None})
        assert [x["asset"] for x in p["allocation"]["waiting"]] != [], favorites             # one slot for two
        return p["allocation"]["new"][0]["asset"], {o["asset"]: o["reason"] for o in p["orders"]}
    assert first("AAA", [])[0] == "BBB"
    got, reasons = first("AAA", ["AAA-STOCK"])                      # named AAA (no coin AAA this run)
    assert got == "AAA" and "(#1 by crypto_first; favorite #1)" in reasons["AAA"]
    assert first("AAA", ["AAA"])[0] == "AAA"                        # by name, as before
    assert first("AAA-STOCK", ["AAA-STOCK"])[0] == "AAA-STOCK"      # renamed: by name, as before
    assert first("AAA-STOCK", ["AAA"])[0] == "BBB"                  # the bare name is the coin's, not the stock's
    explicit = {"name": "AAA", "asset": {"name": "AAA", "vehicle": {"type": "equity", "symbol": "AAA"}}}
    coin = {"name": "AAA", "asset": dict(uasset("AAA", "crypto", "coinbase"))}
    assert planner._fav_rank(explicit, {"AAA-STOCK": 1}) is None and planner._fav_rank(coin, {"AAA-STOCK": 1}) is None
    assert planner._fav_rank(dict(explicit, asset=ustock("AAA", "AAA")), {"AAA-STOCK": 2, "AAA": 3}) == 2


# ------------------------------------------------------------------ digest

def test_digest_signal_column_is_neutral():
    base = {"name": "X", "enabled": True, "errors": [], "entry_frac": None, "universe": None}
    assert sg._signal(dict(base, target_frac=0.5, prev_target_frac=1.0)) == "1.00->0.50"
    assert sg._signal(dict(base, target_frac=0.5, prev_target_frac=0.0)) == "new 0.50"
    assert sg._signal(dict(base, target_frac=1.0, prev_target_frac=1.0)) == "-"
    assert sg._signal(dict(base, target_frac=0.0, prev_target_frac=1.0)) == "1.00->0.00"
    assert sg._signal(dict(base, target_frac=1.0, prev_target_frac=0.5, entry_frac=0.5)) == \
        "0.50->1.00 (entry-eligible 0.50)"
    assert sg._signal(dict(base, enabled=False, target_frac=0.5, prev_target_frac=1.0,
                           universe={"outcome": "watch", "reason": "too little history (80 bars): x"})) == \
        "1.00->0.50 (watch: too little history (80 bars))"
    assert sg._signal(dict(base, errors=["x"])) == "ERROR: no trade"
    for t in ("SELL", "BUY", "HOLD", "EXIT"):
        assert t not in sg._signal(dict(base, target_frac=0.0, prev_target_frac=1.0))


def test_skip_feed_leaves_robinhood_assets_out_without_errors(state, monkeypatch, capsys):
    install_yf(monkeypatch)
    raw = stock_cfg(equity={"enabled": False})
    raw["assets"] = [dict(raw["assets"][0], enabled=True),
                     {"name": "AAA", "class": "equity", "enabled": True, "alloc_frac": 0.1, "mode": "split",
                      "signal": {"source": "computed", "feed": "yfinance", "symbol": "AAA"},
                      "vehicle": {"type": "equity", "symbol": "AAA", "fractional": True}}]
    paths()["base"].mkdir(parents=True, exist_ok=True)
    paths()["config"].write_text(json.dumps(raw))
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    assert cli.main(["signals", "--skip-feed", "robinhood"]) == 0
    out = capsys.readouterr()
    assert "SKIPPED feed robinhood (needs Claude's captures; computed in /moneyline): SPY" in out.out
    assert "ALERT" not in out.err
    sig = json.loads((paths()["signals"] / "signals_2026-10-19.json").read_text())
    assert [a["name"] for a in sig["assets"]] == ["AAA"] and sig["skipped_feeds"] == ["robinhood"]
    assert (paths()["digests"] / "digest_2026-10-19_no-robinhood.txt").exists()
    assert cli.main(["signals"]) == 1                                         # SPY has no captures: an error
    assert "ALERT: signal errors for SPY" in capsys.readouterr().err


# ------------------------------------------------------------------ fetch-list

def test_fetch_list_stage1_then_stock_needs(state, monkeypatch, capsys):
    fake = install_yf(monkeypatch)
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: {"equity": set(), "crypto": set()})
    cfg = validate(stock_cfg())
    needs = cli.fetch_needs(cfg, NOW)
    assert needs["stage1"] and not needs["pairs_stage1"] and needs["tradability"] == TICKERS
    calls = cli.fetch_calls(cfg, NOW, needs=needs)
    assert [c["tool"] for c in calls] == ["get_equity_tradability"] * 2 and not fake.calls
    assert [len(c["params"]["symbols"]) for c in calls] == [10, 5] and calls[0]["params"]["account_number"] == ACCT
    write_tradability(paths()["inbox"])
    needs = cli.fetch_needs(cfg, NOW)
    assert not needs["stage1"] and len(fake.calls) == 1
    eligible = ["AAA", "BBB", "EEE", "FFF", "GGG", "KKK", "NNN", "OOO"]
    assert needs["equity_quotes"] == eligible and needs["stocks_scanned"] == 12
    calls = cli.fetch_calls(cfg, NOW, needs=needs)
    tools = [c["tool"] for c in calls]
    assert tools == ["get_accounts", "get_portfolio", "get_equity_orders", "get_equity_positions",
                     "get_equity_tradability", "get_equity_tradability", "get_equity_quotes"]
    assert next(c for c in calls if c["tool"] == "get_equity_quotes")["params"]["symbols"] == eligible
    paths()["config"].write_text(json.dumps(stock_cfg()))
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    capsys.readouterr()
    assert cli.main(["fetch-list"]) == 0
    out = capsys.readouterr().out
    assert "(stock universe: 12 tickers scanned; quotes for 8 held or green and entry-eligible today: AAA" in out
    # feed robinhood: the bars come through Claude, in windows, for every scanned ticker
    raw = stock_cfg(equity={"feed": "robinhood", "symbols": ["AAA", "BBB", "LLL"]})
    calls = cli.fetch_calls(validate(raw), NOW)
    hist = [c["params"] for c in calls if c["tool"] == "get_equity_historicals"]
    assert {h["symbols"][0] for h in hist} == {"AAA", "BBB"} and all(len(h["symbols"]) == 1 for h in hist)
    assert next(c for c in calls if c["tool"] == "get_equity_quotes")["params"]["symbols"] == ["AAA", "BBB"]


def test_stage1_never_repeats_for_a_failing_tradability_call(state, monkeypatch):
    """Regression: while one tradability chunk kept failing, every fetch-list was stage 1 (no account, order or
    position reads), so no plan and no exits for any asset."""
    install_yf(monkeypatch)
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: {"equity": set(), "crypto": set()})
    cfg, inbox = validate(stock_cfg()), paths()["inbox"]
    assert cli.fetch_needs(cfg, NOW)["stage1"]
    write_cap(inbox, "get_equity_tradability", tradability_response(TICKERS[:10]),
              {"account_number": ACCT, "symbols": TICKERS[:10]}, NOW - timedelta(minutes=3))
    write_cap(inbox, "get_equity_tradability", {"isError": True, "content": [{"type": "text", "text": "Error: "
                                                                               "upstream rejected the request"}]},
              {"account_number": ACCT, "symbols": TICKERS[10:]}, NOW - timedelta(minutes=2))
    needs = cli.fetch_needs(cfg, NOW)
    assert not needs["stage1"]
    calls = cli.fetch_calls(cfg, NOW, needs=needs)
    assert [c["tool"] for c in calls][:4] == ["get_accounts", "get_portfolio", "get_equity_orders",
                                              "get_equity_positions"]
    assert any(c["tool"] == "get_equity_tradability" and c["params"]["symbols"] == TICKERS[10:] for c in calls)
    assert by_ticker(needs["stock_report"])["KKK"]["outcome"] == "watch"         # unconfirmed: watch-only meanwhile
    later = NOW + timedelta(hours=stocks.cu.STAGE1_RETRY_HOURS + 1)              # no success since: asked first again
    assert cli.fetch_needs(cfg, later)["stock_stage1"] == TICKERS[10:]
    paths()["hook_log"].write_text(json.dumps({                                   # a failure without a capture
        "ts": (later - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "hook": "post",
        "tool": "mcp__robinhood-trading__get_equity_tradability", "decision": "failure", "reason": "timed out",
        "ref_id": None}) + "\n", encoding="utf-8")
    assert not cli.fetch_needs(cfg, later)["stage1"]
    pairs_cfg = validate(stock_cfg(equity={"enabled": False}, crypto={"enabled": True, "source": "robinhood"}))
    assert universe.stage1_etfs(pairs_cfg, NOW, inbox)                           # no pair list yet: stage 1
    write_cap(inbox, "get_currency_pairs", {"isError": True, "content": [{"type": "text", "text": "Error"}]},
              {"limit": 700}, NOW - timedelta(minutes=1))
    assert universe.stage1_etfs(pairs_cfg, NOW, inbox) is None                   # tried: the normal list asks again


# ------------------------------------------------------------------ init --update

def test_init_update_adds_missing_nested_keys_only(state, monkeypatch, capsys):
    assert cli.main(["init"]) == 0
    old = json.loads(cfgmod.EXAMPLE.read_text())
    old["account"]["account_number"] = ACCT
    del old["allocation"]["favorites"], old["allocation"]["slot_frac"], old["allocation"]["_comment_favorites"]
    del old["universe"]["equity"]
    del old["universe"]["crypto"]["etf_map"]["NEAR"]                   # a deleted mapping is a value: never re-added
    old["universe"]["crypto"]["exclude"] = ["USDC"]                    # lists are never touched
    old["limits"]["max_day_usd"] = 777
    f = paths()["config"]
    f.write_text(json.dumps(old))
    del old["universe"]["crypto"]["enabled"]                         # missing: off; the example's true would turn it on
    f = paths()["config"]
    f.write_text(json.dumps(old))
    kept = []
    merged, added = cli.init_update(f, kept=kept)
    assert added == ["allocation.favorites", "universe.equity"]
    assert kept == ["allocation.slot_frac: stays 0.2 (the example's 0.1 would change it)",
                    "universe.crypto.enabled: stays false (the example's true would change it)"]
    assert "slot_frac" not in merged["allocation"] and "enabled" not in merged["universe"]["crypto"]
    assert merged["universe"]["crypto"]["exclude"] == ["USDC"] and "NEAR" not in merged["universe"]["crypto"]["etf_map"]
    assert merged["limits"]["max_day_usd"] == 777 and merged["allocation"]["_comment_favorites"]
    assert merged["universe"]["equity"] == json.loads(cfgmod.EXAMPLE.read_text())["universe"]["equity"]
    assert cli.effective_changes(old, merged, added) == []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "update")
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    capsys.readouterr()
    assert cli.main(["init", "--update"]) == 0
    out = capsys.readouterr().out
    assert "allocation.favorites: []" in out and "not added: allocation.slot_frac: stays 0.2" in out
    new = json.loads(f.read_text())
    assert new["universe"]["crypto"] == old["universe"]["crypto"] and new["assets"] == old["assets"]
    assert validate(new)["allocation"]["slot_frac"] == 0.20 and not cfgmod.crypto_universe(validate(new))["enabled"]
    assert len(list(f.parent.glob("config.json.bak-*"))) == 1
    assert cli.main(["init", "--update"]) == 0 and "up to date" in capsys.readouterr().out


# ------------------------------------------------------------------ scheduler

@pytest.mark.parametrize("zone,args,want", [
    ("US Central", (1, 5 * 3600, 6 * 3600), "19:15"), ("US Eastern", (1, 4 * 3600, 5 * 3600), "20:15"),
    ("US Pacific", (1, 7 * 3600, 8 * 3600), "17:15"), ("UTC", (0, 0, 0), "00:15")])
def test_job_time_from_the_time_zone(zone, args, want):
    t, why = cal.job_time(*args)
    assert t == want, zone
    assert "after the 00:00 UTC crypto close" in why
    if args[0]:
        assert "00:15 UTC on daylight time" in why and "01:15 UTC on standard time" in why


BASH = None if os.name == "nt" else __import__("shutil").which("bash")


@pytest.mark.skipif(BASH is None, reason="needs bash")
@pytest.mark.parametrize("tz,want", [("CST6CDT,M3.2.0,M11.1.0", "19:15"), ("EST5EDT,M3.2.0,M11.1.0", "20:15"),
                                     ("PST8PDT,M3.2.0,M11.1.0", "17:15"), ("UTC0", "00:15")])
def test_schedule_install_picks_the_time_from_the_pc_time_zone(tmp_path, tz, want):
    e = dict(os.environ, TZ=tz, AGENTIC_PYTHON=sys.executable,
             CLAUDE_CODE_GIT_BASH_PATH="C:\\Program Files\\Git\\bin\\bash.exe")
    r = subprocess.run([BASH, str(WIN / "schedule_crypto_signals.sh"), "install", "--dry-run"], env=e,
                       capture_output=True, text=True, timeout=60, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    first, cmd = r.stdout.splitlines()[0], shlex.split(r.stdout, comments=True)
    assert first.startswith(f"# time {want} chosen from this PC's time zone: {want} local = 00:15 UTC")
    assert cmd[:8] == ["MSYS_NO_PATHCONV=1", "schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", want]
    r = subprocess.run([BASH, str(WIN / "schedule_crypto_signals.sh"), "install", "--dry-run", "--time", "22:40"],
                       env=e, capture_output=True, text=True, timeout=60)
    assert shlex.split(r.stdout, comments=True)[7] == "22:40" and "--time" in r.stdout.splitlines()[0]
    r = subprocess.run([BASH, str(WIN / "schedule_crypto_signals.sh"), "install", "--dry-run"],
                       env=dict(e, AGENTIC_PYTHON=str(tmp_path / "missing")), capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 2 and "pass --time HH:MM" in r.stderr


# ------------------------------------------------------------------ end to end through the real hooks

def e2e_cfg():
    return stock_cfg(crypto={"enabled": True, "source": "list", "symbols": list(COINS), "etf_map": {}},
                     favorites=["OOO", "EEE", "UNI"], sleeve={"DDD": 10})


SPLIT_PC = {"FFF", "DDD"}             # Robinhood's previous_close disagrees with yfinance (a split): buys blocked


def e2e_response(tool, params, w):
    """Synthetic result for one fetch-list / re-fetch call (official output shapes)."""
    from tests.test_agentic_universe import pair_row
    qts = w["quote_time"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    ddd = w["px"]["DDD"]
    cash = 10000.0
    if tool == "get_accounts":
        return env({"accounts": [{"account_number": ACCT, "rhs_account_number": RHS, "agentic_allowed": True}]})
    if tool == "get_portfolio":
        return env({"total_value": f"{cash + 10 * ddd:.2f}", "cash": f"{cash:.2f}",
                    "buying_power": {"buying_power": f"{cash:.2f}", "unleveraged_buying_power": f"{cash:.2f}"},
                    "crypto_buying_power": {"buying_power": f"{cash:.2f}"}})
    if tool == "get_equity_positions":
        return env({"positions": [{"symbol": "DDD", "quantity": "10", "shares_available_for_sells": "10",
                                   "average_buy_price": "90.00", "type": "long"}], "next": ""})
    if tool == "get_crypto_positions":
        return env({"results": [{"currency": {"code": "USD", "type": "fiat"}, "quantity": f"{cash:.2f}"}],
                    "next": ""})
    if tool == "get_equity_orders":
        return env({"orders": [], "next": ""})
    if tool == "get_crypto_orders":
        return env({"rhs_account_number": RHS, "results": [], "next": ""})
    if tool == "get_currency_pairs":
        return env({"results": [pair_row(c) for c in COINS], "next": ""})
    if tool == "get_equity_tradability":
        assert params["account_number"] == ACCT and len(params["symbols"]) <= 10
        return tradability_response(params["symbols"])
    if tool == "get_equity_quotes":
        assert len(params["symbols"]) <= 20
        rows = []
        for s in params["symbols"]:
            px = w["px"][s]
            rows.append({"quote": {"symbol": s, "bid_price": f"{px * 0.999:.4f}", "ask_price": f"{px * 1.001:.4f}",
                                   "last_trade_price": f"{px:.4f}", "venue_bid_time": qts, "venue_ask_time": qts,
                                   "previous_close": f"{px * (2 if s in SPLIT_PC else 1):.4f}",
                                   "adjusted_previous_close": f"{px:.4f}",
                                   "previous_close_date": w["eq_end"].isoformat(), "has_traded": True,
                                   "state": "active"}})
        return env({"results": rows})
    if tool == "get_crypto_quotes":
        rows = []
        for p in params["symbols"]:
            px = w["px"][p]
            rows.append({"symbol": p.replace("-", ""), "id": f"pair-{p[:-4].lower()}", "bid_price": f"{px * 0.999:.8f}",
                         "ask_price": f"{px * 1.001:.8f}", "mark_price": f"{px:.8f}", "updated_at": qts})
        return env({"results": rows})
    raise AssertionError(f"unexpected read {tool}")


def e2e_world(now):
    crypto_end, eq_end = cal.last_closed_crypto_bar(now), cal.last_closed_equity_session(now)
    yf = {t: stock_frame(t, eq_end) for t in STOCKS}
    cb = FakeCoinbase(crypto_end)
    px = {t: float(f.loc[pd.Timestamp(eq_end), "close"]) for t, f in yf.items()}
    px.update({p: float(f.loc[pd.Timestamp(crypto_end), "close"]) for p, f in cb.frames.items()})
    return dict(yf=yf, cb=cb, px=px, eq_end=eq_end, crypto_end=crypto_end, quote_time=now - timedelta(minutes=1))


def test_stocks_and_coins_end_to_end_dry_run_through_the_hooks(state, monkeypatch, capsys):
    now = real_now()
    w = e2e_world(now)
    monkeypatch.setattr(urllib.request, "urlopen", w["cb"])
    yf = install_yf(monkeypatch, w["yf"])
    assert cli.main(["init"]) == 0
    (state / "config.json").write_text(json.dumps(e2e_cfg()))

    def reads(calls):
        for c in calls:
            mcp_call(state, c["tool"], c["params"], e2e_response(c["tool"], c["params"], w))

    capsys.readouterr()
    assert cli.main(["fetch-list", "--json"]) == 0                   # stage 1: the tickers' tradability first
    stage1 = json.loads(capsys.readouterr().out)
    assert [c["tool"] for c in stage1] == ["get_equity_tradability"] * 2 and not yf.calls
    reads(stage1)
    assert cli.main(["fetch-list", "--json"]) == 0
    calls = json.loads(capsys.readouterr().out)
    tools = [c["tool"] for c in calls]
    assert tools[:7] == ["get_accounts", "get_portfolio", "get_equity_orders", "get_crypto_orders",
                         "get_crypto_orders", "get_equity_positions", "get_crypto_positions"]
    assert "get_equity_historicals" not in tools                       # yfinance: no bars through Claude
    assert len(yf.calls) == 1 and len(yf.calls[0][0]) == 13             # one batch (not LLL, MMM)
    eq = next(c for c in calls if c["tool"] == "get_equity_quotes")["params"]["symbols"]
    assert eq == ["AAA", "BBB", "EEE", "FFF", "GGG", "KKK", "NNN", "OOO"]     # DDD is not known as held yet
    cq = next(c for c in calls if c["tool"] == "get_crypto_quotes")["params"]["symbols"]
    assert cq == ["AAVE-USD", "AVAX-USD", "DOGE-USD", "LINK-USD", "UNI-USD"]
    reads(calls)
    n_cb = len(w["cb"].urls)
    assert cli.main(["run"]) == 1                                      # DDD's exit needs a quote: re-fetch
    assert len(yf.calls) == 1 and len(w["cb"].urls) == n_cb             # the caches were current: no download
    out = capsys.readouterr().out
    assert "SCAN 22 assets (0 explicit, 22 universe)" in out and "UNIVERSE stocks (feed yfinance" in out
    assert "UNIVERSE crypto (universe.crypto.symbols): 10 coins considered, 10 scanned" in out
    assert "cross-check vs Robinhood: yfinance close" in out and "  SIGNAL" in out and sg.SIGNAL_NOTE in out
    plan = json.loads((state / "plan_current.json").read_text())
    assert plan["refetch"] == [{"tool": "get_equity_quotes", "params": {"symbols": ["DDD"]},
                                "why": "quotes this plan needs (missing or stale)"}]
    w["quote_time"] = datetime.now(UTC)
    reads(plan["refetch"])
    assert cli.main(["plan"]) == 0
    out = capsys.readouterr().out
    plan = json.loads((state / "plan_current.json").read_text())
    assert plan["errors"] == [] and plan["refetch"] == []
    al = plan["allocation"]
    assert al["held"] == ["DDD"]
    assert [x["asset"] for x in al["new"]] == ["UNI", "DOGE", "AAVE", "LINK", "AVAX", "OOO", "EEE", "AAA", "BBB"]
    assert [x["asset"] for x in al["waiting"]] == ["GGG", "KKK", "NNN"]
    keys = [o["key"] for o in plan["orders"]]
    assert keys[0] == "DDD|DDD|sell|0"                                  # cross-check fails, the exit still goes
    assert not any(k.startswith("FFF|") for k in keys)
    sk = {x["asset"]: x["reason"] for x in plan["skipped"]}
    assert "cross-check failed" in sk["FFF"] and "no free slot" in sk["GGG"]
    assert any(x.startswith("ALERT FFF: cross-check failed") for x in plan["warnings"])
    reasons = {o["asset"]: o["reason"] for o in plan["orders"]}
    assert "favorite #1" in reasons["OOO"] and "favorite #2" in reasons["EEE"] and "favorite #3" in reasons["UNI"]
    stock_buys = [o for o in plan["orders"] if o["tool"] == "place_equity_order" and o["params"]["side"] == "buy"]
    assert {o["params"]["symbol"] for o in stock_buys} == {"OOO", "EEE", "AAA", "BBB"}
    assert all(o["params"]["type"] == "limit" for o in stock_buys)
    for o in plan["orders"]:                                           # every plan order passes the real guard
        assert hook(PRE, state, o["preview_tool"], o["preview_params"]).returncode == 0
        r = hook(PRE, state, o["tool"], o["params"])
        assert r.returncode == 0, r.stderr.decode()
    aaa = next(o for o in stock_buys if o["params"]["symbol"] == "AAA")
    for change in ({"symbol": "FFF"}, {"quantity": str(int(aaa["params"]["quantity"]) + 1)}, {"side": "sell"},
                   {"limit_price": "999.00"}):
        r = hook(PRE, state, aaa["tool"], {**aaa["params"], **change})
        assert r.returncode == 2 and b"BLOCKED" in r.stderr, change
    for o in plan["orders"]:
        assert hook(POST, state, o["tool"], o["params"], env({"order": None})).returncode == 0
    assert not (state / "STOP").exists()
    assert ledger.placed_usd(datetime.now(UTC)) == pytest.approx(sum(o["notional_usd"] for o in plan["orders"]))
    sig = json.loads((state / "signals" / f"signals_{now.date().isoformat()}.json").read_text())
    assert len(sig["universe_equity"]["assets"]) == 12 and len(sig["universe"]["assets"]) == 10
    for f in (state / "journal.jsonl", state / "hook.log"):
        assert ACCT not in f.read_text() and RHS not in f.read_text()


def test_robinhood_feed_windows_through_the_hooks_with_a_too_large_result(state, monkeypatch):
    now = real_now()
    eq_end = cal.last_closed_equity_session(now)
    frames = {t: stock_frame(t, eq_end, forming=False) for t in ("AAA", "BBB", "CCC")}
    raw = stock_cfg(equity={"feed": "robinhood", "symbols": ["AAA", "BBB", "CCC"]})
    paths()["base"].mkdir(parents=True, exist_ok=True)
    paths()["config"].write_text(json.dumps(raw))
    cfg = validate(raw)
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: {"equity": set(), "crypto": set()})
    write_tradability(paths()["inbox"], at=now - timedelta(minutes=5), symbols=["AAA", "BBB", "CCC"])
    calls = [c for c in cli.fetch_calls(cfg, now) if c["tool"] == "get_equity_historicals"]
    per = len(calls) // 3
    assert per >= 4 and all(len(c["params"]["symbols"]) == 1 for c in calls)
    big = [c for c in calls if c["params"]["symbols"] == ["BBB"] and c["params"].get("end_time")][-1]   # recent
    notice = ("Error: MCP tool \"get_equity_historicals\" response (31544 tokens) exceeds maximum allowed tokens "
              "(25000).")
    for c in calls:
        post = mcp_call(state, c["tool"], c["params"], notice if c is big else hist_response(c["params"], frames))
        assert (TOO_LARGE_HELP in post.stderr.decode()) == (c is big)
    again = [c["params"] for c in cli.fetch_calls(cfg, now) if c["tool"] == "get_equity_historicals"]
    # only the window that held no data, in two halves (never the same too-large call again), the first one from 5
    # sessions before it (an overlap with the cached bars: a split since is caught)
    assert len(again) == 2 and all(p["symbols"] == ["BBB"] for p in again)
    b0 = date.fromisoformat(big["params"]["start_time"][:10])
    assert again[0]["start_time"] == f"{cal.trading_days(b0 - timedelta(days=20), b0)[-7].isoformat()}T00:00:00Z"
    assert again[0]["end_time"] == again[1]["start_time"] and again[1]["end_time"] == big["params"]["end_time"]
    a = next(x for x in stocks.build_equity_universe(cfg, now, paths()["inbox"])[0] if x["name"] == "BBB")
    s = sg.asset_signal(a, cfg, now, paths()["inbox"], "")
    assert any(TOO_LARGE_HELP in x for x in s["warnings"]) and any("gap of" in x for x in s["warnings"])
    for p in again:
        mcp_call(state, "get_equity_historicals", p, hist_response(p, frames))
    assert [c for c in cli.fetch_calls(cfg, now) if c["tool"] == "get_equity_historicals"] == []
    s = sg.asset_signal(a, cfg, now, paths()["inbox"], "")
    assert s["errors"] == [] and not any("gap of" in x or "skipped capture" in x for x in s["warnings"])
    assert s["bars"] == len(frames["BBB"][frames["BBB"].index >= pd.Timestamp(now.date() - timedelta(days=700))])
