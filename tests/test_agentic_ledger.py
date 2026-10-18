"""Tests for agentic/ledger.py: journal, ET-dated notional ledger, flags, wash-sale lookup, reconcile."""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentic import config as cfgmod  # noqa: E402
from agentic import ledger  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(tmp_path / "state"))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ journal

def test_journal_append_read_strips_account_numbers():
    e = ledger.append_journal({"event": "place", "tool": "mcp__rh__place_equity_order", "account_number": "X1",
                               "params": {"account_number": "X1", "symbol": "ETHA", "side": "buy"}}, now_utc=NOW)
    assert e["ts"] == "2026-10-19T15:00:00Z" and "account_number" not in e and "account_number" not in e["params"]
    ledger.append_journal({"event": "cancel", "ts": iso(NOW + timedelta(hours=1))})
    with open(cfgmod.paths()["journal"], "a") as fh:
        fh.write("not json\n[1, 2]\n")
    js = ledger.read_journal()
    assert [x["event"] for x in js] == ["place", "cancel"]
    assert [x["event"] for x in ledger.read_journal(since=NOW + timedelta(minutes=30))] == ["cancel"]
    assert "X1" not in cfgmod.paths()["journal"].read_text()


def test_read_journal_without_a_file():
    assert ledger.read_journal() == []


# ------------------------------------------------------------------ ledger

def test_ledger_is_keyed_by_et_date_and_idempotent_per_ref_id():
    late = datetime(2026, 10, 20, 2, 0, tzinfo=UTC)          # 22:00 ET on the 19th
    assert ledger.day_key(late) == "2026-10-19"
    assert ledger.add_placed(305.16, "ref-a", NOW) == 305.16
    assert ledger.add_placed(305.16, "ref-a", late) == 305.16          # same ref, same ET day: counted once
    assert ledger.add_placed(100.0, "ref-b", late) == 405.16
    assert ledger.placed_usd(NOW) == 405.16
    assert ledger.placed_usd(datetime(2026, 10, 20, 15, 0, tzinfo=UTC)) == 0.0
    raw = json.loads(cfgmod.paths()["ledger"].read_text())
    assert raw["2026-10-19"]["refs"] == {"ref-a": 305.16, "ref-b": 100.0}


def test_ledger_reads_other_day_formats():
    p = cfgmod.paths()["ledger"]
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"2026-10-19": 250.0, "2026-10-20": [{"notional_usd": 10}, {"notional_usd": 5.5}],
                             "2026-10-21": {"refs": {"a": 1, "b": 2}}}))
    assert ledger.placed_usd(day="2026-10-19") == 250.0
    assert ledger.placed_usd(day="2026-10-20") == 15.5
    assert ledger.placed_usd(day="2026-10-21") == 3.0
    assert ledger.add_placed(50.0, "c", NOW) == 300.0                 # a bare number is kept as prior notional


# ------------------------------------------------------------------ flags

def test_flags_set_read_clear():
    assert ledger.read_flags() == {}
    ledger.set_flag("BLOCK_BUYS", "reconcile: ETHA expected 10 got 12")
    ledger.set_flag("STOP")
    assert ledger.read_flags() == {"BLOCK_BUYS": "reconcile: ETHA expected 10 got 12", "STOP": ""}
    assert ledger.clear_flag("STOP") and not ledger.clear_flag("STOP")
    assert set(ledger.read_flags()) == {"BLOCK_BUYS"}
    with pytest.raises(ValueError):
        ledger.set_flag("PAUSE")


# ------------------------------------------------------------------ wash sales

def test_loss_sales_within_30_days_equity_only():
    def fill(days, px, basis, kind="equity", sym="ETHA"):
        return {"ts": iso(NOW - timedelta(days=days)), "event": "fill", "kind": kind, "symbol": sym, "side": "sell",
                "average_price": px, "avg_buy_price": basis}
    js = [fill(10, "20.0", "25.0"), fill(5, "30.0", "25.0"), fill(40, "20.0", "25.0"),
          fill(3, "100", "200", kind="crypto", sym="SOL"), fill(2, "1.0", "2.0", sym="SPY")]
    got = ledger.loss_sales("etha", NOW, js)
    assert len(got) == 1 and got[0]["average_price"] == "20.0"
    assert ledger.loss_sales("SOL", NOW, js) == []


# ------------------------------------------------------------------ reconcile

def test_reconcile_pure():
    exp = {"equity": {"ETHA": 49}, "crypto": {"SOL": {"qty": 2.0}}}
    ok = ledger.reconcile(exp, {"equity": {"ETHA": {"qty": 49.0, "sellable": 49.0}}, "crypto": {"SOL": 2.0000000001}})
    assert ok["ok"] and not ok["block_buys"] and ok["mismatches"] == []
    bad = ledger.reconcile(exp, {"equity": {"ETHA": 52.0, "AAPL": 1.0}, "crypto": {"SOL": 2.0}})
    assert bad["block_buys"] and {m["symbol"] for m in bad["mismatches"]} == {"ETHA", "AAPL"}
    assert any("buys blocked" in line for line in bad["report"])


def eq(sym, qty, avg=22.0):
    return {"qty": qty, "sellable": qty, "avg_buy_price": avg}


def order(oid, sym, side, filled, qty, state="filled", ref=None, kind="equity", price=25.13, avg=None,
          created=NOW - timedelta(minutes=30), agent=True):
    return {"id": oid, "ref_id": ref, "symbol": sym, "side": side, "state": state, "qty": qty, "filled": filled,
            "price": price, "kind": kind, "type": "limit", "open": state in ("queued", "partially_filled"),
            "created_at": iso(created), "average_price": avg, "agent_initiated": agent}


def snapshot(eq_pos=None, cr_pos=None, orders=(), as_of=NOW):
    return {"as_of": iso(as_of), "equity_positions": eq_pos or {}, "crypto_positions": cr_pos or {},
            "orders": list(orders), "open_orders": [o for o in orders if o["open"]], "errors": []}


def place(ref, sym="ETHA", side="buy", qty="49", price="25.13", order_id=None, ts=NOW - timedelta(minutes=31)):
    return ledger.append_journal({"event": "place", "tool": "mcp__robinhood-trading__place_equity_order",
                                  "ref_id": ref, "order_id": order_id, "ts": iso(ts),
                                  "params": {"symbol": sym, "side": side, "type": "limit", "quantity": qty,
                                             "limit_price": price, "ref_id": ref}})


def test_reconcile_snapshot_lifecycle():
    p = cfgmod.paths()
    r = ledger.reconcile_snapshot(snapshot({"ETHA": eq("ETHA", 10.0)}, as_of=NOW - timedelta(hours=2)),
                                  now_utc=NOW - timedelta(hours=2))
    assert r["ok"] and r["baseline_written"] and "baseline" in r["notes"][0]
    base = json.loads(p["positions_ref"].read_text())
    assert base["equity"] == {"ETHA": {"qty": 10.0, "avg_buy_price": 22.0}}

    place("ref-1", order_id="ord-1")                        # this system's order, partially filled so far
    s = snapshot({"ETHA": eq("ETHA", 30.0)}, orders=[order("ord-1", "ETHA", "buy", 20.0, 49.0, "partially_filled")])
    r = ledger.reconcile_snapshot(s, now_utc=NOW)
    assert r["ok"] and not r["block_buys"] and len(r["fills"]) == 1 and r["fills"][0]["filled_delta"] == 20.0
    assert not p["BLOCK_BUYS"].exists()

    s = snapshot({"ETHA": eq("ETHA", 59.0)}, orders=[order("ord-1", "ETHA", "buy", 49.0, 49.0)])
    r = ledger.reconcile_snapshot(s, now_utc=NOW + timedelta(minutes=5))
    assert r["ok"] and r["fills"][0]["filled_delta"] == 29.0
    ledger.reconcile_snapshot(s, now_utc=NOW + timedelta(minutes=6))       # nothing new: no duplicate fill event
    fills = [e for e in ledger.read_journal() if e.get("event") == "fill"]
    assert [f["cumulative_quantity"] for f in fills] == [20.0, 49.0]

    manual = order("ord-x", "ETHA", "buy", 5.0, 5.0, agent=False, created=NOW + timedelta(minutes=7))
    s = snapshot({"ETHA": eq("ETHA", 64.0)}, orders=[order("ord-1", "ETHA", "buy", 49.0, 49.0), manual])
    r = ledger.reconcile_snapshot(s, now_utc=NOW + timedelta(minutes=10))
    assert r["block_buys"] and not r["baseline_written"]
    assert p["BLOCK_BUYS"].exists() and "ETHA" in p["BLOCK_BUYS"].read_text()
    assert any("not placed by this system" in n for n in r["notes"])
    assert json.loads(p["positions_ref"].read_text())["equity"]["ETHA"]["qty"] == 59.0     # baseline kept

    r = ledger.reconcile_snapshot(s, now_utc=NOW + timedelta(minutes=11), accept=True)
    assert r["baseline_written"] and not r["block_buys"]
    assert json.loads(p["positions_ref"].read_text())["equity"]["ETHA"]["qty"] == 64.0


def test_reconcile_records_avg_buy_price_on_sells_for_wash_sales():
    ledger.reconcile_snapshot(snapshot({"ETHA": eq("ETHA", 10.0, avg=25.0)}, as_of=NOW - timedelta(hours=1)),
                              now_utc=NOW - timedelta(hours=1))
    place("ref-s", side="sell", qty="10", price="20.00")
    sold = order("ord-s", "ETHA", "sell", 10.0, 10.0, price=20.0, avg=20.0, ref="approval-77")
    s = snapshot({}, orders=[sold])
    r = ledger.reconcile_snapshot(s, now_utc=NOW)
    assert r["ok"] and r["fills"][0]["avg_buy_price"] == 25.0          # matched by params (approval id differs)
    assert len(ledger.loss_sales("ETHA", NOW + timedelta(days=1))) == 1


def test_reconcile_without_baseline_but_with_orders_blocks():
    place("ref-1", order_id="ord-1")
    r = ledger.reconcile_snapshot(snapshot({"ETHA": eq("ETHA", 49.0)}), now_utc=NOW)
    assert r["block_buys"] and cfgmod.paths()["BLOCK_BUYS"].exists()
    assert not cfgmod.paths()["positions_ref"].exists()


def test_reconcile_snapshot_with_errors_does_nothing():
    r = ledger.reconcile_snapshot({"errors": ["missing capture"]}, now_utc=NOW)
    assert not r["ok"] and not r["block_buys"] and not cfgmod.paths()["positions_ref"].exists()
    assert not cfgmod.paths()["BLOCK_BUYS"].exists()


def test_is_own_order_rules():
    place("ref-1", order_id="ord-1")
    idx = ledger.journal_index(ledger.read_journal())
    assert ledger.is_own_order(order("ord-1", "ETHA", "buy", 0, 49.0), idx)
    assert ledger.is_own_order(order("other", "ETHA", "buy", 0, 49.0, ref="approval"), idx)       # same params
    assert not ledger.is_own_order(order("other", "ETHA", "buy", 0, 49.0, agent=False), idx)
    assert not ledger.is_own_order(order("other", "ETHA", "buy", 0, 48.0), idx)
    assert not ledger.is_own_order(order("other", "ETHA", "buy", 0, 49.0,
                                         created=NOW - timedelta(hours=3)), idx)                  # predates the place


def test_sleeve_starts_at_the_declared_quantity_and_follows_own_fills():
    """The sleeve owns only what config sleeve_initial_qty declares at the first baseline plus its own fills; the
    user's other shares are never the plan's to sell (review p1)."""
    p = cfgmod.paths()
    r = ledger.reconcile_snapshot(snapshot({"ETHA": eq("ETHA", 100.0)}, as_of=NOW - timedelta(hours=2)),
                                  now_utc=NOW - timedelta(hours=2), initial_sleeve={"ETHA": 9})
    assert r["sleeve"]["equity"] == {"ETHA": 9.0} and any("outside the sleeve" in n for n in r["notes"])
    assert json.loads(p["positions_ref"].read_text())["sleeve"]["equity"] == {"ETHA": 9.0}
    place("ref-1", order_id="ord-1")
    s = snapshot({"ETHA": eq("ETHA", 149.0)}, orders=[order("ord-1", "ETHA", "buy", 49.0, 49.0)])
    st = ledger.sleeve_status(s)
    assert st["baseline"] and st["sleeve"]["equity"]["ETHA"] == 58.0 and st["mismatches"] == []
    stale = snapshot({"ETHA": eq("ETHA", 100.0)}, orders=[order("ord-1", "ETHA", "buy", 49.0, 49.0)])
    assert ledger.sleeve_status(stale)["mismatches"][0]["expected"] == 149.0      # positions predate the fill
    r = ledger.reconcile_snapshot(s, now_utc=NOW)
    assert r["ok"] and json.loads(p["positions_ref"].read_text())["sleeve"]["equity"] == {"ETHA": 58.0}
    sold = snapshot({"ETHA": eq("ETHA", 10.0)}, orders=[order("ord-1", "ETHA", "buy", 49.0, 49.0)])
    r = ledger.reconcile_snapshot(sold, now_utc=NOW + timedelta(minutes=5), accept=True)   # the user sold 139
    assert r["sleeve"]["equity"] == {"ETHA": 10.0}                                       # clamped to what is held


def test_sleeve_status_without_a_baseline():
    assert ledger.sleeve_status(snapshot({"ETHA": eq("ETHA", 5.0)}))["baseline"] is False
