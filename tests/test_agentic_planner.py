"""Tests for agentic/planner.py: sizing, order construction, caps, flags, ref_ids, cancels. Synthetic data only."""
import copy
import json
import sys
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentic import config as cfgmod  # noqa: E402
from agentic import ledger, planner  # noqa: E402
from agentic import snapshot as sn  # noqa: E402
from tests.test_agentic_snapshot import write_inbox  # noqa: E402

UTC = timezone.utc
ACCT = "TESTACCT01"          # synthetic, as in test_agentic_snapshot
RHS = "100000001"
NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)          # Monday 11:00 ET, market open
PREOPEN = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)      # Monday 09:00 ET, market closed

# Parameter names of the official input schemas (tools/list capture 2026-10-12).
OFFICIAL = {
    "place_equity_order": {"account_number", "symbol", "side", "type", "quantity", "dollar_amount", "limit_price",
                           "stop_price", "time_in_force", "market_hours", "tax_lots", "ref_id"},
    "place_crypto_order": {"rhs_account_number", "symbol", "side", "type", "quantity", "dollar_amount", "limit_price",
                           "stop_price", "time_in_force", "tax_lots", "ref_id"},
    "review_equity_order": {"account_number", "symbol", "side", "type", "quantity", "dollar_amount", "limit_price",
                            "stop_price", "time_in_force", "market_hours", "tax_lots"},
    "preview_crypto_order": {"rhs_account_number", "symbol", "side", "type", "quantity", "dollar_amount", "limit_price",
                             "stop_price", "time_in_force", "tax_lots"},
    "cancel_equity_order": {"account_number", "order_id"},
    "cancel_crypto_order": {"rhs_account_number", "order_id"},
}
REQUIRED = {"place_equity_order": {"account_number", "symbol", "side", "type"},
            "place_crypto_order": {"rhs_account_number", "symbol", "side", "type"}}

ASSETS = {
    "ETH": {"name": "ETH", "class": "crypto", "alloc_frac": 0.25, "mode": "split",
            "signal": {"source": "computed", "feed": "coinbase", "symbol": "ETH-USD"},
            "vehicle": {"type": "equity", "symbol": "ETHA", "fractional": True}},
    "SOL": {"name": "SOL", "class": "crypto", "alloc_frac": 0.10, "mode": "immediate",
            "signal": {"source": "computed", "feed": "coinbase", "symbol": "SOL-USD"},
            "vehicle": {"type": "crypto", "symbol": "SOL"}},
    "SPY": {"name": "SPY", "class": "equity", "alloc_frac": 0.20, "mode": "split",
            "signal": {"source": "computed", "feed": "robinhood", "symbol": "SPY"},
            "vehicle": {"type": "equity", "symbol": "SPY", "fractional": True}},
    "ETH-TV": {"name": "ETH-TV", "class": "crypto", "alloc_frac": 0.25, "mode": "split",
               "signal": {"source": "tv_export", "path": "private/tv_exports/x*.csv"},
               "vehicle": {"type": "equity", "symbol": "ETHA", "fractional": True}},
}


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(tmp_path / "state"))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_cfg(*names, account=ACCT, **limits):
    assets = [dict(copy.deepcopy(ASSETS[n]), enabled=True) for n in names]
    lim = {"max_order_usd": 5000, "max_day_usd": 20000, **limits}
    return cfgmod.validate({"account": {"account_number": account, "rhs_account_number": RHS},
                            "capital": {"max_usd": 10000}, "limits": lim, "assets": assets})


def quote(bid, ask, now=NOW, age=1.0, last=None, kind="equity"):
    return {"bid": bid, "ask": ask, "last": round((bid + ask) / 2, 4) if last is None else last,
            "ts": iso(now - timedelta(minutes=age)), "captured_at": iso(now), "kind": kind, "problem": None}


def pos(qty, sellable=None, avg=22.0):
    return {"qty": qty, "sellable": qty if sellable is None else sellable, "avg_buy_price": avg}


SOL_PAIR = {"SOL-USD": {"min_order_size": "0.000001", "asset_increment": "0.000001", "quote_increment": "0.01",
                        "tradability": "tradable"}}


def snap(now=NOW, total=10000.0, bp=10000.0, cbp=None, eq=None, cr=None, quotes=None, open_orders=(), orders=(),
         pairs=None, errors=(), account=ACCT):
    q = {"ETHA": quote(24.95, 25.00, now), "SPY": quote(600.00, 600.50, now),
         "SOL-USD": quote(150.00, 150.50, now, kind="crypto")}
    q.update(quotes or {})
    return dict(as_of=iso(now - timedelta(minutes=2)), total_value=total, cash=bp, buying_power=bp,
                crypto_buying_power=bp if cbp is None else cbp, equity_positions=eq or {}, crypto_positions=cr or {},
                quotes=q, open_orders=list(open_orders), orders=list(orders) + list(open_orders),
                pairs=SOL_PAIR if pairs is None else pairs, account_number=account, rhs_account_number=RHS,
                errors=list(errors), warnings=[])


def owned(s, **override):
    """A sleeve status that owns every captured position and sees no mismatch (the default in these tests)."""
    sl = {"equity": {k: v["qty"] for k, v in s["equity_positions"].items()},
          "crypto": {k: v["qty"] for k, v in s["crypto_positions"].items()}}
    for k, v in override.items():
        sl["crypto" if k in s["crypto_positions"] else "equity"][k] = v
    return {"baseline": True, "sleeve": sl, "mismatches": []}


def fresh(green, bar, w=1.0, n=1, bars=0, close=100.0):
    """A tranche as signals.py writes it; a green one flipped `bars` bars before the signal bar."""
    return {"weight": w, "n_entry": n, "n_exit": n, "green": green, "pending": 0,
            "last_green_flip_date": bar if green else None, "bars_since_green_flip": bars if green else None,
            "flip_close": close if green else None}


def sig(name, tf, errors=(), bar=None, tranches=None, close=100.0):
    """A signal record; without `tranches`, ones consistent with tf whose green flips are on the signal bar (fresh,
    so the default entry policy join_recent lets them be bought)."""
    cls = ASSETS[name]["class"]
    bar = bar or ("2026-10-18" if cls == "crypto" else "2026-10-16")
    if tranches is None:
        ws = [(1.0, 1)] if ASSETS[name]["mode"] == "immediate" else [(0.5, 1), (0.5, 5)]
        tranches = [fresh(sum(w for w, _ in ws[:k + 1]) <= tf + 1e-9, bar, w, n) for k, (w, n) in enumerate(ws)]
    return {"name": name, "class": cls, "target_frac": tf, "prev_target_frac": None, "bar_date": bar,
            "close": close, "tranches": tranches, "errors": list(errors), "warnings": []}


def signals(*s):
    return {"date": "2026-10-19", "generated_at": "2026-10-19T01:00:00Z", "assets": list(s)}


def run(sigs, s, cfg, now=NOW, attempt=1, flags=None, placed=0.0, journal=None, sleeve=None):
    p = planner.make_plan(signals(*sigs), s, cfg, now, attempt, {} if flags is None else flags,
                          placed_today_usd=placed, journal=[] if journal is None else journal,
                          sleeve=owned(s) if sleeve is None else sleeve)
    check_schema(p)
    return p


def check_schema(p):
    json.dumps(p)
    for o in p["orders"]:
        assert set(o["params"]) <= OFFICIAL[o["tool"]] and REQUIRED[o["tool"]] <= set(o["params"])
        assert all(isinstance(v, str) for v in o["params"].values())
        assert set(o["preview_params"]) <= OFFICIAL[o["preview_tool"]]
        assert o["preview_params"] == {k: v for k, v in o["params"].items() if k != "ref_id"}
        acct_key = "account_number" if o["tool"] == "place_equity_order" else "rhs_account_number"
        assert o["params"][acct_key] == (ACCT if acct_key == "account_number" else RHS)
    for c in p["cancels"]:
        assert set(c["params"]) == OFFICIAL[c["tool"]] and all(isinstance(v, str) for v in c["params"].values())


def only(p):
    assert len(p["orders"]) == 1, p["orders"]
    return p["orders"][0]


TRANCHES_HALF = [dict(fresh(True, "2026-10-18", 0.5), pending=0),
                 dict(fresh(False, "2026-10-18", 0.5, 5), pending=2)]


# ------------------------------------------------------------------ sizing and orders

def test_entry_zero_to_half_first_tranche():
    p = run([sig("ETH", 0.5, tranches=TRANCHES_HALF)], snap(), make_cfg("ETH"))
    o = only(p)
    assert o["key"] == "ETH|ETHA|buy|0"
    assert o["tool"] == "place_equity_order" and o["preview_tool"] == "review_equity_order"
    prm = dict(o["params"])
    rid = prm.pop("ref_id")
    assert prm == {"account_number": ACCT, "symbol": "ETHA", "side": "buy", "type": "limit", "quantity": "49",
                   "limit_price": "25.13", "time_in_force": "gfd", "market_hours": "regular_hours"}
    assert str(uuid.UUID(rid)) == rid
    assert o["notional_usd"] == 1231.37
    assert o["reason"].startswith("target 0.00 -> 0.50 (tranche 1: green; tranche 2: red")
    assert p["errors"] == [] and p["cancels"] == [] and p["capital_usd"] == 10000.0 and p["live"] is False
    assert p["valid_until"] == "2026-10-19T19:45:00Z"            # 15:45 ET today
    assert p["signals_file"] == "signals/signals_2026-10-19.json"


def test_second_tranche_half_to_full():
    p = run([sig("ETH", 1.0)], snap(eq={"ETHA": pos(49)}), make_cfg("ETH"))
    o = only(p)
    assert (o["params"]["side"], o["params"]["quantity"], o["params"]["limit_price"]) == ("buy", "50", "25.13")
    assert o["reason"].startswith("target 0.49 -> 1.00")


def test_half_exit_sells_about_half_the_shares():
    p = run([sig("ETH", 0.5)], snap(eq={"ETHA": pos(100)}), make_cfg("ETH"))
    o = only(p)
    assert (o["key"], o["params"]["side"], o["params"]["type"]) == ("ETH|ETHA|sell|0", "sell", "limit")
    assert o["params"]["quantity"] == "49" and o["params"]["limit_price"] == "24.83"     # bid 24.95 x 0.995


def test_full_exit_sells_exactly_the_sellable_quantity():
    p = run([sig("ETH", 0.0)], snap(eq={"ETHA": pos(100, sellable=97)}), make_cfg("ETH"))
    o = only(p)
    assert o["params"]["side"] == "sell" and o["params"]["quantity"] == "97" and o["params"]["type"] == "limit"
    assert "full exit" in o["reason"]


def test_full_exit_of_fractional_shares():
    p = run([sig("ETH", 0.0)], snap(eq={"ETHA": pos(97.5)}), make_cfg("ETH"))
    o = only(p)                                                  # market open: one fractional market order
    assert o["params"]["type"] == "market" and o["params"]["quantity"] == "97.5" and "limit_price" not in o["params"]
    p = run([sig("ETH", 0.0)], snap(PREOPEN, eq={"ETHA": pos(97.5)}), make_cfg("ETH"), now=PREOPEN)
    o = only(p)                                                  # closed: whole shares now, remainder later
    assert o["params"]["type"] == "limit" and o["params"]["quantity"] == "97"
    assert any("fractional remainder" in w for w in p["warnings"])


def test_rebalance_band_suppresses_drift_trades():
    p = run([sig("ETH", 1.0)], snap(eq={"ETHA": pos(95)}), make_cfg("ETH"))   # $127 off a $2500 target, band $625
    assert p["orders"] == [] and p["errors"] == [] and p["skipped"] == []


def test_crypto_cap_scales_crypto_assets_together():
    cfg = make_cfg("ETH", "SOL", max_crypto_frac=0.3)
    p = run([sig("ETH", 1.0), sig("SOL", 1.0)], snap(), cfg)
    by = {o["asset"]: o for o in p["orders"]}
    assert by["ETH"]["params"]["quantity"] == "85"              # 2142.86 / 25.13
    assert by["SOL"]["tool"] == "place_crypto_order" and by["SOL"]["notional_usd"] == pytest.approx(857.14, abs=0.02)
    assert sum(o["notional_usd"] for o in p["orders"]) <= 3000
    assert any("scaled" in w for w in p["warnings"]) and "crypto cap x0.86" in by["ETH"]["reason"]


def test_max_order_usd_splits_orders():
    p = run([sig("ETH", 0.5)], snap(), make_cfg("ETH", max_order_usd=500))
    assert [o["key"] for o in p["orders"]] == ["ETH|ETHA|buy|0", "ETH|ETHA|buy|1", "ETH|ETHA|buy|2"]
    assert [o["params"]["quantity"] for o in p["orders"]] == ["19", "19", "11"]
    assert all(o["notional_usd"] <= 500 for o in p["orders"])
    assert len({o["params"]["ref_id"] for o in p["orders"]}) == 3


def test_max_day_usd_uses_the_ledger():
    ledger.add_placed(1000.0, "earlier-ref", NOW)
    cfg = make_cfg("ETH", max_day_usd=1500)
    p = planner.make_plan(signals(sig("ETH", 0.5)), snap(), cfg, NOW, 1, {}, journal=[], sleeve=owned(snap()))
    o = only(p)
    assert o["params"]["quantity"] == "19" and o["notional_usd"] <= 500       # $500 left today
    assert any("capped" in w for w in p["warnings"])
    ledger.add_placed(497.0, "another-ref", NOW)
    p = planner.make_plan(signals(sig("ETH", 0.5)), snap(), cfg, NOW, 1, {}, journal=[], sleeve=owned(snap()))
    assert p["orders"] == [] and any("min_order_usd" in s["reason"] for s in p["skipped"])


def test_buying_power_caps_buys():
    p = run([sig("ETH", 0.5)], snap(bp=300.0), make_cfg("ETH"))
    assert only(p)["params"]["quantity"] == "11"


def test_crypto_buying_power_caps_crypto_buys():
    p = run([sig("SOL", 1.0)], snap(cbp=200.0), make_cfg("SOL"))
    assert only(p)["notional_usd"] <= 200.0


# ------------------------------------------------------------------ flags and skips

def open_eq(oid="ord-1", sym="SPY", side="buy", ref="old-ref", qty=1.0, price=601.0, state="queued"):
    return dict(id=oid, ref_id=ref, symbol=sym, side=side, state=state, qty=qty, filled=0.0, price=price,
                kind="equity", type="limit", open=True, cancel_pending=state == "pending_cancelled",
                created_at=iso(NOW - timedelta(hours=1)), agent_initiated=True)


def open_cr(oid="cord-1", code="SOL", side="buy", ref="old-cref", qty=2.0, price=152.0):
    return dict(id=oid, ref_id=ref, symbol=code, side=side, state="confirmed", qty=qty, filled=0.0, price=price,
                kind="crypto", type="limit", open=True, cancel_pending=False, created_at=iso(NOW - timedelta(hours=1)))


def test_stop_means_no_orders_but_cancels_this_systems_open_orders():
    mine = open_eq(sym="ETHA")                                       # agent-initiated, on a managed vehicle
    users = dict(open_eq("user-1", sym="ETHA"), agent_initiated=False)
    s = snap(eq={"ETHA": pos(100)}, open_orders=[mine, open_eq("ord-2", sym="ETHA", state="pending_cancelled"), users])
    p = run([sig("ETH", 0.0)], s, make_cfg("ETH"), flags={"STOP": "manual kill"})
    assert p["orders"] == [] and p["flags"] == ["STOP"]
    assert [c["params"] for c in p["cancels"]] == [{"account_number": ACCT, "order_id": "ord-1"}]
    assert any("STOP" in x["reason"] and "manual kill" in x["reason"] for x in p["skipped"])
    assert any("user-1"[:8] in w and "not cancelled" in w for w in p["warnings"])


def test_flatten_sells_everything_and_buys_nothing():
    s = snap(eq={"ETHA": pos(100)}, cr={"SOL": pos(2.0)})
    p = run([sig("ETH", 1.0, errors=["bad data"]), sig("SPY", 1.0)], s, make_cfg("ETH", "SPY", "SOL"),
            flags={"FLATTEN": ""})
    assert {(o["asset"], o["params"]["side"], o["params"]["quantity"]) for o in p["orders"]} == {
        ("ETH", "sell", "100"), ("SOL", "sell", "2")}
    assert all(o["reason"].startswith("FLATTEN") for o in p["orders"])


def test_block_buys_allows_sells_only():
    s = snap(cr={"SOL": pos(2.0)})
    p = run([sig("ETH", 1.0), sig("SOL", 0.0)], s, make_cfg("ETH", "SOL"), flags={"BLOCK_BUYS": "reconcile"})
    o = only(p)
    assert o["asset"] == "SOL" and o["params"]["side"] == "sell" and o["params"]["limit_price"] == "148.50"
    assert o["params"]["time_in_force"] == "gtc" and o["params"]["rhs_account_number"] == RHS
    assert any(x["asset"] == "ETH" and "BLOCK_BUYS" in x["reason"] for x in p["skipped"])


def test_flags_are_read_from_the_state_dir():
    ledger.set_flag("BLOCK_BUYS", "reconcile: mismatch")
    p = planner.make_plan(signals(sig("ETH", 1.0)), snap(), make_cfg("ETH"), NOW, journal=[], placed_today_usd=0,
                          sleeve=owned(snap()))
    assert p["orders"] == [] and p["flags"] == ["BLOCK_BUYS"]


def test_asset_with_signal_errors_is_skipped_entirely():
    p = run([sig("ETH", 0.0, errors=["last bar is 2026-10-17, expected 2026-10-18"])],
            snap(eq={"ETHA": pos(100)}), make_cfg("ETH"))
    assert p["orders"] == []
    assert any(x["asset"] == "ETH" and "signal errors" in x["reason"] for x in p["skipped"])
    assert any(w.startswith("ALERT ETH") for w in p["warnings"])


def test_missing_or_stale_signal_never_means_exit():
    s = snap(eq={"ETHA": pos(100)})
    p = run([], s, make_cfg("ETH"))
    assert p["orders"] == [] and "no signal" in p["skipped"][0]["reason"]
    p = run([sig("ETH", 0.0, bar="2026-10-17")], s, make_cfg("ETH"))
    assert p["orders"] == [] and "re-run signals" in p["skipped"][0]["reason"]


def test_wash_sale_block_symbols_blocks_buys():
    cfg = make_cfg("ETH")
    cfg["wash_sale_block_symbols"] = ["etha"]
    p = run([sig("ETH", 0.5)], snap(), cfg)
    assert p["orders"] == [] and "wash_sale_block_symbols" in p["skipped"][0]["reason"]


def test_wash_sale_warning_from_journal():
    loss = {"ts": iso(NOW - timedelta(days=10)), "event": "fill", "kind": "equity", "symbol": "ETHA", "side": "sell",
            "average_price": "20.00", "avg_buy_price": "25.00"}
    p = run([sig("ETH", 0.5)], snap(), make_cfg("ETH"), journal=[loss])
    assert len(p["orders"]) == 1 and any(w.startswith("wash sale: ETHA") for w in p["warnings"])


def test_fractional_equity_only_during_market_hours():
    p = run([sig("SPY", 0.5)], snap(), make_cfg("SPY"))
    o = only(p)                                # $1000 target, one share is $603.50: whole shares miss by > 10%
    assert o["params"]["type"] == "market" and o["params"]["quantity"] == "1.657"
    assert "limit_price" not in o["params"]
    assert (o["params"]["time_in_force"], o["params"]["market_hours"]) == ("gfd", "regular_hours")
    p = run([sig("SPY", 0.5)], snap(PREOPEN), make_cfg("SPY"), now=PREOPEN)
    assert p["orders"] == [] and p["skipped"][0]["reason"] == planner.FRACTIONAL_MSG


def test_crypto_quantity_and_price_rounding():
    pairs = {"SOL-USD": {"min_order_size": "0.01", "asset_increment": "0.001", "quote_increment": "0.05",
                         "min_order_quote_amount": "1.00", "tradability": "tradable"}}
    o = only(run([sig("SOL", 1.0)], snap(pairs=pairs), make_cfg("SOL")))
    assert o["params"]["limit_price"] == "152.00" and o["params"]["quantity"] == "6.578"   # 152.005 -> 0.05 tick
    assert o["params"]["type"] == "limit" and o["params"]["time_in_force"] == "gtc"
    o = only(run([sig("SOL", 0.0)], snap(pairs=pairs, cr={"SOL": pos(3.14159)}), make_cfg("SOL")))
    assert o["params"]["quantity"] == "3.141" and o["params"]["limit_price"] == "148.50"
    p = run([sig("SOL", 0.0)], snap(pairs=pairs, cr={"SOL": pos(0.005)}), make_cfg("SOL"))
    assert p["orders"] == [] and any("minimum order size" in w for w in p["warnings"])      # dust


def test_same_inputs_same_plan_and_ref_ids():
    args = ([sig("ETH", 0.5), sig("SOL", 1.0)], snap(), make_cfg("ETH", "SOL", max_order_usd=500))
    a, b = run(*args), run(*args)
    assert a == b
    assert a["plan_id"].startswith("2026-10-19-") and len(a["plan_id"]) == len("2026-10-19-") + 8
    for o in a["orders"]:
        assert o["params"]["ref_id"] == str(uuid.uuid5(uuid.NAMESPACE_URL, f"moneyline|{a['plan_id']}|{o['key']}|1"))
    c = run(*args, attempt=2)
    assert c["plan_id"] != a["plan_id"]
    assert not {o["params"]["ref_id"] for o in c["orders"]} & {o["params"]["ref_id"] for o in a["orders"]}


def test_stale_open_orders_are_cancelled_and_block_new_orders():
    s = snap(open_orders=[open_eq(sym="ETHA", qty=10.0, price=24.0), open_eq("ord-spy"), open_cr()])
    journal = [{"ts": iso(NOW - timedelta(days=1)), "event": "place", "tool": "mcp__rh__place_equity_order",
                "order_id": "ord-spy", "params": {"symbol": "SPY", "side": "buy", "quantity": "1"}},
               {"ts": iso(NOW - timedelta(days=1)), "event": "place", "tool": "mcp__rh__place_crypto_order",
                "order_id": "cord-1", "params": {"symbol": "SOL", "side": "buy", "quantity": "2"}}]
    p = run([sig("ETH", 0.5), sig("SOL", 1.0)], s, make_cfg("ETH", "SOL"), journal=journal, attempt=2)
    assert p["orders"] == []
    cancels = {c["params"]["order_id"]: c for c in p["cancels"]}
    assert set(cancels) == {"ord-1", "ord-spy", "cord-1"}                 # ord-1: agent-initiated on ETHA
    assert cancels["cord-1"]["tool"] == "cancel_crypto_order"
    assert cancels["cord-1"]["params"]["rhs_account_number"] == RHS
    assert all(c["reason"] == "stale order from an earlier plan" for c in cancels.values())
    held = [x["reason"] for x in p["skipped"] if planner.CANCEL_MSG in x["reason"]]
    assert len(held) == 2 and all("plan --attempt 2" in r for r in held)


def test_users_own_open_orders_are_never_cancelled():
    """Regression: the plan cancelled the user's open orders on any symbol (review p5)."""
    aapl = dict(open_eq("user-aapl-1", sym="AAPL"), agent_initiated=False)
    btc = dict(open_cr("user-btc-1", code="BTC"), agent_initiated=False)
    etha = dict(open_eq("user-etha-1", sym="ETHA", qty=3.0, price=20.0), agent_initiated=False)
    p = run([sig("ETH", 0.5)], snap(open_orders=[aapl, btc]), make_cfg("ETH"))
    assert p["cancels"] == [] and len(p["orders"]) == 1
    p = run([sig("ETH", 0.5)], snap(open_orders=[aapl, btc, etha]), make_cfg("ETH"))
    assert p["cancels"] == [] and p["orders"] == []                   # managed vehicle: hold off, cancel in the app
    assert any("cancel it in the app" in x["reason"] for x in p["skipped"])
    p = run([sig("ETH", 0.0)], snap(open_orders=[aapl, btc, etha], eq={"ETHA": pos(10)}), make_cfg("ETH"),
            flags={"STOP": ""})
    assert p["cancels"] == []


def test_open_order_of_this_plan_is_kept_not_replaced():
    cfg = make_cfg("ETH")
    first = only(run([sig("ETH", 0.5)], snap(), cfg))
    mine = open_eq("ord-mine", sym="ETHA", ref=first["params"]["ref_id"], qty=49.0, price=25.13)
    p = run([sig("ETH", 0.5)], snap(open_orders=[mine]), cfg)
    assert p["orders"] == [] and p["cancels"] == [] and "already open" in p["skipped"][0]["reason"]
    approved = dict(mine, id="ord-approved", ref_id="approval-id-123")     # approval carries another id
    p = run([sig("ETH", 0.5)], snap(open_orders=[approved]), cfg)
    assert p["orders"] == [] and p["cancels"] == []
    done = dict(mine, state="filled", open=False, filled=49.0)
    p = run([sig("ETH", 0.5)], snap(orders=[done]), cfg)
    assert p["orders"] == [] and "--attempt 2" in p["skipped"][0]["reason"]


def test_collar_ladder_by_attempt():
    cfg = make_cfg("ETH")
    prices = [only(run([sig("ETH", 0.5)], snap(), cfg, attempt=a))["params"]["limit_price"] for a in (1, 2, 3, 4)]
    assert prices == ["25.13", "25.25", "25.50", "25.50"]
    cfg = make_cfg("ETH", equity_collar_frac=0.01)
    assert planner.collar(0.01, cfg["limits"], 3) == 0.03                    # 0.04 capped at max_collar_frac
    assert only(run([sig("ETH", 0.5)], snap(), cfg, attempt=3))["params"]["limit_price"] == "25.75"
    with pytest.raises(ValueError):
        run([sig("ETH", 0.5)], snap(), cfg, attempt=0)


def test_stale_quote_is_an_error():
    p = run([sig("ETH", 0.5)], snap(quotes={"ETHA": quote(24.95, 25.0, age=60)}), make_cfg("ETH"))
    assert p["orders"] == []
    assert any("ETHA" in e and "60 min old" in e for e in p["errors"])


def test_zero_bid_is_an_error():
    p = run([sig("ETH", 0.5)], snap(quotes={"ETHA": quote(0.0, 25.0, last=24.97)}), make_cfg("ETH"))
    assert p["orders"] == [] and any("bid/ask <= 0" in e for e in p["errors"])


def test_account_number_mismatch_is_an_error(tmp_path):
    inbox = tmp_path / "inbox"
    write_inbox(inbox, account="OTHERACCT9")
    cfg = make_cfg("ETH")
    s = sn.build_snapshot(inbox, cfg, NOW)
    p = run([sig("ETH", 0.0)], s, cfg)
    assert p["errors"] and p["orders"] == [] and p["cancels"] == []
    p = run([sig("ETH", 0.0)], snap(account="OTHERACCT9", eq={"ETHA": pos(100)}), cfg)
    assert any("snapshot account_number differs" in e for e in p["errors"]) and p["orders"] == []
    p = run([sig("ETH", 0.0)], snap(eq={"ETHA": pos(100)}), make_cfg("ETH", account="FILL-IN-PRIVATE-CONFIG-ONLY"))
    assert any("not filled in" in e for e in p["errors"]) and p["orders"] == []


def test_plan_from_inbox_end_to_end(tmp_path):
    inbox = tmp_path / "inbox"
    write_inbox(inbox)
    cfg = make_cfg("ETH")
    p = run([sig("ETH", 0.5)], sn.build_snapshot(inbox, cfg, NOW), cfg)
    assert p["errors"] == []
    assert p["cancels"] == []                     # the open SPY order is not this system's and SPY is not managed
    o = only(p)
    assert (o["params"]["side"], o["params"]["quantity"]) == ("sell", "49")


def test_duplicate_vehicle_is_an_error():
    p = run([sig("ETH", 1.0), sig("ETH-TV", 1.0)], snap(), make_cfg("ETH", "ETH-TV"))
    assert p["orders"] == [] and any("same vehicle ETHA" in e for e in p["errors"])


def test_unmanaged_position_warning_and_write_plan(tmp_path):
    p = run([sig("ETH", 0.5)], snap(eq={"AAPL": pos(3)}), make_cfg("ETH"))
    assert any("AAPL" in w and "not managed" in w for w in p["warnings"])
    f = planner.write_plan(p)
    cur = cfgmod.paths()["plan_current"]
    assert f.name == f"plan_{p['plan_id']}.json" and json.loads(f.read_text()) == json.loads(cur.read_text()) == p
    text = planner.format_plan(p)
    assert ACCT not in text and "review_equity_order" in text and "place_equity_order" in text


# ------------------------------------------------------------------ review regressions

NOBODY = {"baseline": True, "sleeve": {"equity": {}, "crypto": {}}, "mismatches": []}


def test_shares_outside_the_sleeve_are_never_sold():
    """Regression: the plan counted the user's own 100 ETHA as the sleeve's and sold them (review p1)."""
    s = snap(eq={"ETHA": pos(100)}, total=5000.0)
    cfg = make_cfg("ETH")
    cfg["capital"]["max_usd"] = 1000
    p = run([sig("ETH", 1.0)], s, cfg, sleeve=NOBODY)
    assert {o["params"]["side"] for o in p["orders"]} == {"buy"}          # green: the sleeve buys its own share
    assert any("outside this sleeve" in w for w in p["warnings"])
    assert any("worth more than capital.max_usd" in w for w in p["warnings"])
    for sigs, flags in (([sig("ETH", 0.0)], {}), ([sig("ETH", 0.5)], {}), ([sig("ETH", 1.0)], {"FLATTEN": ""}),
                        ([sig("ETH", 1.0)], {"BLOCK_BUYS": ""})):
        p = run(sigs, s, cfg, flags=flags, sleeve=NOBODY)
        assert not [o for o in p["orders"] if o["params"]["side"] == "sell"], (sigs, flags)
    p = run([sig("ETH", 0.0)], s, cfg, sleeve=owned(s, ETHA=9.0))            # the sleeve owns 9: exit sells 9
    assert only(p)["params"]["quantity"] == "9"
    spy = snap(eq={"SPY": pos(10, avg=500.0)})
    p = run([sig("SPY", 0.5)], spy, make_cfg("SPY"), sleeve=NOBODY)
    assert {o["params"]["side"] for o in p["orders"]} == {"buy"}


def test_position_mismatch_skips_the_asset_entirely():
    """Regression: a reconcile mismatch only blocked buys, so a manual buy of 100 ETHA was partly sold (review p15)
    and a stale positions capture caused a second full buy (review p4)."""
    s = snap(eq={"ETHA": pos(109)}, cr={"SOL": pos(1.0)})
    status = owned(s, ETHA=9.0)
    status["mismatches"] = [dict(kind="equity", symbol="ETHA", expected=9.0, captured=109.0, diff=100.0)]
    for tf in (0.0, 0.5, 1.0):
        p = run([sig("ETH", tf), sig("SOL", 0.0)], s, make_cfg("ETH", "SOL"), flags={"BLOCK_BUYS": "x"},
                sleeve=status)
        assert [o["asset"] for o in p["orders"]] == ["SOL"]
        assert any(e.startswith("ETH: ETHA position 109 differs") for e in p["errors"])


def test_stale_positions_capture_after_a_fill_is_caught_from_the_state_dir():
    """p4: positions captured before the attempt-1 order filled; `plan --attempt 2` must not buy again."""
    ledger.write_json(cfgmod.paths()["positions_ref"], {"as_of": iso(NOW - timedelta(hours=2)), "equity": {},
                                                        "crypto": {}, "sleeve": {}, "orders": {}})
    first = only(run([sig("ETH", 0.5)], snap(), make_cfg("ETH")))
    place = {"ts": iso(NOW - timedelta(minutes=30)), "event": "place", "tool": "place_equity_order",
             "ref_id": first["params"]["ref_id"], "params": {k: v for k, v in first["params"].items()
                                                              if k != "account_number"}, "state": "queued"}
    filled = dict(open_eq("ord-a1", sym="ETHA", ref="approval-1", qty=49.0, price=25.13, state="filled"),
                  open=False, filled=49.0, created_at=iso(NOW - timedelta(minutes=29)))
    s = snap(orders=[filled])                                               # positions still show 0 ETHA
    p = planner.make_plan(signals(sig("ETH", 0.5)), s, make_cfg("ETH"), NOW, 2, {}, placed_today_usd=0.0,
                          journal=[place])
    assert p["orders"] == [] and any("differs from the 49 expected" in e for e in p["errors"])
    s = snap(orders=[filled], eq={"ETHA": pos(49)})                         # fresh positions: consistent, no buy
    p = planner.make_plan(signals(sig("ETH", 0.5)), s, make_cfg("ETH"), NOW, 2, {}, placed_today_usd=0.0,
                          journal=[place])
    assert p["errors"] == [] and p["orders"] == []
    os_ = planner.make_plan(signals(sig("ETH", 0.5)), snap(), make_cfg("ETH"), NOW, 1, {}, placed_today_usd=0.0,
                            journal=[])
    assert os_["orders"]                                                    # the baseline alone is enough to trade


def test_no_baseline_means_no_orders():
    p = planner.make_plan(signals(sig("ETH", 0.5)), snap(), make_cfg("ETH"), NOW, 1, {}, placed_today_usd=0.0,
                          journal=[])
    assert p["orders"] == [] and any("no reconciled positions baseline" in e for e in p["errors"])


def test_no_market_orders_after_the_1545_cutoff():
    """Regression: a fractional market order planned at 15:50 ET stayed valid until 15:45 the next day (review p2)."""
    late = datetime(2026, 10, 19, 19, 50, tzinfo=UTC)                     # 15:50 ET, market still open
    p = run([sig("SPY", 0.5)], snap(late), make_cfg("SPY"), now=late)
    assert p["orders"] == [] and p["skipped"][0]["reason"] == planner.FRACTIONAL_MSG
    assert all(o["params"]["type"] != "market" for o in run([sig("ETH", 0.5)], snap(late), make_cfg("ETH"),
                                                            now=late)["orders"])


def test_missing_pair_metadata_or_sub_tick_price_skips_only_that_asset():
    """Regression: no pair metadata fell back to a $0.01 tick; a sub-cent coin crashed the whole plan (review p7)."""
    p = run([sig("ETH", 0.5), sig("SOL", 1.0)], snap(pairs={}), make_cfg("ETH", "SOL"))
    assert [o["asset"] for o in p["orders"]] == ["ETH"]
    assert any("no get_currency_pairs metadata for SOL-USD" in e for e in p["errors"])
    tiny = {"SOL-USD": quote(0.0000123, 0.0000124, kind="crypto")}
    p = run([sig("ETH", 0.5), sig("SOL", 1.0)], snap(quotes=tiny), make_cfg("ETH", "SOL"))
    assert [o["asset"] for o in p["orders"]] == ["ETH"] and any("rounds to zero" in e for e in p["errors"])
    p = run([sig("ETH", 0.0), sig("SOL", 0.0)], snap(quotes=tiny, pairs={}, eq={"ETHA": pos(10)},
                                                     cr={"SOL": pos(1000.0)}), make_cfg("ETH", "SOL"))
    assert [o["asset"] for o in p["orders"]] == ["ETH"]


def test_cent_rounded_notionals_respect_max_day_usd():
    """Regression: notional_usd rounded after the caps summed to 300.05 against max_day_usd 300 (review p12)."""
    q = {"SPY": quote(4776.00, 4777.00)}
    cfg = make_cfg("SPY", max_order_usd=25, max_day_usd=300, max_orders_per_plan=20)
    p = run([sig("SPY", 0.0)], snap(eq={"SPY": pos(0.07)}, quotes=q), cfg)
    total = 0.0
    for o in p["orders"]:
        assert o["notional_usd"] <= 25 and o["params"]["type"] == "market"
        total = round(total + o["notional_usd"], 2)
        assert total <= 300 + 1e-9                                         # the hook's check, order by order
    assert len(p["orders"]) == 12 and total == 300.0
    p = run([sig("SPY", 1.0)], snap(quotes=q, bp=2000.0), make_cfg("SPY", max_order_usd=25, max_day_usd=20000))
    assert sum(o["notional_usd"] for o in p["orders"]) <= 2000.0
