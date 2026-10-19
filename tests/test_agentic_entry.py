"""Tests for the entry policy (agentic/entry.py) and the allocation methods (fixed / slots) in planner.py, config
validation of both blocks, and the signal fields they read. Synthetic data only; no network."""
import copy
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentic import config as cfgmod  # noqa: E402
from agentic import data as feeds  # noqa: E402
from agentic import entry, planner  # noqa: E402
from agentic import signals as sg  # noqa: E402
from agentic.indicator import tranche_targets  # noqa: E402
from tests.test_agentic_e2e import tv_csv, trend  # noqa: E402
from tests.test_agentic_planner import ACCT, NOW, RHS, check_schema, owned, pos, quote, snap  # noqa: E402

UTC = timezone.utc
CB, EB = "2026-10-18", "2026-10-16"          # closed crypto bar / stock session at NOW (Monday 11:00 ET)
WAIT = "too late to join (max 20): waiting for the next flip"


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(tmp_path / "state"))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)


# ------------------------------------------------------------------ helpers: 3 crypto (via ETFs) + 3 stock ETFs

def A(name, cls, sym, mode="immediate", **extra):
    src = {"source": "computed", "feed": "coinbase" if cls == "crypto" else "robinhood",
           "symbol": f"{name}-USD" if cls == "crypto" else sym}
    return {"name": name, "class": cls, "enabled": True, "alloc_frac": 0.15, "mode": mode, "signal": src,
            "vehicle": {"type": "equity", "symbol": sym}, **extra}


SIX = [A("ETH", "crypto", "ETHA"), A("SOL", "crypto", "SOLQ"), A("BTC", "crypto", "BTCQ"),
       A("SPY", "equity", "SPY"), A("QQQ", "equity", "QQQ", "split"), A("IWM", "equity", "IWM")]
CLS = {a["name"]: a["class"] for a in SIX}
VSYM = {a["name"]: a["vehicle"]["symbol"] for a in SIX}
TEN = {s: quote(9.99, 10.01) for s in VSYM.values()}          # every vehicle at ~$10: whole-share limits at 10.06


def cfg(*names, alloc=None, entry_=None, live=False, assets=None, **limits):
    names = names or tuple(a["name"] for a in SIX)
    raw = {"account": {"account_number": ACCT, "rhs_account_number": RHS}, "live": live, "capital": {"max_usd": 10000},
           "limits": {"max_order_usd": 10000, "max_day_usd": 50000, **limits},
           "assets": assets or [copy.deepcopy(a) for a in SIX if a["name"] in names]}
    if alloc is not None:
        raw["allocation"] = alloc
    if entry_ is not None:
        raw["entry"] = entry_
    return cfgmod.validate(raw)


def slots(frac=0.25, priority="crypto_first", **caps):
    return {"method": "slots", "slot_frac": frac, "priority": priority, "class_max_frac": caps or {"crypto": 1.0}}


def tr(green, bars=0, w=1.0, n=1, flip=None, close=10.0, bar=CB):
    """One tranche record as signals.py writes it; a green one flipped `bars` bars ago (on `flip`)."""
    if not green:
        return {"weight": w, "n_entry": n, "n_exit": n, "green": False, "pending": 0, "last_green_flip_date": None,
                "bars_since_green_flip": None, "flip_close": None}
    day = flip or (None if bars is None else (date.fromisoformat(bar) - timedelta(days=bars)).isoformat())
    return {"weight": w, "n_entry": n, "n_exit": n, "green": True, "pending": 0, "last_green_flip_date": day,
            "bars_since_green_flip": bars, "flip_close": close}


def S(name, *tranches, close=10.0, bar=None, errors=()):
    """A signal: one green immediate tranche flipped on the bar unless tranches are given."""
    bar = bar or (CB if CLS.get(name, "crypto") == "crypto" else EB)
    ts = list(tranches) or [tr(True, 0, bar=bar)]
    return {"name": name, "class": CLS.get(name, "crypto"), "bar_date": bar, "close": close, "tranches": ts,
            "target_frac": sum(t["weight"] for t in ts if t["green"]), "prev_target_frac": None,
            "errors": list(errors), "warnings": []}


def plan(sigs, c, eq=None, now=NOW, flags=None, start="", bp=10000.0, total=10000.0, sleeve=None, journal=(),
         open_orders=()):
    s = snap(now, total=total, bp=bp, eq=eq or {}, quotes={k: quote(9.99, 10.01, now) for k in VSYM.values()},
             open_orders=open_orders)
    p = planner.make_plan({"date": now.date().isoformat(), "assets": list(sigs)}, s, c, now, 1, flags or {},
                          placed_today_usd=0.0, journal=list(journal), sleeve=owned(s) if sleeve is None else sleeve,
                          strategy_start=start)
    check_schema(p)
    return p


def placed(sym, ts, side="buy"):
    """A journaled place of this system (what the PostToolUse hook writes)."""
    return {"ts": ts, "event": "place", "tool": "place_equity_order", "order_id": f"o-{sym}-{ts}",
            "params": {"symbol": sym, "side": side, "type": "limit", "quantity": "1", "limit_price": "10.06"}}


def bought(p):
    return {o["asset"]: float(o["params"]["quantity"]) for o in p["orders"] if o["params"]["side"] == "buy"}


def sold(p):
    return {o["asset"]: float(o["params"]["quantity"]) for o in p["orders"] if o["params"]["side"] == "sell"}


def why(p, name):
    return " | ".join(x["reason"] for x in p["skipped"] if x["asset"] == name)


# ------------------------------------------------------------------ entry.py

def test_policies_on_single_tranches():
    e = dict(cfgmod.DEFAULT_ENTRY)
    assert entry.tranche_entry(tr(True, 20), 10.0, e, CB) is None                         # 20 bars: still in
    assert entry.tranche_entry(tr(True, 21), 10.0, e, CB) == f"green 21 bars, {WAIT}"
    assert "no flip in the available history" in entry.tranche_entry(tr(True, None), 10.0, e, CB)
    old_file = {k: v for k, v in tr(True, 0).items() if k != "bars_since_green_flip"}
    assert "re-run signals" in entry.tranche_entry(old_file, 10.0, e, CB)
    assert entry.tranche_entry(tr(True, 300), 10.0, dict(e, policy="join"), CB) is None
    assert entry.tranche_entry(old_file, 10.0, dict(e, policy="join"), CB) is None
    fresh = dict(e, policy="fresh_only")
    assert entry.tranche_entry(tr(True, 2), 10.0, fresh, "2026-10-16") is None             # flip 10-16 >= start
    assert "before the strategy start 2026-10-17 (fresh_only)" in entry.tranche_entry(tr(True, 2), 10.0, fresh,
                                                                                         "2026-10-17")
    assert "too late" in entry.tranche_entry(tr(True, 25), 10.0, fresh, "2026-01-01")      # and join_recent's limit


def test_rise_cap():
    e = dict(cfgmod.DEFAULT_ENTRY, max_join_rise_frac=0.10)
    assert entry.tranche_entry(tr(True, 3, close=10.0), 11.0, e, CB) is None                # exactly +10%
    assert "up 10.5% since the green flip" in entry.tranche_entry(tr(True, 3, close=10.0), 11.05, e, CB)
    assert entry.tranche_entry(tr(True, 3, close=10.0), 11.05, dict(e, policy="join"), CB) is None
    off = dict(cfgmod.DEFAULT_ENTRY, max_join_rise_frac=None)                                # null: no rise cap
    assert entry.tranche_entry(tr(True, 3, close=10.0), 30.0, off, CB) is None


def test_default_rise_cap_is_50_percent():
    """The default (README section 9, analysis_2026/results_late_entry): +40% may join, +60% waits."""
    e = dict(cfgmod.DEFAULT_ENTRY)
    assert e["max_join_rise_frac"] == 0.50 and e["max_join_bars"] == 20
    assert entry.tranche_entry(tr(True, 5, close=10.0), 14.0, e, CB) is None                 # +40%
    assert entry.tranche_entry(tr(True, 5, close=10.0), 15.0, e, CB) is None                 # exactly +50%
    assert entry.tranche_entry(tr(True, 5, close=10.0), 16.0, e, CB) == (
        "up 60.0% since the green flip 2026-10-13 (max 50%): waiting for the next flip")
    assert "too late" in entry.tranche_entry(tr(True, 21, close=10.0), 14.0, e, CB)          # bars still apply
    no_fc = dict(tr(True, 5), flip_close=None)                                                 # cannot check: no buy
    assert entry.tranche_entry(no_fc, 14.0, e, CB) == "no flip close to check max_join_rise_frac against"


def test_entry_frac_is_per_tranche_and_capped_at_target():
    e = dict(cfgmod.DEFAULT_ENTRY)
    s = S("QQQ", tr(True, 35, 0.5, bar=EB), tr(True, 4, 0.5, 5, bar=EB))
    frac, notes = entry.entry_frac(s, e, EB)
    assert frac == 0.5 and notes == [f"tranche 1 green 35 bars, {WAIT}"]
    assert entry.entry_frac(s, dict(e, policy="join"), EB) == (1.0, [])
    assert entry.entry_frac(dict(s, target_frac=0.0, tranches=[]), e, EB) == (0.0, [])
    assert entry.entry_frac(dict(s, tranches=[]), e, EB)[0] == 0.0                         # no tranche data: no buy
    assert entry.newest_flip(s, e, EB) == "2026-10-12"                                     # the eligible tranche's


def test_effective_config_and_strategy_start_file():
    c = cfg(entry_={"policy": "join_recent", "max_join_bars": 10},
            assets=[dict(copy.deepcopy(SIX[0]), entry={"policy": "join"}), copy.deepcopy(SIX[1])])
    assert entry.effective(c["assets"][0], c)["policy"] == "join"
    assert entry.effective(c["assets"][1], c) == dict(cfgmod.DEFAULT_ENTRY, max_join_bars=10)
    assert entry.recorded_start() is None
    assert entry.record_start("2026-10-19") == "2026-10-19" == entry.record_start("2026-10-25")   # first one stays
    assert entry.start_for({"start_date": "2026-09-01"}, "2026-10-19", "2026-10-30") == "2026-09-01"
    assert entry.start_for({"start_date": None}, None, "2026-10-30") == "2026-10-30"


# ------------------------------------------------------------------ config validation

def example():
    return json.loads(cfgmod.EXAMPLE.read_text())


def test_example_config_uses_slots_and_join_recent():
    c = cfgmod.validate(example())
    assert c["allocation"] == {"method": "slots", "slot_frac": 0.10, "priority": "crypto_first", "favorites": [],
                               "class_max_frac": {"crypto": 0.60, "equity": 1.0}}
    assert c["allocation"]["slot_frac"] <= c["limits"]["max_asset_frac"]                    # 10 slots of 10%
    assert c["entry"] == {"policy": "join_recent", "max_join_bars": 20, "max_join_rise_frac": 0.50, "start_date": None}


def test_defaults_when_blocks_are_absent():
    raw = example()
    del raw["allocation"], raw["entry"]
    raw["limits"]["max_crypto_frac"] = 0.45
    c = cfgmod.validate(raw)
    assert c["allocation"]["method"] == "fixed" and c["allocation"]["class_max_frac"] == {"crypto": 0.45, "equity": 1.0}
    assert c["entry"] == {"policy": "join_recent", "max_join_bars": 20, "max_join_rise_frac": 0.50, "start_date": None}
    raw["entry"] = {"max_join_rise_frac": None}                                 # an explicit null turns the cap off
    assert cfgmod.validate(raw)["entry"]["max_join_rise_frac"] is None


def test_old_max_crypto_frac_values_still_load():
    raw = example()
    del raw["allocation"]
    for v, cap in (("0.6", 0.6), (1.5, 1.0), (0, 0.0)):                      # what older configs could hold
        raw["limits"]["max_crypto_frac"] = v
        assert cfgmod.validate(raw)["allocation"]["class_max_frac"]["crypto"] == cap
    for v in ("lots", -0.1, None):
        raw["limits"]["max_crypto_frac"] = v
        with pytest.raises(cfgmod.ConfigError, match="limits.max_crypto_frac"):
            cfgmod.validate(raw)
    raw["allocation"] = {"class_max_frac": {"crypto": 0.5}}                   # an explicit cap: not read
    assert cfgmod.validate(raw)["allocation"]["class_max_frac"]["crypto"] == 0.5


@pytest.mark.parametrize("block, value, match", [
    ("entry", {"policy": "late"}, "entry.policy"),
    ("entry", {"max_join_bars": -1}, "max_join_bars"),
    ("entry", {"max_join_bars": 2.5}, "max_join_bars"),
    ("entry", {"max_join_bars": True}, "max_join_bars"),
    ("entry", {"max_join_rise_frac": -0.1}, "max_join_rise_frac"),
    ("entry", {"max_join_rise_frac": "10%"}, "max_join_rise_frac"),
    ("entry", {"start_date": "2026-13-01"}, "start_date"),
    ("entry", {"start_date": "20261001"}, "start_date"),
    ("entry", {"start_date": 20261001}, "start_date"),
    ("entry", {"max_join_days": 20}, "unknown keys"),
    ("entry", "join", "must be an object"),
    ("allocation", {"method": "equal"}, "allocation.method"),
    ("allocation", {"priority": "random"}, "allocation.priority"),
    ("allocation", {"slot_frac": 0}, "slot_frac"),
    ("allocation", {"slot_frac": 1.5}, "slot_frac"),
    ("allocation", {"method": "slots", "slot_frac": 0.35}, "exceeds limits.max_asset_frac"),
    ("allocation", {"class_max_frac": {"bonds": 0.5}}, "class_max_frac"),
    ("allocation", {"class_max_frac": {"crypto": -0.1}}, "class_max_frac.crypto"),
    ("allocation", {"class_max_frac": {"crypto": 1.2}}, "class_max_frac.crypto"),
    ("allocation", {"class_max_frac": [0.6]}, "class_max_frac"),
    ("allocation", {"slots": 5}, "unknown keys"),
])
def test_bad_entry_and_allocation_values(block, value, match):
    raw = example()
    raw[block] = value if not isinstance(value, dict) else {**raw[block], **value}
    with pytest.raises(cfgmod.ConfigError, match=match):
        cfgmod.validate(raw)


def test_asset_entry_override_and_alloc_sum():
    raw = example()
    raw["assets"][0]["entry"] = {"policy": "fresh_only", "start_date": "2026-10-01"}
    assert cfgmod.validate(raw)["assets"][0]["entry"] == {"policy": "fresh_only", "start_date": "2026-10-01"}
    raw["assets"][0]["entry"] = {"policy": "soon"}
    with pytest.raises(cfgmod.ConfigError, match="ETH: entry.policy"):
        cfgmod.validate(raw)
    raw = example()
    for a in raw["assets"][:4]:
        a["enabled"], a["alloc_frac"] = True, 0.30                          # 1.2 of capital: fine in slots mode
    raw["assets"][1]["signal"]["symbol"] = "SOL-USD"
    assert cfgmod.validate(raw)["allocation"]["method"] == "slots"
    raw["allocation"]["method"] = "fixed"
    with pytest.raises(cfgmod.ConfigError, match="allocate 1.20"):
        cfgmod.validate(raw)
    raw["allocation"] = {"method": "fixed", "slot_frac": 0.5}                 # slot_frac unused in fixed: no cap check
    raw["assets"][0]["alloc_frac"] = raw["assets"][1]["alloc_frac"] = 0.1
    assert cfgmod.validate(raw)["allocation"]["slot_frac"] == 0.5


# ------------------------------------------------------------------ entry policy in the planner (fixed allocation)

def test_join_vs_join_recent_vs_fresh_only():
    old, new = S("ETH", tr(True, 35)), S("SOL", tr(True, 1))
    p = plan([old, new], cfg("ETH", "SOL", entry_={"policy": "join"}))
    assert set(bought(p)) == {"ETH", "SOL"}
    p = plan([old, new], cfg("ETH", "SOL"))                                   # default join_recent, 20 bars
    assert set(bought(p)) == {"SOL"} and why(p, "ETH") == f"green 35 bars, {WAIT}"
    c = cfg("ETH", "SOL", entry_={"policy": "fresh_only"})
    p = plan([old, new], c)                                                   # shadow, no recorded start: today
    assert bought(p) == {} and "before the strategy start 2026-10-19 (fresh_only)" in why(p, "SOL")
    assert "too late" in why(p, "ETH")
    p = plan([old, new], c, start="2026-10-17")                                # SOL flipped 10-17: fresh
    assert set(bought(p)) == {"SOL"}
    c = cfg("ETH", "SOL", entry_={"policy": "fresh_only", "start_date": "2026-10-10"})
    assert set(bought(plan([old, new], c, start="2026-10-17"))) == {"SOL"}     # start_date wins over the file
    c = cfg("ETH", "SOL", assets=[dict(copy.deepcopy(SIX[0]), entry={"policy": "join"}), copy.deepcopy(SIX[1])])
    assert set(bought(plan([old, new], c))) == {"ETH", "SOL"}                  # per-asset override


def test_rise_cap_in_the_plan():
    s = S("SOL", tr(True, 3, close=10.0), close=11.5)
    assert "up 15.0% since the green flip" in why(plan([s], cfg("SOL", entry_={"max_join_rise_frac": 0.10})), "SOL")
    assert set(bought(plan([s], cfg("SOL", entry_={"max_join_rise_frac": 0.20})))) == {"SOL"}
    up40, up60 = S("ETH", tr(True, 3, close=10.0), close=14.0), S("SOL", tr(True, 3, close=10.0), close=16.0)
    p = plan([up40, up60], cfg("ETH", "SOL"))                                   # default cap 0.50
    assert set(bought(p)) == {"ETH"} and "up 60.0% since the green flip" in why(p, "SOL")
    p = plan([up40, up60], cfg("ETH", "SOL", entry_={"max_join_rise_frac": None}))
    assert set(bought(p)) == {"ETH", "SOL"}
    p = plan([up60], cfg("SOL"), eq={"SOLQ": pos(75)})                          # half held: kept, not topped up
    assert sold(p) == {} and bought(p) == {} and "up 60.0% since the green flip" in why(p, "SOL")


def test_split_buys_only_the_fresh_tranche():
    s = S("QQQ", tr(True, 35, 0.5, bar=EB), tr(True, 3, 0.5, 5, bar=EB))
    p = plan([s], cfg("QQQ"))
    (o,) = p["orders"]
    assert o["params"]["side"] == "buy" and o["params"]["quantity"] == "74"   # 0.15 x 10000 x 0.5 / 10.06
    assert o["reason"].startswith("target 0.00 -> 0.50 (tranche 1: green; tranche 2: green, 5/5 closes above")
    assert f"tranche 1 green 35 bars, {WAIT}" in o["reason"]
    t2_buy = [placed("QQQ", "2026-10-14T14:00:00Z")]                          # after tranche 2's flip (10-13)
    p = plan([s], cfg("QQQ"), eq={"QQQ": pos(75)}, journal=t2_buy)            # the fresh half is held: no more buys
    assert p["orders"] == [] and "tranche 1 green 35 bars" in why(p, "QQQ")


@pytest.mark.parametrize("alloc, half, buy", [(None, 75, 74.0), (slots(0.25), 125, 124.0)])
def test_held_old_half_adds_the_fresh_half(alloc, half, buy):
    c = cfg("QQQ", alloc=alloc)
    late_t2 = S("QQQ", tr(True, 35, 0.5, bar=EB), tr(True, 0, 0.5, 5, bar=EB))   # holds tranche 1's (old) half
    p = plan([late_t2], c, eq={"QQQ": pos(half)})
    assert bought(p) == {"QQQ": buy} and "too late" not in p["orders"][0]["reason"]
    t2_buy = [placed("QQQ", "2026-10-16T14:00:00Z"), placed("QQQ", "2026-10-17T14:00:00Z")]
    p = plan([late_t2], c, eq={"QQQ": pos(half)}, journal=t2_buy[1:])          # bought after tranche 2's flip: held
    assert bought(p) == {} and "tranche 1 green 35 bars" in why(p, "QQQ")
    assert bought(plan([late_t2], c, eq={"QQQ": pos(half)}, journal=t2_buy[:1])) == {"QQQ": buy}   # before it
    whipsaw = S("QQQ", tr(True, 0, 0.5, bar=EB), tr(True, 31, 0.5, 5, bar=EB))   # tranche 1 re-flipped green
    p = plan([whipsaw], c, eq={"QQQ": pos(half)})                              # holds tranche 2's (old) half
    assert bought(p) == {"QQQ": buy} and p["skipped"] == []
    assert p["orders"][0]["reason"].startswith("target 0.50 -> 1.00 (tranche 1: green; tranche 2: green")


def test_old_position_is_held_not_sold():
    s = S("QQQ", tr(True, 35, 0.5, bar=EB), tr(True, 30, 0.5, 5, bar=EB))   # entry_tf 0, full_tf 1
    for qty in (40, 75, 150, 180):                                            # 0.27 .. 1.2 of the allocation
        p = plan([s], cfg("QQQ"), eq={"QQQ": pos(qty)})
        assert p["orders"] == [], qty
    p = plan([s], cfg("QQQ"), eq={"QQQ": pos(200)})                           # 1.33: above the band, trims to 1.00
    assert sold(p) == {"QQQ": 50.0}
    half = S("QQQ", tr(True, 35, 0.5, bar=EB), tr(False, w=0.5, n=5))        # tranche 2 red: full_tf 0.5
    assert sold(plan([half], cfg("QQQ"), eq={"QQQ": pos(150)})) == {"QQQ": 75.0}


def test_red_is_a_full_exit_under_every_policy():
    red = S("ETH", tr(False))
    for pol in ("join", "join_recent", "fresh_only"):
        for alloc in (None, slots()):
            p = plan([red], cfg("ETH", entry_={"policy": pol}, alloc=alloc), eq={"ETHA": pos(150)})
            assert sold(p) == {"ETH": 150.0} and "full exit" in p["orders"][0]["reason"], (pol, alloc)


def test_flags_are_unaffected_by_the_entry_policy():
    old, red, fresh = S("ETH", tr(True, 35)), S("SOL", tr(False)), S("SPY")
    eq = {"ETHA": pos(150), "SOLQ": pos(100)}
    for alloc in (None, slots()):
        c = cfg("ETH", "SOL", "SPY", alloc=alloc)
        p = plan([old, red, fresh], c, eq=eq, flags={"FLATTEN": ""})
        assert sold(p) == {"ETH": 150.0, "SOL": 100.0} and bought(p) == {}
        p = plan([old, red, fresh], c, eq=eq, flags={"STOP": "x"})
        assert p["orders"] == []
        p = plan([old, red, fresh], c, eq=eq, flags={"BLOCK_BUYS": "reconcile"})
        assert sold(p) == {"SOL": 100.0} and bought(p) == {} and "BLOCK_BUYS" in why(p, "SPY")


def test_strategy_start_recorded_on_the_first_live_plan(tmp_path):
    c = cfg("SOL", entry_={"policy": "fresh_only"})
    p = planner.make_plan({"date": "2026-10-19", "assets": [S("SOL")]},
                          snap(quotes=TEN), c, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=owned(snap()))
    planner.write_plan(p)                                                     # shadow: nothing recorded
    assert entry.recorded_start() is None and p["orders"] == []
    live = cfg("SOL", entry_={"policy": "fresh_only"}, live=True)
    p = planner.make_plan({"date": "2026-10-19", "assets": [S("SOL")]},
                          snap(quotes=TEN), live, NOW, 1, {}, placed_today_usd=0.0, journal=[], sleeve=owned(snap()))
    assert p["strategy_start"] == "2026-10-19" and p["orders"] == []          # the flip on bar 10-18 is pre-existing
    planner.write_plan(p)
    assert json.loads(cfgmod.paths()["strategy_start"].read_text())["date"] == "2026-10-19"
    nxt = NOW + timedelta(days=1)                                             # Tuesday: crypto bar 10-19
    for flip, buys in (("2026-10-19", True), ("2026-10-18", False)):
        s = S("SOL", tr(True, 0 if buys else 1, flip=flip, bar="2026-10-19"), bar="2026-10-19")
        q = snap(nxt, quotes={"SOLQ": quote(9.99, 10.01, nxt)})
        p = planner.make_plan({"date": "2026-10-20", "assets": [s]}, q, live, nxt, 1, {}, placed_today_usd=0.0,
                              journal=[], sleeve=owned(q))                    # reads strategy_start.json
        assert bool(p["orders"]) is buys and p["strategy_start"] == "2026-10-19", flip
    planner.write_plan(p)
    assert entry.recorded_start() == "2026-10-19"                             # never moves


def test_plan_records_the_start_it_used():
    assets = [dict(copy.deepcopy(SIX[1]), entry={"start_date": "2026-10-15"}), copy.deepcopy(SIX[3])]
    c = cfg(assets=assets, entry_={"policy": "fresh_only", "start_date": "2026-10-01"}, live=True)
    p = plan([S("SOL", tr(True, 8)), S("SPY", tr(True, 3, bar=EB))], c)       # flips 10-10 and 10-13
    assert p["strategy_start"] == "2026-10-01" and p["strategy_start_assets"] == {"SOL": "2026-10-15"}
    assert set(bought(p)) == {"SPY"} and "before the strategy start 2026-10-15" in why(p, "SOL")
    planner.write_plan(p)
    assert entry.recorded_start() == "2026-10-19"                             # still the first live plan's date


# ------------------------------------------------------------------ slots

def six(**flips):
    """All six green and fresh; `flips` sets a flip date per asset (newest first wins a slot)."""
    out = []
    for a in SIX:
        bar = CB if a["class"] == "crypto" else EB
        day = flips.get(a["name"], bar)
        bars = (date.fromisoformat(bar) - date.fromisoformat(day)).days
        if a["mode"] == "split":
            out.append(S(a["name"], tr(True, bars, 0.5, flip=day, bar=bar), tr(True, bars, 0.5, 5, flip=day, bar=bar)))
        else:
            out.append(S(a["name"], tr(True, bars, flip=day, bar=bar)))
    return out


FLIPS = dict(ETH="2026-10-10", SOL="2026-10-17", BTC="2026-10-14", SPY="2026-10-16", QQQ="2026-10-09",
             IWM="2026-10-13")


@pytest.mark.parametrize("priority, winners", [
    ("crypto_first", ["SOL", "BTC", "ETH", "SPY"]),
    ("equity_first", ["SPY", "IWM", "QQQ", "SOL"]),
    ("newest_flip", ["SOL", "SPY", "BTC", "IWM"]),
    ("config_order", ["ETH", "SOL", "BTC", "SPY"]),
])
def test_slot_priority_when_room_is_short(priority, winners):
    p = plan(six(**FLIPS), cfg(alloc=slots(0.25, priority)))                  # 4 slots of $2500 for 6 candidates
    al = p["allocation"]
    assert [x["asset"] for x in al["new"]] == winners and al["held"] == []
    assert set(bought(p)) == set(winners) and all(v == 248.0 for v in bought(p).values())    # 2500 / 10.06
    for n in set(CLS) - set(winners):
        assert why(p, n).startswith("no free slot: $0.00 of capital is free (< half a slot, $1250.00; "
                                    f"{priority})")
    first = next(o for o in p["orders"] if o["asset"] == winners[0])
    assert f"new slot $2500.00 (#1 by {priority})" in first["reason"]
    assert [o["asset"] for o in p["orders"]] == winners                       # buys go in priority order


def test_ties_keep_config_order():
    p = plan(six(), cfg(alloc=slots(0.25, "newest_flip")))                    # every crypto flip on 10-18
    assert [x["asset"] for x in p["allocation"]["new"]] == ["ETH", "SOL", "BTC", "SPY"]


def test_holdings_keep_their_slot_and_are_never_trimmed():
    eq = {"ETHA": pos(300), "IWM": pos(240)}                                  # $3000 (above the slot) and $2400
    p = plan(six(ETH="2026-08-01", IWM="2026-08-01"), cfg(alloc=slots(0.25)), eq=eq)   # their runs are old
    al = p["allocation"]
    assert al["held"] == ["ETH", "IWM"] and [x["asset"] for x in al["new"]] == ["SOL", "BTC"]
    assert sold(p) == {} and set(bought(p)) == {"SOL", "BTC"}                 # room 10000 - 3000 - 2500
    assert "no free slot" in why(p, "SPY") and "no free slot" in why(p, "QQQ")
    capped = cfg(alloc=slots(0.25, crypto=0.40))                              # holdings over a class cap stay put
    p = plan(six(), capped, eq={"ETHA": pos(250), "SOLQ": pos(250)})
    assert sold(p) == {} and "BTC" not in bought(p)
    assert why(p, "BTC").startswith("no free slot: the crypto class cap leaves $0.00")
    assert set(bought(p)) == {"SPY", "QQQ"}


def test_held_split_position_adds_its_second_tranche():
    s = S("QQQ", tr(True, 9, 0.5, bar=EB), tr(True, 2, 0.5, 5, bar=EB))
    p = plan([s] + [S(n) for n in ("ETH", "SOL", "BTC")], cfg(alloc=slots(0.25)), eq={"QQQ": pos(124)})
    assert bought(p)["QQQ"] == 125.0 and "held slot $2500.00" in next(o["reason"] for o in p["orders"]
                                                                      if o["asset"] == "QQQ")
    assert p["allocation"]["held"] == ["QQQ"] and len(p["allocation"]["new"]) == 3


def test_partial_slot_only_with_half_a_slot_left():
    p = plan(six(**FLIPS), cfg(alloc=slots(0.30)))                            # 3 x 3000; $1000 < half a slot
    assert [x["asset"] for x in p["allocation"]["new"]] == ["SOL", "BTC", "ETH"]
    assert why(p, "SPY").startswith("no free slot: $1000.00 of capital is free (< half a slot, $1500.00")
    p = plan(six(**FLIPS), cfg(alloc=slots(0.40), max_asset_frac=0.40))       # 2 x 4000; $2000 = half a slot
    new = p["allocation"]["new"]
    assert [(x["asset"], x["usd"], x["partial"]) for x in new] == [("SOL", 4000.0, False), ("BTC", 4000.0, False),
                                                                   ("ETH", 2000.0, True)]
    assert bought(p)["ETH"] == 198.0                                          # 2000 / 10.06
    assert "partial slot $2000.00 of $4000.00" in next(o["reason"] for o in p["orders"] if o["asset"] == "ETH")
    assert "SPY" in [x["asset"] for x in p["allocation"]["waiting"]]


def test_partial_slot_holding_tops_up_only_when_capital_frees_up():
    eq = {"SOLQ": pos(400), "BTCQ": pos(400), "ETHA": pos(200)}               # 4000 + 4000 + a 2000 partial slot
    c = cfg("ETH", "SOL", "BTC", alloc=slots(0.40), max_asset_frac=0.40)
    p = plan([S("ETH"), S("SOL"), S("BTC")], c, eq=eq, bp=50000.0)            # the account has more cash
    assert bought(p) == {} and why(p, "ETH").startswith("no free capital")
    p = plan([S("ETH"), S("SOL", tr(False)), S("BTC")], c, eq=eq, bp=50000.0)  # SOL exits: room frees once sold
    assert sold(p) == {"SOL": 400.0} and bought(p) == {} and why(p, "ETH").startswith("no free capital")
    del eq["SOLQ"]
    p = plan([S("ETH"), S("SOL", tr(False)), S("BTC")], c, eq=eq, bp=50000.0)  # the next plan: ETH tops up
    assert bought(p) == {"ETH": 198.0}


def test_slot_entry_buys_only_the_fresh_tranche_and_too_late_takes_no_slot():
    qqq = S("QQQ", tr(True, 35, 0.5, bar=EB), tr(True, 3, 0.5, 5, bar=EB))
    p = plan([S("ETH", tr(True, 40)), qqq, S("SPY")], cfg("ETH", "QQQ", "SPY", alloc=slots(0.25)))
    assert [x["asset"] for x in p["allocation"]["new"]] == ["SPY", "QQQ"]     # SPY flipped later (on 10-16)
    assert bought(p) == {"QQQ": 124.0, "SPY": 248.0}                          # QQQ: half of its 2500 slot
    assert why(p, "ETH") == f"green 40 bars, {WAIT}"


def test_class_caps_in_slots_and_fixed():
    p = plan(six(), cfg(alloc=slots(0.20, crypto=0.40)))                      # 2 crypto slots, then 3 equity
    assert [x["asset"] for x in p["allocation"]["new"]] == ["ETH", "SOL", "SPY", "QQQ", "IWM"]
    assert why(p, "BTC").startswith("no free slot: the crypto class cap leaves $0.00")
    fixed = {"method": "fixed", "class_max_frac": {"crypto": 0.20, "equity": 0.30}}
    p = plan([S("ETH"), S("SOL"), S("SPY"), S("IWM")], cfg("ETH", "SOL", "SPY", "IWM", alloc=fixed))
    b = bought(p)                                                             # 0.15 each: crypto x0.67, equity x1.00
    assert b == {"ETH": 99.0, "SOL": 99.0, "SPY": 149.0, "IWM": 149.0}
    assert any("crypto targets $3000.00 scaled to the crypto class cap $2000.00" in w for w in p["warnings"])
    assert "crypto cap x0.67" in p["orders"][0]["reason"] and p["allocation"]["method"] == "fixed"
    p = plan([S("SPY"), S("IWM"), S("QQQ")], cfg("SPY", "IWM", "QQQ", alloc={"class_max_frac": {"equity": 0.30}}))
    assert sum(bought(p).values()) == 297.0                                   # 3 x 0.15 scaled to 0.30


def test_fixed_class_cap_ignores_green_runs_it_will_not_buy():
    assets = [dict(copy.deepcopy(a), alloc_frac=0.30) for a in SIX[:3]]
    c = cfg(assets=assets, alloc={"method": "fixed", "class_max_frac": {"crypto": 0.60}})
    eq = {"ETHA": pos(300), "SOLQ": pos(300)}                                 # $3000 each: at the crypto cap
    held = [S("ETH", tr(True, 50)), S("SOL", tr(True, 50))]
    for btc in (tr(False), tr(True, 40)):                                     # red, or green too late to join
        p = plan(held + [S("BTC", btc)], c, eq=eq)
        assert p["orders"] == [] and not any("scaled" in w for w in p["warnings"]), btc
    p = plan(held + [S("BTC")], c, eq=eq)                                     # a fresh BTC flip: all three scaled
    assert sold(p) == {"ETH": 100.0, "SOL": 100.0} and bought(p) == {"BTC": 198.0}
    assert any("crypto targets $9000.00 scaled to the crypto class cap $6000.00" in w for w in p["warnings"])


def test_skipped_holding_keeps_its_slot():
    p = plan([S("ETH", errors=["bad data"])] + six()[1:], cfg(alloc=slots(0.25)), eq={"ETHA": pos(250)})
    assert "ETH" in p["allocation"]["held"] and len(p["allocation"]["new"]) == 3


def test_skipped_holding_counts_at_its_value():
    sigs = [S("ETH", errors=["bad data"]), S("SOL"), S("BTC"), S("SPY")]
    p = plan(sigs, cfg("ETH", "SOL", "BTC", "SPY", alloc=slots(0.25)), eq={"ETHA": pos(310)}, bp=50000.0,
             total=20000.0)                                                   # $3100 held, capital $10000
    assert [(x["asset"], x["usd"]) for x in p["allocation"]["new"]] == [("SOL", 2500.0), ("BTC", 2500.0),
                                                                         ("SPY", 1900.0)]
    assert 3100 + sum(o["notional_usd"] for o in p["orders"]) <= p["capital_usd"]


def test_a_partial_slot_never_takes_a_holdings_second_half():
    c = cfg("ETH", "SPY", "QQQ", "IWM", alloc=slots(0.28))                    # ETH is first in config order
    j = [placed(s, "2026-10-07T14:00:00Z") for s in ("SPY", "QQQ", "IWM")] + [placed("ETHA", "2026-10-15T14:00:00Z")]
    eq = {"QQQ": pos(140), "SPY": pos(280), "IWM": pos(280), "ETHA": pos(159)}   # ETH came last: a $1600 partial
    old = [S("ETH", tr(True, 4)), S("SPY", tr(True, 10, bar=EB)), S("IWM", tr(True, 10, bar=EB))]
    p = plan(old + [S("QQQ", tr(True, 10, 0.5, bar=EB), tr(False, w=0.5, n=5))], c, eq=eq, journal=j, bp=50000.0)
    assert p["orders"] == [] and why(p, "ETH").startswith("no free capital: held slot $2800.00, up to $1600.00")
    p = plan(old + [S("QQQ", tr(True, 10, 0.5, bar=EB), tr(True, 0, 0.5, 5, bar=EB))], c, eq=eq, journal=j,
             bp=50000.0)                                                      # QQQ's 5-close half flips
    assert bought(p) == {"QQQ": 139.0}                                        # its whole $1400 half


def test_an_exit_frees_its_slot_only_once_sold():
    c = cfg("ETH", "SOL", "BTC", "SPY", "IWM", alloc=slots(0.25))
    sigs = [S("ETH", tr(False)), S("SOL", tr(True, 5)), S("BTC", tr(True, 5)), S("SPY", tr(True, 5, bar=EB)), S("IWM")]
    eq = {"ETHA": pos(250, sellable=0), "SOLQ": pos(250), "BTCQ": pos(250), "SPY": pos(250)}
    p = plan(sigs, c, eq=eq, bp=50000.0, total=20000.0)                       # the exit cannot be placed now
    assert p["orders"] == [] and "nothing sellable" in why(p, "ETH")
    assert why(p, "IWM").startswith("no free slot") and why(p, "IWM").endswith("once the positions show it sold")
    eq["ETHA"] = pos(250)
    p = plan(sigs, c, eq=eq, bp=50000.0, total=20000.0)                       # placed, but not filled yet
    assert sold(p) == {"ETH": 250.0} and bought(p) == {}
    del eq["ETHA"]
    assert bought(plan(sigs, c, eq=eq, bp=50000.0, total=20000.0)) == {"IWM": 248.0}


def test_an_exit_held_back_by_an_open_order_keeps_the_class_cap():
    c = cfg("ETH", "SOL", "BTC", alloc=slots(0.25, crypto=0.50))
    sell = {"id": "o1", "ref_id": None, "symbol": "ETHA", "side": "sell", "state": "queued", "qty": 250, "filled": 0,
            "price": 9.5, "kind": "equity", "agent_initiated": True}          # yesterday's exit, still open
    p = plan([S("ETH", tr(False)), S("SOL"), S("BTC")], c, eq={"ETHA": pos(250)}, bp=50000.0, total=20000.0,
             open_orders=[sell])
    assert [x["params"]["order_id"] for x in p["cancels"]] == ["o1"] and sold(p) == {}     # exit held back
    assert bought(p) == {"SOL": 248.0} and "the crypto class cap leaves $0.00" in why(p, "BTC")
    assert 2500 + sum(o["notional_usd"] for o in p["orders"]) <= 0.50 * p["capital_usd"]


def test_dust_is_not_a_holding():
    c = cfg("ETH", "SOL", "BTC", alloc=slots(0.30, crypto=0.60))
    sigs = [S("ETH", tr(True, 25)), S("SOL"), S("BTC", tr(True, 1))]
    p = plan(sigs, c, eq={"ETHA": pos(0.0004)})                               # $0.004 left after an exit
    assert p["allocation"]["held"] == [] and [x["asset"] for x in p["allocation"]["new"]] == ["SOL", "BTC"]
    assert bought(p) == {"SOL": 298.0, "BTC": 298.0} and "too late" in why(p, "ETH")


def test_block_buys_hands_out_no_slots():
    p = plan([S("SOL"), S("SPY")], cfg("SOL", "SPY", alloc=slots(0.25)), flags={"BLOCK_BUYS": "reconcile"})
    assert p["orders"] == [] and p["allocation"]["new"] == [] and p["allocation"]["blocked"] == "BLOCK_BUYS"
    assert why(p, "SOL") == "BLOCK_BUYS: buys blocked (reconcile)"
    assert "held -; new - (BLOCK_BUYS); waiting -" in planner.format_plan(p)


def test_wash_sale_symbol_takes_no_slot():
    c = cfg(alloc=slots(0.25))
    c["wash_sale_block_symbols"] = ["solq"]
    p = plan(six(**FLIPS), c)
    assert "SOL" not in [x["asset"] for x in p["allocation"]["new"]] and "wash_sale" in why(p, "SOL")
    assert [x["asset"] for x in p["allocation"]["new"]] == ["BTC", "ETH", "SPY", "IWM"]


def test_plan_summary_shows_slot_decisions():
    p = plan(six(**FLIPS), cfg(alloc=slots(0.25)), eq={"ETHA": pos(250)})
    text = planner.format_plan(p)
    assert "SLOTS $2500.00 each (0.25 x capital, crypto_first): held ETH; new SOL $2500.00, BTC $2500.00, " \
           "SPY $2500.00; waiting IWM, QQQ" in text
    assert "SKIPPED: QQQ: no free slot" in text


# ------------------------------------------------------------------ signals: flip ages, entry_frac, digest

def bars(dip, end=CB, n=600):
    return trend(pd.date_range(end=end, periods=n, freq="D"), 100.0, dip=dip)


def test_signal_flip_fields_match_the_indicator(monkeypatch):
    df = bars(30)
    monkeypatch.setattr(feeds, "get_bars", lambda a, c, now=None, inbox=None: df)
    c = cfg(assets=[A("ETH", "crypto", "ETHA", "split")])
    a = sg.compute_signals(c, NOW)["assets"][0]
    tt = tranche_targets(df, [(0.5, 1, 1), (0.5, 5, 5)])
    for k, t in enumerate(a["tranches"]):
        j = int(np.flatnonzero(tt[f"flip{k}"].to_numpy() == 1)[-1])
        assert t["last_green_flip_date"] == df.index[j].date().isoformat()
        assert t["bars_since_green_flip"] == len(df) - 1 - j and t["flip_close"] == pytest.approx(df["close"].iloc[j])
    ages = [t["bars_since_green_flip"] for t in a["tranches"]]
    assert ages[0] > 20 >= ages[1]                                            # the N=5 tranche flipped later
    assert a["entry_policy"] == "join_recent" and a["target_frac"] == 1.0 and a["entry_frac"] == 0.5
    text = sg.format_digest({**sg.compute_signals(c, NOW)})
    assert f"entry join_recent: tranche 1 green {ages[0]} bars, {WAIT}" in text


def test_digest_alloc_is_the_slot_in_slots_mode(monkeypatch):
    monkeypatch.setattr(feeds, "get_bars", lambda a, c, now=None, inbox=None: bars(30))
    a = dict(A("ETH", "crypto", "ETHA"), alloc_frac=0.25)
    for alloc, slot, shown in ((None, None, "25%"), (slots(0.20), 0.20, "20%")):
        s = sg.compute_signals(cfg(assets=[copy.deepcopy(a)], alloc=alloc), NOW)
        row = next(x for x in sg.format_digest(s).splitlines() if x.startswith("ETH "))
        assert s["assets"][0]["slot_frac"] == slot and f" {shown}  " in row, row


def test_signal_without_a_flip_in_history_is_not_recent(monkeypatch):
    monkeypatch.setattr(feeds, "get_bars", lambda a, c, now=None, inbox=None: bars(None))
    a = sg.compute_signals(cfg("ETH"), NOW)["assets"][0]
    assert a["tranches"][0]["bars_since_green_flip"] is None and a["entry_frac"] == 0.0
    assert a["entry_notes"] == [f"green with no flip in the available history, {WAIT}"]
    a = sg.compute_signals(cfg("ETH", entry_={"policy": "join"}), NOW)["assets"][0]
    assert a["entry_frac"] == 1.0 and a["entry_notes"] == []


def test_fresh_only_signal_uses_the_recorded_start(monkeypatch):
    df = bars(12)                                                             # both tranches flipped < 12 bars ago
    monkeypatch.setattr(feeds, "get_bars", lambda a, c, now=None, inbox=None: df)
    c = cfg(assets=[A("ETH", "crypto", "ETHA", "split")], entry_={"policy": "fresh_only"})
    a = sg.compute_signals(c, NOW)["assets"][0]
    assert a["entry_frac"] == 0.0 and "before the strategy start 2026-10-19" in a["entry_notes"][0]
    entry.record_start("2026-10-01")
    s = sg.compute_signals(c, NOW)
    assert s["strategy_start"] == "2026-10-01" and s["assets"][0]["entry_frac"] == 1.0


def test_tv_export_flip_fields(tmp_path):
    f = tmp_path / "COINBASE_ETHUSD_1D_x.csv"
    tv_csv(f, date(2026, 10, 18), final=(-1, 0), n=50)                        # bull all along: no flip at all
    a = A("ETH-TV", "crypto", "ETHA", "split")
    a["signal"] = {"source": "tv_export", "path": str(f)}
    r = sg.compute_signals(cfg(assets=[a]), NOW)["assets"][0]
    assert r["errors"] == [] and r["target_frac"] == 1.0 and r["entry_frac"] == 0.0
    assert [t["bars_since_green_flip"] for t in r["tranches"]] == [None, None]
    raw = pd.read_csv(f)                                                      # bear until row 30, then the flip
    raw.loc[:29, ["Direction", "ConfirmCount", "close"]] = [1, 0, 90.0]
    raw.loc[30:34, "Direction"], raw.loc[30:34, "ConfirmCount"], raw.loc[30:34, "close"] = 1, [1, 2, 3, 4, 5], 105.0
    raw.loc[35:48, ["Direction", "ConfirmCount", "close"]] = [-1, 0, 110.0]
    raw.to_csv(f, index=False)
    import os
    os.utime(f, (NOW.timestamp(), NOW.timestamp()))
    r = sg.compute_signals(cfg(assets=[a]), NOW)["assets"][0]
    t1, t2 = r["tranches"]
    assert (t1["bars_since_green_flip"], t1["flip_close"]) == (18, 105.0)    # 48 - 30: the first close above
    assert (t2["bars_since_green_flip"], t2["flip_close"]) == (14, 105.0)    # ConfirmCount reached 5 on row 34
    assert t1["last_green_flip_date"] == (date(2026, 10, 18) - timedelta(days=18)).isoformat()
    assert r["entry_frac"] == 1.0
    a["entry"] = {"max_join_bars": 15}
    r = sg.compute_signals(cfg(assets=[a]), NOW)["assets"][0]
    assert r["entry_frac"] == 0.5 and r["entry_notes"] == [f"tranche 1 green 18 bars, too late to join (max 15): "
                                                           "waiting for the next flip"]
