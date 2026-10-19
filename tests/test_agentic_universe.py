"""Tests for the crypto universe: agentic/universe.py, the Coinbase cache in agentic/data.py, and how signals, the
digest, fetch-list, the planner, init --update and doctor handle ~30+ generated coins. Plus an end-to-end offline dry
run of a synthetic 41-coin universe through the real hooks. All coins, prices, volumes and account numbers are
synthetic; no network (urllib is mocked); state only under tmp_path."""
import copy
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import calendar as cal  # noqa: E402
from agentic import cli, doctor, ledger, planner, universe  # noqa: E402
from agentic import config as cfgmod  # noqa: E402
from agentic import data as feeds  # noqa: E402
from agentic import signals as sg  # noqa: E402
from agentic.config import ConfigError, paths, validate  # noqa: E402
from tests.test_agentic_e2e import PRE, POST, hook, mcp_call, real_now, trend  # noqa: E402
from tests.test_agentic_snapshot import write_cap  # noqa: E402

UTC = timezone.utc
ACCT, RHS = "UNIACCT0K3", "927700451"          # synthetic account numbers
NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)          # Monday 11:00 ET: crypto bar 2026-10-18
EPOCH = pd.Timestamp("1970-01-01")


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(d))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(feeds, "PACER", feeds.Pacer(clock=lambda: 0.0, sleep=lambda s: None))
    return d


# ------------------------------------------------------------------ the synthetic world

ETF_PX = {"IBIT": 19.5, "ETHA": 14.2, "BSOL": 11.0, "XRPC": 8.0, "LTCC": 9.8, "NRR": 7.5}   # whole shares fit a slot
# coin: (pattern, last close, median daily dollar volume, bars). fresh = green again ~12 bars ago (entry-eligible),
# old = green all along (too late to join), red = downtrend.
COINS = {
    "BTC": ("fresh", 60000.0, 9e8), "ETH": ("fresh", 2500.0, 5e8), "SOL": ("old", 150.0, 3e8),
    "XRP": ("fresh", 0.6, 2e8), "LTC": ("red", 80.0, 6e7), "NEAR": ("fresh", 5.0, 5e7),
    "DOGE": ("fresh", 0.12, 1.5e8), "ADA": ("old", 0.4, 9e7), "AVAX": ("fresh", 30.0, 8e7), "LINK": ("red", 14.0, 7e7),
    "DOT": ("red", 6.0, 4e7), "BCH": ("old", 400.0, 4.5e7), "UNI": ("fresh", 8.0, 3.5e7), "AAVE": ("red", 150.0, 3e7),
    "XLM": ("old", 0.1, 2.5e7), "SHIB": ("red", 0.00002, 2.4e7), "ETC": ("red", 20.0, 2.2e7),
    "HBAR": ("fresh", 0.07, 2e7), "ARB": ("red", 0.8, 1.8e7), "OP": ("red", 1.6, 1.6e7), "SUI": ("old", 1.2, 1.5e7),
    "APT": ("red", 7.0, 1.4e7), "ATOM": ("red", 7.0, 1.3e7), "ALGO": ("red", 0.15, 1.2e7), "FIL": ("red", 4.0, 1.1e7),
    "COMP": ("red", 50.0, 1e7), "CRV": ("red", 0.5, 9e6), "MKR": ("red", 1500.0, 8e6), "GRT": ("red", 0.15, 7e6),
    "SNX": ("red", 2.0, 6e6), "ICP": ("red", 8.0, 5.6e6), "INJ": ("red", 20.0, 5.3e6),   # ranks 31-32
    "BONK": ("fresh", 0.00002, 1e6), "ZRX": ("red", 0.3, 2e6),                             # illiquid
    "WIF": ("fresh", 2.0, 2e7, 200),                                                        # too little history
    "USDC": ("red", 1.0, 5e8), "USDT": ("red", 1.0, 5e8), "PYUSD": ("red", 1.0, 1e7), "WBTC": ("fresh", 60000.0, 1e8),
    "HYPE": ("fresh", 30.0, 1e8),                                                           # no Coinbase pair
    "XTZ": ("red", 0.7, 1e7),                                                               # sell_only on Robinhood
}
NOT_ON_COINBASE = {"HYPE"}
RH_SELL_ONLY = {"XTZ"}
ETF_UNTRADABLE = {"XRPC"}
HELD = {"DOGE": "1500", "LINK": "12"}         # the sleeve's direct holdings (sleeve_initial_qty)


def frame(code, last: date, forming=True):
    """Daily bars with volume ending on `last` (plus the forming bar, as Coinbase returns it)."""
    pattern, px, dv, *n = COINS[code]
    n = n[0] if n else 800
    days = pd.date_range(end=pd.Timestamp(last) + pd.Timedelta(days=1 if forming else 0), periods=n, freq="D")
    if pattern == "red":
        f = trend(days, px, drift=-0.003)
    else:
        f = trend(days, px, dip=20 if pattern == "fresh" else None)
    f["volume"] = dv / f["close"]
    return f


class FakeCoinbase:
    """GET /products and /products/{p}/candles (<= 300 rows of [time, low, high, open, close, volume], newest first,
    including the forming bar)."""

    def __init__(self, last: date, codes=None):
        self.last = last
        self.frames = {f"{c}-USD": frame(c, last) for c in (codes or COINS) if c not in NOT_ON_COINBASE}
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
        assert (e - s).days + 1 <= 300
        f = self.frames[product]
        f = f[(f.index >= s) & (f.index <= e)]
        rows = [[int((d - EPOCH).total_seconds()), r.low, r.high, r.open, r.close, r.volume]
                for d, r in f.iloc[::-1].iterrows()]
        return io.BytesIO(json.dumps(rows).encode())

    def candle_calls(self, product=None):
        return [x for x in self.urls if "/candles" in x and (product is None or f"/{product}/" in x)]


def env(data):
    return {"data": data, "guide": "synthetic guide text"}


def pair_row(code, tradability="tradable"):
    return {"id": f"pair-{code.lower()}", "symbol": f"{code}-USD", "display_symbol": "", "name": code.title(),
            "asset_currency": {"id": f"cur-{code.lower()}", "code": code, "name": code.title(),
                               "type": "cryptocurrency"},
            "quote_currency": {"id": "cur-usd", "code": "USD", "name": "U.S. Dollar", "type": "fiat"},
            "tradability": tradability, "tradability_by_account_type": {}, "display_only": False,
            "min_order_size": "0.01", "max_order_size": "100000000", "min_order_quantity_increment": "0.01",
            "min_order_price_increment": "0.000001", "min_order_quote_amount": "1.00", "market_orders_only": False,
            "type": "cryptocurrency", "halted": False}


def pairs_response(codes=None, next_=""):
    rows = [pair_row(c, "sell_only" if c in RH_SELL_ONLY else "tradable") for c in (codes or COINS)]
    rows.append({**pair_row("BTC"), "symbol": "BTC-EUR", "id": "pair-btc-eur",
                 "quote_currency": {"id": "cur-eur", "code": "EUR", "name": "Euro", "type": "fiat"}})
    return env({"results": rows, "next": next_})


def tradability_response(symbols):
    res, nf = [], []
    for s in symbols:
        if s not in ETF_PX:
            nf.append(s)
            continue
        ok = s not in ETF_UNTRADABLE
        res.append({"symbol": s, "name": f"{s} Trust", "state": "active", "tradeable": ok,
                    "fractional_tradability": "tradable" if ok else "untradable",
                    "extended_hours_fractional_tradability": False,
                    "account_type_tradabilities": [{"account_type": "individual",
                                                    "account_type_tradability": "tradable" if ok else "untradable"}]})
    return env({"results": res, "not_found": nf})


def uni_cfg(**over):
    """A slots config whose only assets are a disabled stock: every coin comes from the universe."""
    u = {"enabled": True, **over.pop("universe", {})}
    raw = {"account": {"account_number": ACCT, "rhs_account_number": RHS, "approvals_required": True},
           "live": over.pop("live", True), "capital": {"max_usd": 2000},
           "limits": {"max_order_usd": 500, "max_day_usd": 1500, "max_asset_frac": 0.30, "min_order_usd": 5},
           "allocation": {"method": "slots", "slot_frac": 0.10, "priority": "crypto_first",
                          "class_max_frac": {"crypto": 0.60, "equity": 1.0}},
           "sleeve_initial_qty": dict(HELD),
           "universe": {"crypto": u},
           "assets": over.pop("assets", [
               {"name": "SPY", "class": "equity", "enabled": False, "alloc_frac": 0.2, "mode": "split",
                "signal": {"source": "computed", "feed": "robinhood", "symbol": "SPY"},
                "vehicle": {"type": "equity", "symbol": "SPY", "fractional": True}}])}
    raw.update(over)
    return raw


def explicit(name, vtype="equity", vsym=None, enabled=True, signal=None):
    return {"name": name, "class": "crypto", "enabled": enabled, "alloc_frac": 0.2, "mode": "split",
            "signal": {"source": "computed", "feed": "coinbase", "symbol": signal or f"{name}-USD"},
            "vehicle": {"type": vtype, "symbol": vsym or name, "fractional": vtype == "equity"}}


def fake_fetch(last=date(2026, 10, 18), calls=None):
    def fetch(product, start, now):
        if calls is not None:
            calls.append(product)
        code = product[:-4]
        if code in NOT_ON_COINBASE or code not in COINS:
            raise urllib.error.HTTPError("x", 404, "NotFound", {}, None)
        f = frame(code, last, forming=False)
        return f[f.index >= pd.Timestamp(start)]
    return fetch


def fake_products(now=None):
    return {"products": {f"{c}-USD": {"base": c, "quote": "USD", "online": True}
                         for c in COINS if c not in NOT_ON_COINBASE}, "fetched_at": "2026-10-19T00:05:00Z",
            "error": None}


def write_universe_inbox(inbox, at=None, trad=True, pairs_how="raw", account=ACCT):
    write_cap(inbox, "get_currency_pairs", pairs_response(), {"limit": 700}, at or NOW - timedelta(hours=1),
              pairs_how)
    if trad:
        write_cap(inbox, "get_equity_tradability", tradability_response(sorted(ETF_PX)),
                  {"account_number": account, "symbols": sorted(ETF_PX)}, at or NOW - timedelta(hours=1))


def build(raw=None, inbox=None, held=None, **kw):
    cfg = validate(raw or uni_cfg())
    inbox = inbox if inbox is not None else paths()["inbox"]
    return universe.build_universe(cfg, NOW, inbox, fetch=kw.pop("fetch", fake_fetch()),
                                   products=kw.pop("products", fake_products),
                                   held=held or {"equity": set(), "crypto": set()}, **kw)


def by_coin(report):
    return {c["coin"]: c for c in report["coins"]}


# ------------------------------------------------------------------ config

def test_config_universe_defaults_and_validation():
    c = validate({"capital": {"max_usd": 100}, "assets": []})
    u = c["universe"]["crypto"]
    assert u["enabled"] is False and u["source"] == "robinhood" and u["max_assets"] == 30
    assert u["min_dollar_volume_usd"] == 5e6 and u["min_history_bars"] == 300 and u["mode"] == "split"
    assert u["etf_map"] == {"BTC": "IBIT", "ETH": "ETHA", "SOL": "BSOL", "XRP": "XRPC", "LTC": "LTCC", "NEAR": "NRR"}
    assert {"USDC", "USDT", "WBTC", "PAXG"} <= set(u["exclude"]) and u["prefer_etf"] and u["direct_crypto"]
    assert validate(c)["universe"] == c["universe"]                                   # idempotent
    ex = validate(json.loads(cfgmod.EXAMPLE.read_text()))
    assert ex["universe"]["crypto"]["enabled"] is True
    assert {a["name"]: a["vehicle"]["symbol"] for a in ex["assets"]}["BTC"] == "IBIT"
    assert {a["name"]: a["vehicle"]["symbol"] for a in ex["assets"]}["SOL"] == "BSOL"
    got = validate(uni_cfg(universe={"symbols": ["doge", "DOGE"], "etf_map": {"BTC": "IBIT", "ETH": None},
                                     "min_history_bars": 400, "entry": {"max_join_bars": 10}}))["universe"]["crypto"]
    assert got["symbols"] == ["DOGE"] and got["etf_map"] == {"BTC": "IBIT"} and got["min_history_bars"] == 400
    assert got["entry"] == {"max_join_bars": 10}


@pytest.mark.parametrize("u, msg", [
    ({"source": "binance"}, "source"), ({"enabled": "true"}, "enabled"), ({"max_assets": 0}, "max_assets"),
    ({"min_history_bars": 10}, "min_history_bars"), ({"etf_map": {"BTC": "IBIT", "ETH": "IBIT"}}, "more than one"),
    ({"exclude": "USDT"}, "exclude"), ({"surprise": 1}, "unknown keys"), ({"mode": "fast"}, "mode"),
    ({"min_dollar_volume_usd": -1}, "min_dollar_volume_usd"), ({"symbols": ["BTC-USD"]}, "not a coin code")])
def test_config_universe_rejects(u, msg):
    with pytest.raises(ConfigError, match=msg):
        validate(uni_cfg(universe=u))
    with pytest.raises(ConfigError, match="only"):
        validate({**uni_cfg(), "universe": {"stocks": {}}})


# ------------------------------------------------------------------ captures

@pytest.mark.parametrize("how", ["raw", "text", "structured", "list"])
def test_pairs_capture_wrappers_and_pagination(state, how):
    inbox = state / "inbox"
    first = env({"results": [pair_row("BTC"), pair_row("ETH")], "next": "cur-2"})
    write_cap(inbox, "get_currency_pairs", first, {"limit": 700}, NOW - timedelta(minutes=10), how)
    pc = universe.pairs_capture(inbox, NOW)
    assert set(pc["pairs"]) == {"BTC", "ETH"} and pc["complete"] is False and pc["pages"] == 1
    write_cap(inbox, "get_currency_pairs", env({"results": [pair_row("SOL"), pair_row("XTZ", "sell_only")],
                                                "next": ""}), {"limit": 700, "cursor": "cur-2"},
              NOW - timedelta(minutes=9), how)
    pc = universe.pairs_capture(inbox, NOW)
    assert set(pc["pairs"]) == {"BTC", "ETH", "SOL", "XTZ"} and pc["complete"] and pc["pages"] == 2
    assert pc["pairs"]["SOL"]["tradable"] and not pc["pairs"]["XTZ"]["tradable"]
    assert pc["age_days"] == pytest.approx(10 / 1440, abs=1e-3)


def test_parse_pairs_skips_non_usd_and_display_only():
    rows = pairs_response(["BTC", "ETH"])["data"]["results"] + [dict(pair_row("SOL"), display_only=True)]
    got = universe.parse_pairs(rows)
    assert set(got) == {"BTC", "ETH", "SOL"} and got["BTC"]["symbol"] == "BTC-USD"   # BTC-EUR dropped
    assert not got["SOL"]["tradable"]


def test_etf_tradability_account_age_and_shapes(state):
    inbox = state / "inbox"
    cfg = validate(uni_cfg())
    write_cap(inbox, "get_equity_tradability", tradability_response(["IBIT", "XRPC", "NOPE"]),
              {"account_number": ACCT, "symbols": ["IBIT", "XRPC", "NOPE"]}, NOW - timedelta(hours=2))
    write_cap(inbox, "get_equity_tradability", tradability_response(["ETHA"]),
              {"account_number": "OTHERACCT7", "symbols": ["ETHA"]}, NOW - timedelta(hours=1))
    write_cap(inbox, "get_equity_tradability", tradability_response(["BSOL"]),
              {"account_number": ACCT, "symbols": ["BSOL"]}, NOW - timedelta(days=9))
    tr, warns = universe.etf_tradability(inbox, cfg, NOW)
    assert tr["IBIT"]["ok"] and tr["IBIT"]["fractional"]
    assert not tr["XRPC"]["ok"] and "tradeable" in tr["XRPC"]["why"]
    assert not tr["NOPE"]["ok"] and "not found" in tr["NOPE"]["why"]
    assert "ETHA" not in tr and "BSOL" not in tr                     # other account; older than 7 days
    assert any("not for the configured account" in w for w in warns) and ACCT not in " ".join(warns)
    assert universe._tradability_problem({"tradeable": True, "state": "inactive"}).startswith("state")
    assert "halted" in universe._tradability_problem({"tradeable": True, "state": "active",
                                                      "internal_halt_sessions": ["regular_hours"]})


# ------------------------------------------------------------------ the builder

def test_build_universe_outcomes_filters_and_ranking(state):
    write_universe_inbox(state / "inbox")
    assets, rep = build()
    c = by_coin(rep)
    assert len(rep["coins"]) == len(COINS)                          # every coin considered has an outcome
    assert {k for k, v in c.items() if v["outcome"] == "etf"} == {"BTC", "ETH", "SOL", "LTC", "NEAR"}
    assert c["NEAR"]["vehicle"] == {"type": "equity", "symbol": "NRR", "fractional": True}
    assert c["XRP"]["outcome"] == "watch" and "ETF XRPC not confirmed tradable" in c["XRP"]["reason"]
    assert "never switched to direct crypto" in c["XRP"]["reason"]
    assert c["DOGE"]["outcome"] == "direct" and c["DOGE"]["vehicle"] == {"type": "crypto", "symbol": "DOGE"}
    for code, cat in (("USDC", "stablecoin/wrapped"), ("WBTC", "stablecoin/wrapped"), ("HYPE", "no Coinbase pair"),
                      ("WIF", "too little history"), ("BONK", "illiquid"), ("ZRX", "illiquid"),
                      ("ICP", "beyond max_assets"), ("INJ", "beyond max_assets"),
                      ("XTZ", "not tradable on Robinhood")):
        assert c[code]["outcome"] == "excluded" and c[code]["category"] == cat, code
    assert "rank 31 of 32" in c["ICP"]["reason"] and "200 bars, need 300" in c["WIF"]["reason"]
    assert [a["name"] for a in assets][:4] == ["BTC", "ETH", "SOL", "XRP"]           # most liquid first
    assert len(assets) == 30 and sum(a["enabled"] for a in assets) == 29              # XRP: watch only
    dvs = [a["universe"]["dollar_volume_usd"] for a in assets]
    assert dvs == sorted(dvs, reverse=True)
    a = next(a for a in assets if a["name"] == "AVAX")
    assert a["signal"] == {"source": "computed", "feed": "coinbase", "symbol": "AVAX-USD"}
    assert a["class"] == "crypto" and a["mode"] == "split" and a["alloc_frac"] == 0.0 and a["min_bars"] == 300
    validate(uni_cfg(assets=assets))                                               # valid config assets
    assert rep["counts"]["etf"] == 5 and rep["counts"]["excluded: illiquid"] == 2
    lines = universe.summary_lines(rep)
    assert "41 coins considered, 30 scanned (5 via ETF, 24 direct, 1 watch-only)" in lines[0]
    assert "excluded: 4 stablecoin/wrapped, 1 not tradable on Robinhood, 1 no Coinbase pair" in lines[0]
    assert any("0.95% per side" in x for x in lines) and any(x.strip().startswith("XRP:") for x in lines)
    assert len(universe.summary_lines(rep, full=True)) > len(COINS)


def test_build_universe_etf_missing_capture_and_fractional(state):
    write_universe_inbox(state / "inbox", trad=False)
    assets, rep = build()
    c = by_coin(rep)
    for code in ("BTC", "ETH", "SOL", "LTC", "NEAR", "XRP"):
        assert c[code]["outcome"] == "watch" and "no get_equity_tradability capture" in c[code]["reason"], code
    assert not any(a["enabled"] and a["vehicle"]["type"] == "crypto" and a["name"] in universe.crypto_universe(
        validate(uni_cfg()))["etf_map"] for a in assets)                         # never switched to direct
    resp = tradability_response(["IBIT"])
    resp["data"]["results"][0]["fractional_tradability"] = "untradable"
    write_cap(state / "inbox", "get_equity_tradability", resp, {"account_number": ACCT, "symbols": ["IBIT"]},
              NOW - timedelta(minutes=5))
    c = by_coin(build()[1])
    assert c["BTC"]["outcome"] == "etf" and c["BTC"]["vehicle"]["fractional"] is False
    assert "whole shares only" in c["BTC"]["reason"]


def test_build_universe_explicit_precedence_and_blacklist(state):
    write_universe_inbox(state / "inbox")
    raw = uni_cfg(assets=[explicit("ETH", "equity", "ETHA"),                   # same name, enabled
                          explicit("BTC", "equity", "IBIT", enabled=False),    # disabled: keeps BTC out
                          explicit("SOLX", "crypto", "SOL", signal="SOL-USD"),  # trades the coin itself
                          explicit("NRRWATCH", "equity", "NRR", enabled=False, signal="NEAR-USD"),  # disabled twin
                          explicit("AVAXT", "equity", "AVAXT", signal="AVAX-USD")])   # on its Coinbase signal
    assets, rep = build(raw)
    c = by_coin(rep)
    assert c["ETH"]["outcome"] == "explicit" and "ETH (enabled)" in c["ETH"]["reason"]
    assert c["BTC"]["outcome"] == "explicit" and "(disabled)" in c["BTC"]["reason"]
    assert c["SOL"]["outcome"] == "explicit" and "SOLX trades it" in c["SOL"]["reason"]
    assert c["AVAX"]["outcome"] == "explicit"
    assert c["NEAR"]["outcome"] == "etf"                                     # a disabled same-vehicle twin: no
    names = {a["name"] for a in assets}
    assert not names & {"ETH", "BTC", "SOL", "AVAX"}
    cfg = validate(raw)
    eff, warns = universe.with_universe(cfg, {"universe": {"assets": assets}})
    assert warns == [] and len(eff["assets"]) == len(cfg["assets"]) + len(assets)
    planner.make_plan({"date": "2026-10-19", "assets": []}, {"total_value": 0.0, "errors": ["x"]}, eff, NOW, 1, {},
                      placed_today_usd=0.0, journal=[])                      # no duplicate-vehicle error raised


def test_two_explicit_assets_on_one_vehicle_still_an_error(state):
    write_universe_inbox(state / "inbox")
    raw = uni_cfg(assets=[explicit("ETH", "equity", "ETHA"), explicit("ETH2", "equity", "ETHA", signal="ETH-USD")])
    assets, rep = build(raw)
    eff, _ = universe.with_universe(validate(raw), {"universe": {"assets": assets}})
    s = {"date": "2026-10-19", "assets": [{"name": n, "target_frac": 0.0, "bar_date": "2026-10-18", "errors": [],
                                           "tranches": []} for n in ("ETH", "ETH2")]}
    snap = {"total_value": 1000.0, "cash": 1000.0, "buying_power": 1000.0, "quotes": {}, "errors": [], "warnings": [],
            "equity_positions": {}, "crypto_positions": {}, "open_orders": [], "orders": [], "pairs": {}}
    p = planner.make_plan(s, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[],
                          sleeve={"baseline": True, "sleeve": {"equity": {}, "crypto": {}}, "mismatches": []})
    assert any("trade the same vehicle ETHA" in e for e in p["errors"])
    assert not any("ETHA" in str(a["vehicle"]) for a in assets)              # the universe adds no third


def test_build_universe_without_pairs_capture_and_list_source(state):
    _, rep = build(uni_cfg(universe={"symbols": ["DOGE", "AVAX"]}))
    assert {c["coin"] for c in rep["coins"]} == {"DOGE", "AVAX"}
    assert any("no get_currency_pairs capture" in w for w in rep["warnings"])
    write_universe_inbox(state / "inbox")
    assets, rep = build(uni_cfg(universe={"source": "list", "symbols": ["DOGE", "XTZ", "SOL"]}))
    c = by_coin(rep)
    assert set(c) == {"DOGE", "XTZ", "SOL"} and c["SOL"]["outcome"] == "etf"
    assert c["XTZ"]["outcome"] == "watch" and "no tradable Robinhood pair" in c["XTZ"]["reason"]
    _, rep = build(uni_cfg(universe={"symbols": ["XTZ"]}))                  # listed on purpose: watched
    assert by_coin(rep)["XTZ"]["outcome"] == "watch"
    _, rep = build(uni_cfg(universe={"source": "list", "symbols": ["DOGE"], "direct_crypto": False}))
    assert by_coin(rep)["DOGE"]["outcome"] == "watch" and "direct_crypto is false" in by_coin(rep)["DOGE"]["reason"]
    _, rep = build(uni_cfg(universe={"source": "list", "symbols": ["BTC"], "prefer_etf": False}))
    assert by_coin(rep)["BTC"]["outcome"] == "direct"


def test_build_universe_keeps_held_coins_hold_only(state):
    write_universe_inbox(state / "inbox")
    held = {"crypto": {"BONK", "SOL"}, "equity": set()}
    assets, rep = build(held=held)
    c = by_coin(rep)
    assert c["BONK"]["outcome"] == "direct" and "illiquid" in c["BONK"]["hold_only"]
    assert c["SOL"]["outcome"] == "direct" and "BSOL is preferred" in c["SOL"]["hold_only"]
    sol = next(a for a in assets if a["name"] == "SOL")
    assert sol["vehicle"]["type"] == "crypto" and sol["universe"]["hold_only"]
    assets, rep = build(uni_cfg(universe={"exclude": ["USDT", "LTC"]}), held={"crypto": set(), "equity": {"LTCC"}})
    c = by_coin(rep)
    assert c["LTC"]["outcome"] == "etf" and "held, so kept" in c["LTC"]["hold_only"]
    assert c["USDC"]["outcome"] == "direct"                                 # not excluded any more: user's list


def test_build_universe_data_errors_and_stale_bars(state):
    write_universe_inbox(state / "inbox")
    base = fake_fetch()

    def fetch(product, start, now):
        if product == "ADA-USD":
            raise urllib.error.URLError("reset")
        if product == "DOT-USD":
            return base(product, start, now).iloc[:-3]
        return base(product, start, now)
    _, rep = build(fetch=fetch, products=lambda now: {"products": None, "fetched_at": None, "error": "down"})
    c = by_coin(rep)
    assert c["ADA"]["category"] == "Coinbase data error" and c["DOT"]["category"] == "stale Coinbase data"
    assert c["HYPE"]["category"] == "no Coinbase pair"                     # the candle 404, products unknown
    assert any("availability not checked" in w for w in rep["warnings"])


def test_with_universe_rechecks_stored_assets(state):
    write_universe_inbox(state / "inbox")
    cfg = validate(uni_cfg())
    assets, _ = build()
    bad = copy.deepcopy(assets)
    bad[0]["vehicle"] = {"type": "equity", "symbol": "QQQ"}
    bad[1]["signal"]["symbol"] = "BTC-USD"
    bad.append(dict(copy.deepcopy(assets[2]), name="SPY"))
    eff, warns = universe.with_universe(cfg, {"universe": {"assets": bad}})
    assert len(warns) == 3 and all("ignored; re-run signals" in w for w in warns)
    assert {a["name"] for a in eff["assets"]} == {"SPY"} | {a["name"] for a in assets[2:]}
    off = validate(uni_cfg(universe={"enabled": False}))
    eff, warns = universe.with_universe(off, {"universe": {"assets": assets}})
    assert eff["assets"] == off["assets"] and len(warns) == 1 and "universe.crypto is off" in warns[0]
    kept = copy.deepcopy(assets[:2])
    kept[0]["universe"]["hold_only"] = "universe.crypto is off: held, so kept for exits only"
    eff, warns = universe.with_universe(off, {"universe": {"assets": kept}})
    assert [a["name"] for a in eff["assets"][1:]] == [kept[0]["name"]] and "1 universe assets" in warns[0]
    nodirect = validate(uni_cfg(universe={"direct_crypto": False}))
    eff, warns = universe.with_universe(nodirect, {"universe": {"assets": assets}})
    assert not any(a["vehicle"]["type"] == "crypto" for a in eff["assets"]) and warns


# ------------------------------------------------------------------ Coinbase cache

class CandleServer:
    """Candles for one product from `first_day`, recording each request's [start, end]."""

    def __init__(self, first_day="2023-01-01"):
        self.first = pd.Timestamp(first_day)
        self.ranges = []

    def __call__(self, req, timeout=None):
        q = parse_qs(urlparse(req.full_url).query)
        s, e = (pd.Timestamp(q[k][0]).tz_convert(None) for k in ("start", "end"))
        self.ranges.append((s.date(), e.date()))
        days = pd.date_range(max(s, self.first), e, freq="D")
        rows = [[int((d - EPOCH).total_seconds()), 9.0, 11.0, 10.0, 10.0 + (d - EPOCH).days % 7, 100.0]
                for d in reversed(days)]
        return io.BytesIO(json.dumps(rows).encode())


def test_coinbase_cache_incremental_and_paced(state):
    srv, waits, clock = CandleServer(), [], [0.0]

    def sleep(s):
        waits.append(s)
        clock[0] += s
    pacer = feeds.Pacer(rate=5, clock=lambda: clock[0], sleep=sleep)
    t1 = datetime(2026, 10, 18, 1, 0, tzinfo=UTC)
    df = feeds.coinbase_daily_cached("ETH-USD", "2025-01-01", t1, srv, pace=pacer)
    assert df.index[-1] == pd.Timestamp("2026-10-17") and df.index[0] == pd.Timestamp("2025-01-01")
    assert len(srv.ranges) == 3 and waits == [pytest.approx(0.2)] * 2              # <= 5 requests a second
    f = feeds.coinbase_cache_dir() / "ETH-USD.csv"
    cached = feeds.read_coinbase_cache(f)
    assert cached.index[-1] == pd.Timestamp("2026-10-17") and list(cached.columns)[-1] == "volume"
    srv.ranges.clear()
    again = feeds.coinbase_daily_cached("ETH-USD", "2025-01-01", t1 + timedelta(hours=5), srv, pace=pacer)
    assert srv.ranges == [] and again.equals(df)                                    # last closed bar cached
    t2 = datetime(2026, 10, 21, 2, 0, tzinfo=UTC)
    df2 = feeds.coinbase_daily_cached("ETH-USD", "2025-01-03", t2, srv, pace=pacer)
    assert srv.ranges == [(date(2026, 10, 18), date(2026, 10, 21))]     # only bars after the cache (+ forming)
    assert df2.index[0] == pd.Timestamp("2025-01-03") and df2.index[-1] == pd.Timestamp("2026-10-20")
    assert feeds.missing_days(df2.index) == 0
    srv.ranges.clear()
    feeds.coinbase_daily_cached("ETH-USD", "2024-12-01", t2, srv, pace=pacer)       # older history wanted
    assert srv.ranges == [(date(2024, 12, 1), date(2024, 12, 31))]


def test_coinbase_cache_corrupt_gap_and_unsettled(state):
    srv = CandleServer(first_day="2026-01-01")
    pace = feeds.Pacer(clock=lambda: 0.0, sleep=lambda s: None)
    f = feeds.coinbase_cache_dir() / "SOL-USD.csv"
    f.parent.mkdir(parents=True)
    f.write_text("date,open,high,low,close,volume\n2026-01-01,1,2,0.5,nan,3\n")
    issues = []
    t = datetime(2026, 10, 18, 0, 2, tzinfo=UTC)                                    # 2 min after the close
    df = feeds.coinbase_daily_cached("SOL-USD", "2025-06-01", t, srv, pace=pace, issues=issues)
    assert any("corrupt" in x for x in issues) and df.index[-1] == pd.Timestamp("2026-10-17")
    assert feeds.read_coinbase_cache(f).index[-1] == pd.Timestamp("2026-10-16")    # 10-17 not settled yet
    srv.ranges.clear()
    feeds.coinbase_daily_cached("SOL-USD", "2025-06-01", t + timedelta(minutes=10), srv, pace=pace)
    assert srv.ranges == [(date(2026, 10, 17), date(2026, 10, 18))]
    assert feeds.read_coinbase_cache(f).index[-1] == pd.Timestamp("2026-10-17")
    assert not srv.ranges[0][0] < date(2026, 1, 1)                                 # listing date remembered
    gappy = feeds.read_coinbase_cache(f).drop(pd.Timestamp("2026-05-05"))
    f.write_text(gappy.to_csv(index_label="date", date_format="%Y-%m-%d"))
    srv.ranges.clear()
    issues = []
    t3 = datetime(2026, 10, 19, 1, 0, tzinfo=UTC)
    feeds.coinbase_daily_cached("SOL-USD", "2025-06-01", t3, srv, pace=pace, issues=issues)
    assert any("missing days" in x for x in issues) and len(srv.ranges) == 2        # full refetch
    assert feeds.missing_days(feeds.read_coinbase_cache(f).index) == 0


def test_coinbase_products_cached_daily_with_fallback(state):
    calls = []

    def opener(req, timeout=None):
        calls.append(req.full_url)
        return io.BytesIO(json.dumps([{"id": "BTC-USD", "base_currency": "BTC", "quote_currency": "USD",
                                       "status": "online", "trading_disabled": False},
                                      {"id": "OLD-USD", "status": "delisted"}]).encode())
    pace = feeds.Pacer(clock=lambda: 0.0, sleep=lambda s: None)
    p = feeds.coinbase_products(NOW, opener, pace=pace)
    assert p["products"]["BTC-USD"]["online"] and not p["products"]["OLD-USD"]["online"] and p["error"] is None
    assert feeds.coinbase_products(NOW + timedelta(hours=3), opener, pace=pace)["products"] == p["products"]
    assert len(calls) == 1                                                         # once per UTC day

    def down(req, timeout=None):
        raise urllib.error.URLError("down")
    q = feeds.coinbase_products(NOW + timedelta(days=1), down, pace=pace, sleep=lambda s: None)
    assert q["products"] == p["products"] and "down" in q["error"]
    (feeds.coinbase_cache_dir() / "products.json").unlink()
    assert feeds.coinbase_products(NOW, down, pace=pace, sleep=lambda s: None)["products"] is None


def test_get_bars_coinbase_uses_the_cache(state, monkeypatch):
    fake = FakeCoinbase(date(2026, 10, 18), codes=["AVAX"])
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    a = {"name": "AVAX", "class": "crypto", "signal": {"source": "computed", "feed": "coinbase", "symbol": "AVAX-USD"},
         "vehicle": {"type": "crypto", "symbol": "AVAX"}}
    df = feeds.get_bars(a, {"limits": {"min_bars": 300}}, NOW)
    n = len(fake.candle_calls())
    assert df.index[-1] == pd.Timestamp("2026-10-18") and n == 3
    assert feeds.get_bars(a, {"limits": {"min_bars": 300}}, NOW + timedelta(hours=1)).equals(df)
    assert len(fake.candle_calls()) == n                                            # second run: no request


# ------------------------------------------------------------------ signals and digest

def universe_signals(state, monkeypatch, raw=None, held=None):
    write_universe_inbox(state / "inbox")
    cfg = validate(raw or uni_cfg())
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: held or {"equity": set(), "crypto": set()})

    def b(cfg_, now, inbox):
        return universe.build_universe(cfg_, now, inbox, fetch=fake_fetch(), products=fake_products,
                                       held=held or {"equity": set(), "crypto": set()})
    monkeypatch.setattr(feeds, "get_bars", lambda a, c, now=None, inbox=None: fake_fetch()(
        a["signal"]["symbol"], "2024-01-01", now))
    return cfg, sg.compute_signals(cfg, NOW, state / "inbox", build=b)


def test_signals_cover_the_universe_and_digest_stays_compact(state, monkeypatch):
    held = {"crypto": {"DOGE", "LINK"}, "equity": set()}
    cfg, sig = universe_signals(state, monkeypatch, held=held)
    by = {a["name"]: a for a in sig["assets"]}
    assert len(sig["assets"]) == 30 and sig["universe"]["report"]["counts"]["etf"] == 5
    assert by["AVAX"]["dollar_volume_usd"] == pytest.approx(8e7, rel=1e-6) and by["AVAX"]["errors"] == []
    assert by["DOGE"]["held"] and by["LINK"]["held"] and not by["AVAX"]["held"]
    assert by["XRP"]["enabled"] is False and by["XRP"]["universe"]["outcome"] == "watch"
    assert by["AVAX"]["target_frac"] == 1.0 and by["AVAX"]["entry_frac"] == 1.0
    assert by["SOL"]["target_frac"] == 1.0 and by["SOL"]["entry_frac"] == 0.0         # green too long
    json.dumps(sig)
    text = sg.format_digest(sig)
    lines = text.splitlines()
    assert lines[2].startswith("SCAN 30 assets (0 explicit, 30 universe): 13 green, 0 partial, 7 eligible to buy "
                               "today, 2 held (*), 0 changed today, 0 with errors"), lines[2]
    rows = [x.split()[0] for x in lines if x and not x.startswith((" ", "MONEYLINE", "crypto", "SCAN", "UNIVERSE",
                                                                   "ASSET", "OTHERS", "Data", "Check"))]
    assert set(rows) == {"BTC", "ETH", "NEAR", "DOGE*", "AVAX", "UNI", "HBAR", "LINK*"}
    others = next(x for x in lines if x.startswith("OTHERS"))
    assert "GREEN, not eligible (5): SOL, ADA, BCH, XLM, SUI" in others and "watch-only (1): XRP (GREEN)" in others
    assert "RED (16):" in others and "22 more OK" in text
    assert len(lines) < 60
    full = sg.format_digest(sig, full=True)
    assert "OTHERS" not in full and all(f"\n{n} " in full or f"\n{n}*" in full for n in by)
    assert "(watch: ETF XRPC not confirmed tradable" in full


# ------------------------------------------------------------------ fetch-list

def test_fetch_list_with_the_universe(state, monkeypatch, capsys):
    held = {"crypto": {"DOGE", "LINK"}, "equity": set()}
    cfg = validate(uni_cfg())
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: held)
    monkeypatch.setattr(feeds, "get_bars", lambda a, c, now=None, inbox=None: fake_fetch()(
        a["signal"]["symbol"], "2024-01-01", now))

    real = universe.build_universe

    def b(cfg_, now, inbox, base=None, **k):
        return real(cfg_, now, inbox, fetch=fake_fetch(), products=fake_products, held=held)
    stage1 = universe.fetch_needs(cfg, NOW, state / "inbox", build=b)
    assert stage1["stage1"] and stage1["tradability"] == ["BSOL", "ETHA", "IBIT", "LTCC", "NRR", "XRPC"]
    calls = cli.fetch_calls(cfg, NOW, needs=stage1)
    assert [c["tool"] for c in calls] == ["get_currency_pairs", "get_equity_tradability"]
    assert calls[0]["params"] == {"limit": 700} and calls[1]["params"]["account_number"] == ACCT
    write_universe_inbox(state / "inbox")
    needs = universe.fetch_needs(cfg, NOW, state / "inbox", build=b)
    assert not needs["stage1"]
    assert needs["equity_quotes"] == ["ETHA", "IBIT", "NRR"]               # green + eligible ETF coins (not XRPC)
    assert needs["crypto_quotes"] == ["AVAX-USD", "DOGE-USD", "HBAR-USD", "LINK-USD", "UNI-USD"]   # + held LINK
    calls = cli.fetch_calls(cfg, NOW, needs=needs)
    tools = [c["tool"] for c in calls]
    assert tools == ["get_accounts", "get_portfolio", "get_equity_orders", "get_crypto_orders", "get_crypto_orders",
                     "get_equity_positions", "get_crypto_positions", "get_currency_pairs", "get_equity_tradability",
                     "get_equity_quotes", "get_crypto_quotes"]
    by = {c["tool"]: c["params"] for c in calls}
    assert by["get_currency_pairs"] == {"limit": 700}
    assert by["get_equity_tradability"] == {"account_number": ACCT,
                                            "symbols": ["BSOL", "ETHA", "IBIT", "LTCC", "NRR", "XRPC"]}
    many = dict(needs, tradability=[f"T{k:02d}" for k in range(23)], crypto_quotes=[f"C{k}-USD" for k in range(45)])
    calls = cli.fetch_calls(cfg, NOW, needs=many)
    assert [len(c["params"]["symbols"]) for c in calls if c["tool"] == "get_equity_tradability"] == [10, 10, 3]
    assert [len(c["params"]["symbols"]) for c in calls if c["tool"] == "get_crypto_quotes"] == [20, 20, 5]
    paths()["base"].mkdir(parents=True, exist_ok=True)
    paths()["config"].write_text(json.dumps(uni_cfg()))
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(universe, "build_universe", b)
    assert cli.main(["fetch-list"]) == 0
    out = capsys.readouterr().out
    assert "quotes for 8 held or green and entry-eligible today" in out and "Then run:" in out


# ------------------------------------------------------------------ planner with 30+ assets

def plan_inputs(state, monkeypatch, quotes_missing=(), held=None):
    held = held if held is not None else {"crypto": {"DOGE", "LINK"}, "equity": set()}
    cfg, sig = universe_signals(state, monkeypatch, held=held)
    eff, warns = universe.with_universe(cfg, sig)
    assert warns == []
    t = (NOW - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    quotes = {}
    for a in eff["assets"][1:]:                                    # the universe's (SPY is disabled)
        v = a["vehicle"]
        key = f"{v['symbol']}-USD" if v["type"] == "crypto" else v["symbol"]
        px = ETF_PX.get(v["symbol"]) or COINS[a["name"]][1]
        if key not in quotes_missing:
            quotes[key] = {"bid": px * 0.999, "ask": px * 1.001, "last": px, "ts": t, "captured_at": t,
                           "kind": v["type"], "problem": None}
    pairs = {f"{c}-USD": {"min_order_size": "0.01", "asset_increment": "0.01", "quote_increment": "0.000001",
                          "tradability": "tradable"} for c in COINS}
    cr = {"DOGE": {"qty": 1500.0, "sellable": 1500.0}, "LINK": {"qty": 12.0, "sellable": 12.0}}
    total = 2000.0
    snap = dict(as_of=t, total_value=total, cash=total - 348.0, buying_power=total - 348.0,
                crypto_buying_power=total - 348.0, equity_positions={}, crypto_positions=cr, quotes=quotes,
                open_orders=[], orders=[], pairs=pairs, account_number=ACCT, rhs_account_number=RHS, errors=[],
                warnings=[])
    sleeve = {"baseline": True, "sleeve": {"equity": {}, "crypto": {"DOGE": 1500.0, "LINK": 12.0}}, "mismatches": []}
    return eff, sig, snap, sleeve


def test_planner_many_assets_slots_ties_by_liquidity(state, monkeypatch):
    eff, sig, snap, sleeve = plan_inputs(state, monkeypatch)
    p = planner.make_plan(sig, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve)
    assert p["errors"] == [] and p["refetch"] == []
    al = p["allocation"]
    assert al["held"] == ["DOGE", "LINK"]
    # LINK (red) still counts until its sell fills: $2000 x 0.60 crypto cap = $1200 = DOGE + LINK + 4 new slots
    assert [x["asset"] for x in al["new"]] == ["BTC", "ETH", "AVAX", "NEAR"]       # same flip: more liquid first
    assert [x["asset"] for x in al["waiting"]] == ["UNI", "HBAR"]
    keys = [o["key"] for o in p["orders"]]
    assert keys[0] == "LINK|LINK|sell|0"                                          # exit of the red holding
    assert [k.split("|")[0] for k in keys[1:]] == ["BTC", "ETH", "AVAX", "NEAR"]   # DOGE: within its band
    btc = next(o for o in p["orders"] if o["asset"] == "BTC")
    assert btc["tool"] == "place_equity_order" and btc["params"]["symbol"] == "IBIT"
    assert next(o for o in p["orders"] if o["asset"] == "AVAX")["params"]["symbol"] == "AVAX"
    assert not any(o["asset"] == "XRP" for o in p["orders"])                      # watch only: never traded
    assert len(p["skipped"]) < 12 and len(p["warnings"]) < 5


def test_planner_missing_quotes_scale(state, monkeypatch):
    # HBAR (waiting for a slot) has no quote: nothing to say. AVAX (gets a slot) has none: re-fetch, no error.
    eff, sig, snap, sleeve = plan_inputs(state, monkeypatch, quotes_missing={"HBAR-USD", "AVAX-USD"})
    p = planner.make_plan(sig, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve)
    assert p["errors"] == []
    assert p["refetch"] == [{"tool": "get_crypto_quotes", "params": {"symbols": ["AVAX-USD"],
                                                                     "rhs_account_number": RHS},
                             "why": "quotes this plan needs (missing or stale)"}]
    sk = {x["asset"]: x["reason"] for x in p["skipped"]}
    assert "get_crypto_quotes for AVAX-USD" in sk["AVAX"] and "--attempt 1" in sk["AVAX"]
    assert "HBAR" not in sk or "quote" not in sk["HBAR"]
    assert [x["asset"] for x in p["allocation"]["new"]] == ["BTC", "ETH", "AVAX", "NEAR"]   # its slot is held
    assert not any(o["asset"] == "AVAX" for o in p["orders"])
    assert "RE-FETCH QUOTES" in cli.format_calls(dict(p, live=True)) and RHS in cli.format_calls(p)
    assert "RE-FETCH QUOTES: get_crypto_quotes" in planner.format_plan(p) and RHS not in planner.format_plan(p)
    # a held coin's missing quote is still an error (its exit cannot be sized)
    eff, sig, snap, sleeve = plan_inputs(state, monkeypatch, quotes_missing={"LINK-USD"})
    p = planner.make_plan(sig, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve)
    assert any("LINK" in e and "no quote" in e for e in p["errors"])
    assert p["refetch"][0]["params"]["symbols"] == ["LINK-USD"]


def test_planner_hold_only_never_buys(state, monkeypatch):
    eff, sig, snap, sleeve = plan_inputs(state, monkeypatch)
    for a in eff["assets"]:
        if a["name"] in ("DOGE", "BTC"):
            a["universe"]["hold_only"] = "illiquid; held, so kept for exits only"
    snap["crypto_positions"]["DOGE"]["qty"] = snap["crypto_positions"]["DOGE"]["sellable"] = 500.0
    sleeve["sleeve"]["crypto"]["DOGE"] = 500.0
    p = planner.make_plan(sig, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve)
    assert not any(o["asset"] in ("DOGE", "BTC") and o["params"]["side"] == "buy" for o in p["orders"])
    sk = {x["asset"]: x["reason"] for x in p["skipped"]}
    assert "hold only" in sk["DOGE"] and "hold only" in sk["BTC"]


def test_default_attempt_keeps_attempt_while_refetching(state):
    paths()["base"].mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    plan = {"plan_id": "x", "attempt": 2, "valid_until": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skipped": [], "refetch": [{"tool": "get_crypto_quotes", "params": {"symbols": ["AVAX-USD"]}}]}
    ledger.write_json(paths()["plan_current"], plan)
    assert cli.default_attempt(now) == 2
    ledger.write_json(paths()["plan_current"], dict(plan, refetch=[]))
    assert cli.default_attempt(now) == 1


# ------------------------------------------------------------------ init --update

def test_init_update_adds_missing_blocks_only(state, monkeypatch, capsys):
    assert cli.main(["init"]) == 0
    old = json.loads(cfgmod.EXAMPLE.read_text())
    for k in ("universe", "allocation", "entry"):
        old.pop(k)
    old["limits"]["max_day_usd"] = 777
    old["assets"] = old["assets"][:1]
    old["account"]["account_number"] = ACCT
    f = paths()["config"]
    f.write_text(json.dumps(old))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    capsys.readouterr()
    assert cli.main(["init", "--update"]) == 2                    # no terminal: shows what it would add only
    out = capsys.readouterr()
    assert "allocation" in out.out and "universe" in out.out and "interactive terminal" in out.err
    assert json.loads(f.read_text()) == old
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert cli.main(["init", "--update"]) == 1 and json.loads(f.read_text()) == old
    monkeypatch.setattr("builtins.input", lambda prompt="": "update")
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    assert cli.main(["init", "--update"]) == 0
    new = json.loads(f.read_text())
    assert set(new) == set(old) | {"universe", "allocation", "entry"}
    assert all(new[k] == v for k, v in old.items())                # nothing existing changed
    assert new["universe"] == json.loads(cfgmod.EXAMPLE.read_text())["universe"]
    backups = list(f.parent.glob("config.json.bak-*"))
    assert len(backups) == 1 and json.loads(backups[0].read_text()) == old
    assert "added: allocation, entry, universe" in capsys.readouterr().out
    assert cli.main(["init", "--update"]) == 0 and "up to date" in capsys.readouterr().out
    bad = dict(old, limits=dict(old["limits"], max_asset_frac=0.10))   # the example's slot 0.20 would not fit
    f.write_text(json.dumps(bad))
    assert cli.main(["init", "--update"]) == 2 and json.loads(f.read_text()) == bad
    assert "slot_frac" in capsys.readouterr().err


# ------------------------------------------------------------------ doctor

def test_doctor_universe_checks(state):
    def lines(cfg):
        rep = doctor.Report()
        doctor.check_universe(rep, validate(cfg), paths())
        return {(s, n, d) for s, n, d in rep.rows}
    off = lines(uni_cfg(universe={"enabled": False}))
    assert any(s == "PASS" and "universe off" in d and "init --update" in d for s, n, d in off)
    raw = uni_cfg(assets=[explicit("SOL", "crypto", "SOL"), explicit("BTC", "equity", "IBIT", enabled=False)],
                  universe={"exclude": ["USDC"]})
    got = lines(raw)
    text = "\n".join(f"{s} {n} {d}" for s, n, d in got)
    assert "PASS universe crypto universe on: source robinhood, at most 30 coins" in text
    assert 'WARN crypto vehicle SOL trades SOL directly' in text and '"symbol": "BSOL"' in text
    assert "WARN universe the disabled explicit asset BTC keeps BTC out" in text
    assert "WARN universe universe.crypto.exclude lacks USDT" in text
    assert "WARN currency pairs no get_currency_pairs capture yet" in text
    assert "WARN coinbase cache none yet" in text
    write_cap(paths()["inbox"], "get_currency_pairs", pairs_response(), {"limit": 700}, datetime.now(UTC) -
              timedelta(days=10))
    feeds._write_atomic(feeds.coinbase_cache_dir() / "BTC-USD.csv", "date,open,high,low,close,volume\n")
    text = "\n".join(f"{s} {n} {d}" for s, n, d in lines(uni_cfg()))
    assert "WARN currency pairs the newest get_currency_pairs capture is 10 days old" in text
    assert "PASS coinbase cache" in text and "1 products" in text
    write_cap(paths()["inbox"], "get_currency_pairs", pairs_response(), {"limit": 700}, datetime.now(UTC))
    text = "\n".join(f"{s} {n} {d}" for s, n, d in lines(uni_cfg(allocation={"method": "fixed"})))
    assert "PASS currency pairs newest get_currency_pairs capture 0 h old" in text
    assert "WARN universe allocation.method is fixed" in text
    assert ACCT not in text and RHS not in text


def test_doctor_bom_message_names_vs_code(tmp_path):
    (tmp_path / "settings.json").write_bytes(b"\xef\xbb\xbf{}")
    _, prob = doctor._read_settings(tmp_path, "settings.json")
    assert "code .claude/settings.json" in prob and "Save with Encoding" in prob and "otepad" not in prob


def test_docs_never_say_notepad():
    for f in (REPO / "agentic").rglob("*"):
        if f.suffix in (".py", ".md", ".json", ".sh"):
            assert "notepad" not in f.read_text(encoding="utf-8").lower(), f
    assert "notepad" not in (REPO / ".claude" / "commands" / "moneyline.md").read_text().lower()


# ------------------------------------------------------------------ end to end through the real hooks

def read_response(tool, params, w):
    """Synthetic result for one universe fetch-list call (official output shapes)."""
    qts = w["quote_time"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cash = 2000.0 - w["held_usd"]
    if tool == "get_accounts":
        return env({"accounts": [{"account_number": ACCT, "rhs_account_number": RHS, "agentic_allowed": True}]})
    if tool == "get_portfolio":
        return env({"total_value": "2000.00", "cash": f"{cash:.2f}",
                    "buying_power": {"buying_power": f"{cash:.2f}", "unleveraged_buying_power": f"{cash:.2f}"},
                    "crypto_buying_power": {"buying_power": f"{cash:.2f}"}})
    if tool == "get_equity_positions":
        return env({"positions": [], "next": ""})
    if tool == "get_crypto_positions":
        rows = [{"currency": {"code": c, "type": "cryptocurrency"}, "currency_pair_id": f"pair-{c.lower()}",
                 "quantity": q, "quantity_transferable": q} for c, q in HELD.items()]
        return env({"results": rows, "next": ""})
    if tool == "get_equity_orders":
        return env({"orders": [], "next": ""})
    if tool == "get_crypto_orders":
        return env({"rhs_account_number": RHS, "results": [], "next": ""})
    if tool == "get_currency_pairs":
        assert params["limit"] == 700
        return pairs_response()
    if tool == "get_equity_tradability":
        assert params["account_number"] == ACCT and len(params["symbols"]) <= 10
        return tradability_response(params["symbols"])
    if tool == "get_equity_quotes":
        return env({"results": [{"quote": {"symbol": s, "bid_price": f"{ETF_PX[s] * 0.999:.4f}",
                                           "ask_price": f"{ETF_PX[s] * 1.001:.4f}", "last_trade_price": f"{ETF_PX[s]}",
                                           "venue_bid_time": qts, "venue_ask_time": qts, "has_traded": True,
                                           "state": "active"}} for s in params["symbols"]]})
    if tool == "get_crypto_quotes":
        rows = []
        for p in params["symbols"]:
            if p in w["no_quote"]:
                continue
            px = COINS[p[:-4]][1]
            rows.append({"symbol": p.replace("-", ""), "id": f"pair-{p[:-4].lower()}", "bid_price": f"{px * 0.999:.8f}",
                         "ask_price": f"{px * 1.001:.8f}", "mark_price": f"{px:.8f}", "open_price": f"{px:.8f}",
                         "updated_at": qts})
        return env({"results": rows})
    raise AssertionError(f"unexpected read {tool}")


def test_universe_end_to_end_dry_run_through_the_hooks(state, monkeypatch, capsys):
    now = real_now()
    fake = FakeCoinbase(cal.last_closed_crypto_bar(now))
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert cli.main(["init"]) == 0
    (state / "config.json").write_text(json.dumps(uni_cfg()))
    w = {"quote_time": now - timedelta(minutes=1), "held_usd": 1500 * 0.12 + 12 * 14.0, "no_quote": set()}

    def reads(calls):
        for c in calls:
            mcp_call(state, c["tool"], c["params"], read_response(c["tool"], c["params"], w))

    capsys.readouterr()
    assert cli.main(["fetch-list", "--json"]) == 0                     # stage 1: the coin list first
    stage1 = json.loads(capsys.readouterr().out)
    assert [c["tool"] for c in stage1] == ["get_currency_pairs", "get_equity_tradability"]
    reads(stage1)
    assert cli.main(["fetch-list", "--json"]) == 0
    calls = json.loads(capsys.readouterr().out)
    tools = [c["tool"] for c in calls]
    assert tools[0] == "get_accounts" and "get_currency_pairs" in tools and tools[-1] == "get_crypto_quotes"
    assert fake.candle_calls() and len(fake.candle_calls()) >= 3 * 30              # first scan: ~2 years per coin
    eq = next(c for c in calls if c["tool"] == "get_equity_quotes")["params"]["symbols"]
    assert eq == ["ETHA", "IBIT", "NRR"]                                # XRPC: not tradable, so no quote
    w["no_quote"] = {"LINK-USD"}                                       # LINK is not held yet: the first plan asks
    reads(calls)
    n_candles = len(fake.candle_calls())
    assert cli.main(["run"]) == 1                                      # LINK's exit needs a quote: an error
    assert len(fake.candle_calls()) == n_candles                       # the scan reused the cache
    out = capsys.readouterr().out
    assert "SCAN 30 assets (0 explicit, 30 universe)" in out and "UNIVERSE crypto (Robinhood pairs captured" in out
    assert "XRP: ETF XRPC not confirmed tradable" in out and "RE-FETCH QUOTES" in out
    plan = json.loads((state / "plan_current.json").read_text())
    assert plan["refetch"][0]["params"]["symbols"] == ["LINK-USD"]
    w["no_quote"] = set()
    w["quote_time"] = datetime.now(UTC)
    reads(plan["refetch"])                                             # the exact call, once
    assert cli.main(["plan"]) == 0                                     # same attempt; nothing was placed
    plan = json.loads((state / "plan_current.json").read_text())
    out = capsys.readouterr().out
    assert plan["errors"] == [] and plan["refetch"] == [] and plan["attempt"] == 1
    keys = [o["key"] for o in plan["orders"]]
    assert keys[0] == "LINK|LINK|sell|0"
    assert [x["asset"] for x in plan["allocation"]["new"]] == ["BTC", "ETH", "AVAX", "NEAR"]
    assert {o["params"]["symbol"] for o in plan["orders"]} >= {"LINK", "IBIT", "ETHA", "AVAX", "NRR"}
    for o in plan["orders"]:                                           # every plan order passes the real guard
        assert hook(PRE, state, o["preview_tool"], o["preview_params"]).returncode == 0
        r = hook(PRE, state, o["tool"], o["params"])
        assert r.returncode == 0, r.stderr.decode()
    ibit = next(o for o in plan["orders"] if o["params"]["symbol"] == "IBIT")
    for change in ({"symbol": "XRPC"}, {"quantity": str(int(float(ibit["params"]["quantity"])) + 1)},
                   {"side": "sell"}):
        r = hook(PRE, state, ibit["tool"], {**ibit["params"], **change})
        assert r.returncode == 2 and b"BLOCKED" in r.stderr, change
    for o in plan["orders"]:
        assert hook(POST, state, o["tool"], o["params"], env({"order": None})).returncode == 0
    assert not (state / "STOP").exists()
    assert ledger.placed_usd(datetime.now(UTC)) == pytest.approx(sum(o["notional_usd"] for o in plan["orders"]))
    sig = json.loads((state / "signals" / f"signals_{now.date().isoformat()}.json").read_text())
    assert sig["universe"]["report"]["counts"]["etf"] == 5 and len(sig["universe"]["assets"]) == 30
    for f in (state / "journal.jsonl", state / "hook.log"):
        assert ACCT not in f.read_text() and RHS not in f.read_text()


# ------------------------------------------------------------------ held coins after a settings change; outages

def day_run(state, monkeypatch, capsys, w):
    """fetch-list (again after a stage 1), every listed read captured at NOW - 2 min, then run (cli._now = NOW)."""
    def reads():
        capsys.readouterr()
        assert cli.main(["fetch-list", "--json"]) == 0
        calls = json.loads(capsys.readouterr().out)
        for c in calls:
            resp = pairs_response() if c["tool"] == "get_currency_pairs" else read_response(c["tool"], c["params"], w)
            write_cap(paths()["inbox"], c["tool"], resp, c["params"], NOW - timedelta(minutes=2))
        return calls
    calls = reads()
    if calls[0]["tool"] == "get_currency_pairs":
        calls = reads()
    capsys.readouterr()
    rc = cli.main(["run"])
    return calls, rc, capsys.readouterr().out, json.loads(paths()["plan_current"].read_text())


@pytest.mark.parametrize("change", [{"direct_crypto": False}, {"enabled": False}])
def test_held_coins_keep_their_exits_after_a_settings_change(state, monkeypatch, capsys, change):
    # day 1: the universe trades, DOGE and LINK are the sleeve's; day 2: direct coins or the universe turned off
    monkeypatch.setattr(urllib.request, "urlopen", FakeCoinbase(date(2026, 10, 18)))
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    assert cli.main(["init"]) == 0
    raw = uni_cfg(live=False)
    paths()["config"].write_text(json.dumps(raw))
    w = {"quote_time": NOW - timedelta(minutes=2), "held_usd": 1500 * 0.12 + 12 * 14.0, "no_quote": set()}
    day_run(state, monkeypatch, capsys, w)
    for f in paths()["inbox"].glob("*.json"):
        f.unlink()
    raw["universe"]["crypto"].update(change)
    paths()["config"].write_text(json.dumps(raw))
    calls, rc, out, plan = day_run(state, monkeypatch, capsys, w)
    tools = [c["tool"] for c in calls]
    assert "get_crypto_positions" in tools and tools.count("get_crypto_orders") == 2
    assert next(c for c in calls if c["tool"] == "get_crypto_quotes")["params"]["symbols"] == ["DOGE-USD", "LINK-USD"]
    assert rc == 0 and plan["errors"] == [] and "RECONCILE ok" in out and not paths()["BLOCK_BUYS"].exists()
    assert not any("re-run signals" in x for x in plan["warnings"])        # watch-only coins are accepted too
    keys = [o["key"] for o in plan["orders"]]
    assert "LINK|LINK|sell|0" in keys                                      # the red holding still exits
    assert not any(o["tool"] == "place_crypto_order" and o["params"]["side"] == "buy" for o in plan["orders"])
    if change == {"enabled": False}:
        assert keys == ["LINK|LINK|sell|0"]                                # nothing new is bought
        assert "UNIVERSE crypto (off: held coins only, kept for exits): 2 coins considered" in out
        assert "DOGE: held directly by the sleeve; hold only: universe.crypto is off" in out


def test_with_universe_accepts_watch_only_coins_without_direct_crypto(state):
    write_universe_inbox(state / "inbox")
    raw = uni_cfg(universe={"direct_crypto": False})
    assets, rep = build(raw)
    assert rep["counts"]["watch"] == 25 and sum(a["enabled"] for a in assets) == 5
    eff, warns = universe.with_universe(validate(raw), {"universe": {"assets": assets}})
    assert warns == [] and len(eff["assets"]) == 1 + len(assets)
    assert [a["name"] for a in eff["assets"] if a["enabled"]] == [a["name"] for a in assets if a["enabled"]]
    raw = uni_cfg(universe={"direct_crypto": False, "prefer_etf": False})
    assets, _ = build(raw)
    assert universe.with_universe(validate(raw), {"universe": {"assets": assets}})[1] == []
    on = copy.deepcopy(next(a for a in assets if a["name"] == "DOGE"))
    on["enabled"] = True                                                   # a direct buy the config forbids
    assert "not one the universe settings allow" in universe.with_universe(validate(raw),
                                                                          {"universe": {"assets": [on]}})[1][0]


def test_fetch_list_asks_for_crypto_while_the_account_holds_coins(state):
    cfg = validate(uni_cfg(universe={"enabled": False}))
    needs = {"stage1": False}

    def tools():
        return [c["tool"] for c in cli.fetch_calls(cfg, NOW, needs=needs)]
    assert "get_crypto_positions" not in tools() and not cli.crypto_needed(cfg)
    paths()["base"].mkdir(parents=True, exist_ok=True)
    ledger.write_json(paths()["positions_ref"], {"as_of": "2026-10-18T15:00:00Z", "equity": {},
                                                 "crypto": {"DOGE": {"qty": 1500.0}}, "orders": {},
                                                 "sleeve": {"equity": {}, "crypto": {}}})
    t = tools()
    assert "get_crypto_positions" in t and t.count("get_crypto_orders") == 2 and cli.crypto_needed(cfg)
    ledger.write_json(paths()["positions_ref"], {"as_of": "2026-10-18T15:00:00Z", "equity": {}, "crypto": {},
                                                 "orders": {}, "sleeve": {"equity": {}, "crypto": {}}})
    assert not cli.crypto_needed(cfg)
    ledger.append_journal({"event": "place", "tool": "mcp__x__place_crypto_order",
                           "params": {"symbol": "DOGE-USD", "side": "buy", "quantity": "10"}}, now_utc=NOW)
    assert cli.crypto_needed(cfg)                                          # a buy since the baseline may have filled
    assert cli.crypto_needed(cfg, {"crypto_vehicles": True}) and "get_crypto_positions" in tools()


def test_fetch_list_account_check_follows_the_universe_needs(state, monkeypatch, capsys):
    raw = uni_cfg(universe={"direct_crypto": False})
    raw["account"]["rhs_account_number"] = "FILL-IN"
    assert cli.main(["init"]) == 0
    paths()["config"].write_text(json.dumps(raw))
    assert not cli.crypto_needed(validate(raw))
    needs = {"stage1": False, "tradability": [], "equity_quotes": [], "crypto_quotes": ["DOGE-USD"],
             "candidates": ["DOGE"], "report": None, "crypto_vehicles": True}   # a held coin kept for exits
    monkeypatch.setattr(universe, "fetch_needs", lambda cfg, now=None, **k: needs)
    capsys.readouterr()
    assert cli.main(["fetch-list"]) == 2                                   # never a placeholder in a crypto call
    assert "account.rhs_account_number not filled in" in capsys.readouterr().out
    needs["crypto_vehicles"] = False
    needs["crypto_quotes"] = []
    assert cli.main(["fetch-list"]) == 0 and "get_crypto" not in capsys.readouterr().out


def test_coinbase_outage_trips_the_breaker(state, monkeypatch):
    write_universe_inbox(state / "inbox")
    attempts = []

    def down(req, timeout=None):
        attempts.append(timeout)
        raise urllib.error.URLError("getaddrinfo failed")
    monkeypatch.setattr(urllib.request, "urlopen", down)
    monkeypatch.setattr(feeds, "BACKOFF_S", 0.0)
    eth = frame("ETH", date(2026, 10, 18), forming=False)                 # current cached bars: still scanned
    feeds._write_atomic(feeds.coinbase_cache_dir() / "ETH-USD.csv",
                        eth.to_csv(index_label="date", date_format="%Y-%m-%d"))
    monkeypatch.setattr(universe, "sleeve_vehicles", lambda base=None: {"crypto": {"DOGE"}, "equity": set()})
    sig = sg.compute_signals(validate(uni_cfg()), NOW, state / "inbox")
    rep = sig["universe"]["report"]
    # the product list (1 retry) and two coins (1 retry each), then no more requests: signals included
    assert len(attempts) == 2 + 2 * 2 and set(attempts) == {universe.SCAN_TIMEOUT_S}
    assert rep["coinbase_down"] == "2 Coinbase requests in a row failed"
    assert any("no further requests this run" in x for x in rep["warnings"])
    c = by_coin(rep)
    assert c["ETH"]["outcome"] == "etf" and c["ETH"]["dollar_volume_usd"] == pytest.approx(5e8, rel=1e-6)
    assert c["SOL"]["category"] == "Coinbase data error" and "not scanned" in c["SOL"]["reason"]
    assert c["DOGE"]["outcome"] == "direct" and "Coinbase unreachable" in c["DOGE"]["hold_only"]
    by = {a["name"]: a for a in sig["assets"]}
    assert by["ETH"]["errors"] == [] and any("no readable cache" in e for e in by["DOGE"]["errors"])
    assert any("Coinbase unreachable" in x for x in universe.summary_lines(rep))


def test_empty_pairs_capture_falls_back(state):
    inbox = state / "inbox"
    cfg = validate(uni_cfg(universe={"symbols": ["DOGE"]}))
    write_universe_inbox(inbox, at=NOW - timedelta(hours=3))
    write_cap(inbox, "get_currency_pairs", env({"results": None, "next": ""}), {"limit": 700},
              NOW - timedelta(hours=1))
    pc = universe.pairs_capture(inbox, NOW)
    assert len(pc["pairs"]) == len(COINS) and pc["empty"] and pc["empty"] != pc["file"]
    assets, rep = build()
    assert len(assets) == 30 and any("has no USD pairs: the earlier capture" in x for x in rep["warnings"])
    for f in inbox.glob("*get_currency_pairs*"):
        if f.name != pc["empty"]:
            f.unlink()
    pc = universe.pairs_capture(inbox, NOW)
    assert pc["pairs"] == {} and pc["empty"] == pc["file"]
    _, rep = build(uni_cfg(universe={"symbols": ["DOGE"]}))
    assert {x["coin"] for x in rep["coins"]} == {"DOGE"} and by_coin(rep)["DOGE"]["outcome"] == "direct"
    assert any("only universe.crypto.symbols" in x for x in rep["warnings"]) and rep["pairs"] is None

    def b(cfg_, now, inbox_, base=None, **k):
        return universe.build_universe(cfg_, now, inbox_, fetch=fake_fetch(), products=fake_products,
                                       held={"equity": set(), "crypto": set()})
    assert not universe.fetch_needs(cfg, NOW, inbox, build=b)["stage1"]
    r = doctor.Report()
    doctor.check_universe(r, cfg, paths())
    assert any(s == "WARN" and "has no USD pairs" in d for s, n, d in r.rows)


class HoleServer(CandleServer):
    """CandleServer without any candle for one day (a permanent hole in Coinbase's history)."""

    def __init__(self, hole, **k):
        super().__init__(**k)
        self.hole = int((pd.Timestamp(hole) - EPOCH).total_seconds())

    def __call__(self, req, timeout=None):
        rows = [r for r in json.loads(super().__call__(req, timeout).read()) if r[0] != self.hole]
        return io.BytesIO(json.dumps(rows).encode())


def test_permanent_coinbase_gap_is_not_refetched_daily(state):
    srv = HoleServer("2025-06-01", first_day="2025-01-01")
    pace = feeds.Pacer(clock=lambda: 0.0, sleep=lambda s: None)
    issues = []
    feeds.coinbase_daily_cached("AAA-USD", "2025-01-01", datetime(2026, 10, 18, 1, 0, tzinfo=UTC), srv, pace=pace,
                                issues=issues)
    assert len(srv.ranges) == 3 and issues == []
    for day in (19, 20, 21):
        srv.ranges.clear()
        df = feeds.coinbase_daily_cached("AAA-USD", "2025-01-01", datetime(2026, 10, day, 1, 0, tzinfo=UTC), srv,
                                         pace=pace, issues=issues)
        assert len(srv.ranges) == 1 and issues == [], day                  # only the new bar, no warning
        assert feeds.gap_dates(df.index) == ["2025-06-01"]
    f = feeds.coinbase_cache_dir() / "AAA-USD.csv"
    f.write_text(feeds.read_coinbase_cache(f).drop(pd.Timestamp("2026-01-05"))
                 .to_csv(index_label="date", date_format="%Y-%m-%d"))
    srv.ranges.clear()
    feeds.coinbase_daily_cached("AAA-USD", "2025-01-01", datetime(2026, 10, 22, 1, 0, tzinfo=UTC), srv, pace=pace,
                                issues=issues)
    assert len(srv.ranges) == 3 and any("2 missing days" in x for x in issues)   # a new hole: fetched again


def test_digest_does_not_count_hold_only_coins_as_eligible(state, monkeypatch):
    cfg, sig = universe_signals(state, monkeypatch, held={"crypto": {"DOGE", "LINK", "BONK"}, "equity": set()})
    bonk = next(a for a in sig["assets"] if a["name"] == "BONK")
    assert "illiquid" in bonk["universe"]["hold_only"] and bonk["target_frac"] > 0 and bonk["entry_frac"] > 0
    assert not sg._eligible(bonk)
    assert "7 eligible to buy today, 3 held (*)" in sg.format_digest(sig).splitlines()[2]


def test_stock_named_like_a_coin_is_reported(state):
    write_universe_inbox(state / "inbox")
    ltc = {"name": "LTC", "class": "equity", "enabled": False, "alloc_frac": 0.1, "mode": "split",
           "signal": {"source": "computed", "feed": "robinhood", "symbol": "LTC"},
           "vehicle": {"type": "equity", "symbol": "LTC", "fractional": True}}
    raw = uni_cfg(assets=uni_cfg()["assets"] + [ltc])
    c = by_coin(build(raw)[1])
    assert c["LTC"]["outcome"] == "explicit" and "rename it to let the universe trade the coin" in c["LTC"]["reason"]
    rep = doctor.Report()
    doctor.check_universe(rep, validate(raw), paths())
    text = "\n".join(f"{s} {n} {d}" for s, n, d in rep.rows)
    assert "WARN universe the equity asset LTC shares the coin code LTC" in text and "SPY shares" not in text


def test_slot_ties_keep_config_order_for_explicit_assets():
    def it(name, cls, dv=None, uni=False):
        a = {"name": name, "class": cls, **({"universe": {"outcome": "direct"}} if uni else {})}
        return {"name": name, "asset": a, "flip": "2026-10-14", "sig": {"dollar_volume_usd": dv}}
    its = [it("SPY", "equity"), it("ETH", "crypto", 5e8), it("SOL", "crypto", 9e8), it("AVAX", "crypto", 8e7, True),
           it("DOGE", "crypto", 1.5e8, True)]
    order = {x["name"]: i for i, x in enumerate(its)}

    def names(prio):
        return [x["name"] for x in planner._ranked(its, prio, order)]
    assert names("newest_flip") == ["SPY", "ETH", "SOL", "DOGE", "AVAX"]
    assert names("crypto_first") == ["ETH", "SOL", "DOGE", "AVAX", "SPY"]
    assert names("equity_first") == ["SPY", "ETH", "SOL", "DOGE", "AVAX"]


def test_pegged_coin_is_dropped_without_a_list(state):
    base = fake_fetch()

    def fetch(product, start, now):
        if product != "PEGX-USD":
            return base(product, start, now)
        f = frame("AVAX", date(2026, 10, 18), forming=False)
        wobble = pd.Series(range(len(f)), index=f.index).mod(7).astype(float) * 0.004
        f["open"] = f["low"] = 0.995 + wobble
        f["close"] = 0.998 + wobble
        f["high"] = 1.01 + wobble
        f["volume"] = 1e8
        return f[f.index >= pd.Timestamp(start)]
    none = {"products": None, "fetched_at": None, "error": None}
    c = by_coin(build(uni_cfg(universe={"source": "list", "symbols": ["PEGX", "AVAX"]}), fetch=fetch,
                      products=lambda now: none)[1])
    assert c["PEGX"]["outcome"] == "excluded" and c["PEGX"]["category"] == "stablecoin/wrapped"
    assert "pegged" in c["PEGX"]["reason"] and c["AVAX"]["outcome"] == "direct"
    c = by_coin(build(uni_cfg(universe={"source": "list", "symbols": ["PEGX"]}), fetch=fetch,
                      products=lambda now: none, held={"crypto": {"PEGX"}, "equity": set()})[1])
    assert c["PEGX"]["outcome"] == "direct" and "pegged" in c["PEGX"]["hold_only"]   # held: exits only


def test_held_etf_not_confirmed_tradable_is_exits_only(state, monkeypatch):
    eff, sig, snap, sleeve = plan_inputs(state, monkeypatch, held={"crypto": {"DOGE", "LINK"}, "equity": {"XRPC"}})
    xrp = next(a for a in eff["assets"] if a["name"] == "XRP")
    assert xrp["enabled"] and xrp["vehicle"]["symbol"] == "XRPC"
    assert "XRPC not confirmed tradable (tradeable is not true): exits only" in xrp["universe"]["hold_only"]
    snap["equity_positions"]["XRPC"] = {"qty": 5.0, "sellable": 5.0, "avg_buy_price": 8.0}
    sleeve["sleeve"]["equity"]["XRPC"] = 5.0
    p = planner.make_plan(sig, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve)
    assert not any(o["asset"] == "XRP" for o in p["orders"])
    assert "hold only" in {x["asset"]: x["reason"] for x in p["skipped"]}["XRP"]
    next(a for a in sig["assets"] if a["name"] == "XRP").update(target_frac=0.0, prev_target_frac=1.0, changed=True)
    p = planner.make_plan(sig, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve)
    assert "XRP|XRPC|sell|0" in [o["key"] for o in p["orders"]]             # the exit still goes through


def test_fixed_allocation_keeps_green_universe_holdings(state, monkeypatch):
    eff, sig, snap, sleeve = plan_inputs(state, monkeypatch)
    eff["allocation"]["method"] = "fixed"
    p = planner.make_plan(sig, snap, eff, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=sleeve)
    assert [o["key"] for o in p["orders"]] == ["LINK|LINK|sell|0"]         # red: sold; green DOGE kept; no buys
    assert "no allocation of its own (alloc_frac 0): target -> 0.00" in p["orders"][0]["reason"]
    assert "allocation.method fixed" in {x["asset"]: x["reason"] for x in p["skipped"]}["DOGE"]
    p = planner.make_plan(sig, snap, eff, NOW, 1, {"FLATTEN": True}, placed_today_usd=0.0, journal=[],
                          sleeve=sleeve)
    assert sorted(o["key"] for o in p["orders"]) == ["DOGE|DOGE|sell|0", "LINK|LINK|sell|0"]
