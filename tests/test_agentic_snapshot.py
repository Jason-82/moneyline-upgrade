"""Tests for agentic/snapshot.py: official Robinhood MCP output shapes (tools/list capture 2026-10-12), MCP
wrappers, newest-capture selection, freshness, account checks, pagination. All data is synthetic."""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentic import config as cfgmod  # noqa: E402
from agentic import snapshot as sn  # noqa: E402

UTC = timezone.utc
ACCT = "TESTACCT01"          # synthetic account numbers
RHS = "100000001"
OTHER = "OTHERACCT9"
NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)      # Monday 11:00 ET


@pytest.fixture(autouse=True)
def _state(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(tmp_path / "state"))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def make_cfg(crypto=False, **limits):
    raw = json.loads(cfgmod.EXAMPLE.read_text())
    raw["account"] = {"account_number": ACCT, "rhs_account_number": RHS, "approvals_required": True}
    for a in raw["assets"]:
        a["enabled"] = a["name"] == "ETH" or (crypto and a["name"] == "SOL")
    raw["limits"].update(limits)
    return cfgmod.validate(raw)


# ------------------------------------------------------------------ builders (official output schemas)

def env(data):
    return {"data": data, "guide": "synthetic guide text"}


def portfolio(total="10000.00", cash="4000.00", bp="4000.00", ubp=None, cbp="4000.00"):
    d = {"total_value": total, "equity_value": "6000.00", "options_value": "0.00", "futures_value": "0.00",
         "event_contracts_value": "0.00", "crypto_value": "0.00", "cash": cash, "pending_deposits": "0.00",
         "mutual_funds_value": "0.00", "fixed_income_value": "0.00", "currency": "USD",
         "buying_power": {"buying_power": bp, "unleveraged_buying_power": ubp or bp, "intraday_buying_power": None,
                          "off_intraday_buying_power": None, "display_currency": "USD"}}
    if cbp is not None:
        d["crypto_buying_power"] = {"buying_power": cbp}
    return env(d)


def eq_position(sym, qty, sellable=None, avg="20.00"):
    return {"symbol": sym, "quantity": qty, "intraday_quantity": "0.00000000", "average_buy_price": avg,
            "shares_available_for_sells": qty if sellable is None else sellable, "shares_held_for_sells": "0.00000000",
            "shares_held_for_stock_grants": "0.00000000", "shares_held_for_options_events": "0.00000000",
            "shares_held_for_asset_transfer": "0.00000000", "shares_pending_from_options_events": "0.00000000",
            "type": "long"}


def eq_positions(*rows, next_=""):
    return env({"positions": list(rows), "next": next_})


def cr_position(code, qty, transferable=None, pair_id="pair-sol-uuid"):
    return {"account_id": "acct-uuid", "currency": {"code": code, "name": code.title(), "type": "cryptocurrency"},
            "currency_pair_id": pair_id, "quantity": qty,
            "quantity_transferable": qty if transferable is None else transferable,
            "quantity_held_for_sell": "0", "cost_bases": [{"direct_quantity": qty, "direct_cost_basis": "300.00",
                                                           "intraday_quantity": "0", "intraday_cost_basis": "0"}]}


def cr_positions(*rows):
    usd = {"account_id": "acct-uuid", "currency": {"code": "USD", "name": "U.S. Dollar", "type": "fiat"},
           "quantity": "12.00", "quantity_transferable": "12.00", "quantity_held_for_sell": "0"}
    return env({"results": [usd, *rows], "next": ""})


def eq_quote(sym, bid, ask, last, ts):
    return {"quote": {"symbol": sym, "last_trade_price": last, "venue_last_trade_time": ts,
                      "last_non_reg_trade_price": None, "venue_last_non_reg_trade_time": None,
                      "adjusted_previous_close": last, "previous_close": last, "previous_close_date": "2026-10-16",
                      "bid_price": bid, "venue_bid_time": ts, "ask_price": ask, "venue_ask_time": ts,
                      "has_traded": True, "state": "active"},
            "close": {"symbol": sym, "date": "2026-10-16", "price": last, "interpolated": False, "source": "sip-close"}}


def eq_quotes(*rows):
    return env({"results": list(rows)})


def cr_quote(sym, bid, ask, ts, pair_id="pair-sol-uuid"):
    mark = f"{(float(bid) + float(ask)) / 2:.4f}"
    return {"symbol": sym, "id": pair_id, "bid_price": bid, "bid_time": ts, "ask_price": ask, "ask_time": ts,
            "mark_price": mark, "open_price": mark, "routing": "market_maker", "updated_at": ts}


def cr_quotes(*rows):
    return env({"results": list(rows)})


def eq_order(oid, sym, side="buy", state="queued", qty="10.00000000", filled="0.00000000", price="25.13000000",
             ref=None, created=None, agent=True, typ="limit"):
    return {"id": oid, "ref_id": ref, "instrument_id": "instr-uuid", "symbol": sym, "side": side, "type": typ,
            "state": state, "quantity": qty, "cumulative_quantity": filled, "price": price, "stop_price": None,
            "average_price": None if filled.strip("0.") == "" else price, "fees": "0.00", "dollar_based_amount": None,
            "time_in_force": "gfd", "market_hours": "regular_hours", "trigger": "immediate",
            "placed_agent": "agentic", "agent_initiated": agent, "created_at": created or iso(NOW - timedelta(hours=1)),
            "last_transaction_at": None, "executions": []}


def eq_orders(*rows, next_=""):
    return env({"orders": list(rows), "next": next_})


def cr_order(oid, code="SOL", side="buy", state="confirmed", group="open", qty="2.000", filled="0", price="152.00",
             ref=None, pair_id="pair-sol-uuid", with_code=True, created=None):
    d = {"id": oid, "ref_id": ref, "account_id": "acct-uuid", "currency_pair_id": pair_id, "side": side,
         "type": "limit", "state": state, "derived_state": group, "state_group": group, "time_in_force": "gtc",
         "quantity": qty, "cumulative_quantity": filled, "price": price, "limit_price": price, "stop_price": None,
         "average_price": None, "initiator_type": "api_trading", "created_at": created or iso(NOW - timedelta(hours=1)),
         "updated_at": iso(NOW - timedelta(minutes=30)), "canceled_at": None}
    if with_code:
        d["currency_code"] = code
    return d


def cr_orders(*rows, rhs=RHS):
    return env({"rhs_account_number": rhs, "crypto_account_number": "RHC0000001", "results": list(rows), "next": ""})


def pair(sym="SOL-USD", pid="pair-sol-uuid", qinc="0.001", pinc="0.05", min_size="0.01"):
    code = sym.split("-")[0]
    return {"id": pid, "symbol": sym, "display_symbol": "", "name": code.title(),
            "asset_currency": {"id": f"cur-{code}", "code": code, "name": code.title(), "type": "cryptocurrency"},
            "quote_currency": {"id": "cur-usd", "code": "USD", "name": "U.S. Dollar", "type": "fiat"},
            "tradability": "tradable", "tradability_by_account_type": {}, "display_only": False,
            "min_order_size": min_size, "max_order_size": "100000", "min_order_quantity_increment": qinc,
            "min_order_price_increment": pinc, "min_order_quote_amount": "1.00", "market_orders_only": False,
            "type": "cryptocurrency", "halted": False}


def pairs(*rows):
    return env({"results": list(rows), "next": ""})


DEFAULT_INPUT = {
    "get_portfolio": {"account_number": ACCT}, "get_equity_positions": {"account_number": ACCT},
    "get_equity_orders": {"account_number": ACCT}, "get_crypto_positions": {"rhs_account_number": RHS},
    "get_crypto_orders": {"rhs_account_number": RHS, "state_group": "open"},
    "get_equity_quotes": {"symbols": ["ETHA"]}, "get_crypto_quotes": {"symbols": ["SOL-USD"]},
    "get_currency_pairs": {"limit": 100}}


def wrap(response, how):
    if how == "text":
        return {"content": [{"type": "text", "text": json.dumps(response)}]}
    if how == "structured":
        return {"structuredContent": response, "content": [{"type": "text", "text": "see structuredContent"}]}
    if how == "list":
        return [{"type": "text", "text": json.dumps(response)}]
    return response


def write_cap(inbox, short, response, tool_input=None, at=None, how="raw", server="robinhood-trading"):
    at = at or NOW - timedelta(minutes=2)
    inbox.mkdir(parents=True, exist_ok=True)
    n = 0
    while True:
        f = inbox / f"{(at + timedelta(microseconds=n)).strftime('%Y%m%dT%H%M%S.%fZ')}_{short}.json"
        if not f.exists():
            break
        n += 1
    ti = DEFAULT_INPUT.get(short, {}) if tool_input is None else tool_input
    f.write_text(json.dumps({"captured_at": iso(at), "tool": f"mcp__{server}__{short}", "tool_input": ti,
                             "response": wrap(response, how)}))
    return f


def write_inbox(inbox, crypto=False, how="raw", at=None, account=ACCT, rhs=RHS, eth_qty="100.00000000",
                quote_ts=None, total="10000.00"):
    """A consistent standard set: 100 ETHA (+ 2 SOL) plus cash."""
    qts = quote_ts or iso(NOW - timedelta(minutes=3))
    acct_in = {"account_number": account}
    cash = "7202.00" if crypto else "7502.50"
    write_cap(inbox, "get_portfolio", portfolio(total=total, cash=cash), acct_in, at, how)
    write_cap(inbox, "get_equity_positions", eq_positions(eq_position("ETHA", eth_qty, avg="22.10")), acct_in, at, how)
    write_cap(inbox, "get_equity_orders", eq_orders(
        eq_order("eq-open-1", "SPY", state="queued", qty="1.00000000", price="601.00000000", ref="ref-stale"),
        eq_order("eq-filled-1", "ETHA", state="filled", filled="10.00000000")), acct_in, at, how)
    write_cap(inbox, "get_equity_quotes", eq_quotes(eq_quote("ETHA", "24.95", "25.00", "24.97", qts),
                                                    eq_quote("SPY", "600.00", "600.50", "600.20", qts)),
              {"symbols": ["ETHA", "SPY"]}, at, how)
    if crypto:
        write_cap(inbox, "get_crypto_positions", cr_positions(cr_position("SOL", "2.000000", "1.500000")),
                  {"rhs_account_number": rhs}, at, how)
        write_cap(inbox, "get_crypto_orders", cr_orders(cr_order("cr-open-1"), rhs=rhs),
                  {"rhs_account_number": rhs, "state_group": "open"}, at, how)
        write_cap(inbox, "get_crypto_quotes", cr_quotes(cr_quote("SOLUSD", "150.00", "150.50",
                                                                 "2026-10-19T10:57:00-04:00")),
                  {"symbols": ["SOL-USD"]}, at, how)
        write_cap(inbox, "get_currency_pairs", pairs(pair()), {"limit": 100}, at, how)


# ------------------------------------------------------------------ tests

def test_official_shapes(tmp_path):
    write_inbox(tmp_path, crypto=True)
    s = sn.build_snapshot(tmp_path, make_cfg(crypto=True), NOW)
    assert s["errors"] == [] and s["warnings"] == []
    assert s["total_value"] == 10000.0 and s["cash"] == 7202.0
    assert s["buying_power"] == 4000.0 and s["crypto_buying_power"] == 4000.0
    assert s["equity_positions"] == {"ETHA": {"qty": 100.0, "sellable": 100.0, "avg_buy_price": 22.1}}
    assert s["crypto_positions"]["SOL"]["qty"] == 2.0 and s["crypto_positions"]["SOL"]["sellable"] == 1.5
    assert "USD" not in s["crypto_positions"]
    q = s["quotes"]["ETHA"]
    assert (q["bid"], q["ask"], q["last"], q["kind"]) == (24.95, 25.0, 24.97, "equity")
    assert q["ts"] == "2026-10-19T14:57:00Z"
    c = s["quotes"]["SOL-USD"]                          # 'SOLUSD' normalised; ET offset honoured
    assert (c["bid"], c["ask"], c["kind"], c["ts"]) == (150.0, 150.5, "crypto", "2026-10-19T14:57:00Z")
    assert c["last"] == pytest.approx(150.25)
    opened = {o["id"]: o for o in s["open_orders"]}
    assert set(opened) == {"eq-open-1", "cr-open-1"}
    assert opened["eq-open-1"]["kind"] == "equity" and opened["eq-open-1"]["ref_id"] == "ref-stale"
    assert opened["eq-open-1"]["qty"] == 1.0 and opened["eq-open-1"]["price"] == 601.0
    assert opened["cr-open-1"]["symbol"] == "SOL" and opened["cr-open-1"]["kind"] == "crypto"
    assert {o["id"] for o in s["orders"]} == {"eq-open-1", "eq-filled-1", "cr-open-1"}
    assert s["pairs"]["SOL-USD"]["asset_increment"] == "0.001" and s["pairs"]["SOL-USD"]["quote_increment"] == "0.05"
    assert s["pairs"]["SOL-USD"]["min_order_size"] == "0.01"
    assert s["account_number"] == ACCT and s["rhs_account_number"] == RHS
    assert s["as_of"] == iso(NOW - timedelta(minutes=2))[:19] + "Z"


@pytest.mark.parametrize("how", ["raw", "text", "structured", "list"])
def test_mcp_wrappers_unwrap_to_the_same_snapshot(tmp_path, how):
    write_inbox(tmp_path / how, crypto=True, how=how)
    write_inbox(tmp_path / "ref", crypto=True)
    cfg = make_cfg(crypto=True)
    got, ref = sn.build_snapshot(tmp_path / how, cfg, NOW), sn.build_snapshot(tmp_path / "ref", cfg, NOW)
    for k in ("errors", "total_value", "buying_power", "equity_positions", "crypto_positions", "quotes",
              "open_orders", "pairs"):
        if k == "quotes":
            assert {s: {f: v for f, v in q.items() if f != "captured_at"} for s, q in got[k].items()} == \
                   {s: {f: v for f, v in q.items() if f != "captured_at"} for s, q in ref[k].items()}
        else:
            assert got[k] == ref[k], k


def test_equity_quote_alternative_shapes(tmp_path):
    ts = iso(NOW - timedelta(minutes=1))
    flat = {"quotes": [{"symbol": "ETHA", "bid_price": "24.95", "ask_price": "25.00", "last_trade_price": "24.97",
                        "venue_bid_time": ts, "venue_ask_time": ts}]}
    assert sn.parse_equity_quotes(flat, NOW)["ETHA"]["bid"] == 24.95
    nodata = {"results": [eq_quote("SPY", "600.00", "600.50", "600.20", ts)]}
    write_cap(tmp_path, "get_equity_quotes", nodata)                           # no {"data": ...} level
    write_cap(tmp_path, "get_equity_quotes", env(flat), at=NOW - timedelta(minutes=1))
    got = sn.build_snapshot(tmp_path, make_cfg(), NOW)["quotes"]
    assert got["SPY"]["ask"] == 600.5 and got["ETHA"]["ask"] == 25.0


def test_newest_capture_per_tool_and_newest_quote_per_symbol(tmp_path):
    write_inbox(tmp_path)
    write_cap(tmp_path, "get_portfolio", portfolio(total="11000.00", cash="8502.50"), at=NOW - timedelta(minutes=1))
    write_cap(tmp_path, "get_equity_quotes", eq_quotes(eq_quote("ETHA", "26.00", "26.05", "26.02",
                                                                iso(NOW - timedelta(seconds=30)))),
              at=NOW - timedelta(seconds=20))
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert s["total_value"] == 11000.0
    assert s["quotes"]["ETHA"]["bid"] == 26.0              # newer capture
    assert s["quotes"]["SPY"]["bid"] == 600.0              # only in the older capture


def test_missing_required_captures(tmp_path):
    write_cap(tmp_path, "get_portfolio", portfolio())
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert any("get_equity_positions" in e for e in s["errors"])
    assert any("get_equity_orders" in e for e in s["errors"])
    assert not any("crypto" in e for e in s["errors"])
    write_inbox(tmp_path / "b")
    s = sn.build_snapshot(tmp_path / "b", make_cfg(crypto=True), NOW)      # crypto vehicle enabled
    assert any("get_crypto_positions" in e for e in s["errors"])
    assert any("get_crypto_orders" in e for e in s["errors"])


def test_stale_capture_is_an_error(tmp_path):
    write_inbox(tmp_path, at=NOW - timedelta(minutes=45))
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert any("get_portfolio" in e and "min old" in e for e in s["errors"])
    s = sn.build_snapshot(tmp_path, make_cfg(snapshot_max_age_min=60), NOW)
    assert s["errors"] == []


def test_account_mismatch_is_an_error_without_leaking_numbers(tmp_path):
    write_inbox(tmp_path, account=OTHER)
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert s["errors"] and all("differs from the configured agentic account" in e for e in s["errors"])
    assert not any(OTHER in e or ACCT in e for e in s["errors"])
    write_inbox(tmp_path / "c", crypto=True, rhs="999999999")
    s = sn.build_snapshot(tmp_path / "c", make_cfg(crypto=True), NOW)
    assert any("get_crypto_positions" in e for e in s["errors"])
    write_inbox(tmp_path / "e", crypto=True)                  # response echo of another account
    write_cap(tmp_path / "e", "get_crypto_orders", cr_orders(rhs="999999999"), at=NOW - timedelta(minutes=1))
    s = sn.build_snapshot(tmp_path / "e", make_cfg(crypto=True), NOW)
    assert any("different account" in e for e in s["errors"])
    write_inbox(tmp_path / "n")
    write_cap(tmp_path / "n", "get_equity_positions", eq_positions(), tool_input={}, at=NOW - timedelta(minutes=1))
    s = sn.build_snapshot(tmp_path / "n", make_cfg(), NOW)
    assert any("cannot verify the account" in e for e in s["errors"])


def test_buying_power_never_uses_margin_leverage(tmp_path):
    p = sn.parse_portfolio(portfolio(bp="2000.00", ubp="1000.00", cbp=None)["data"])
    assert p["buying_power"] == 1000.0 and p["crypto_buying_power"] is None


def test_total_value_cross_check_warning(tmp_path):
    write_inbox(tmp_path, total="10000.00")
    assert sn.build_snapshot(tmp_path, make_cfg(), NOW)["warnings"] == []
    write_inbox(tmp_path / "w", total="12000.00")
    w = sn.build_snapshot(tmp_path / "w", make_cfg(), NOW)["warnings"]
    assert any("differs from total_value" in x for x in w)


def test_crypto_order_symbol_from_currency_pair_id(tmp_path):
    write_inbox(tmp_path, crypto=True)
    write_cap(tmp_path, "get_crypto_orders", cr_orders(cr_order("cr-open-2", with_code=False)),
              at=NOW - timedelta(minutes=1))
    s = sn.build_snapshot(tmp_path, make_cfg(crypto=True), NOW)
    assert [o["symbol"] for o in s["open_orders"] if o["kind"] == "crypto"] == ["SOL"]


def test_filtered_order_lookups_update_but_never_replace_the_listing(tmp_path):
    write_inbox(tmp_path)
    write_cap(tmp_path, "get_equity_orders", eq_orders(eq_order("eq-open-1", "SPY", state="filled", qty="1.00000000",
                                                                filled="1.00000000")),
              tool_input={"account_number": ACCT, "order_id": "eq-open-1"}, at=NOW - timedelta(minutes=1))
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert s["errors"] == [] and s["open_orders"] == []
    assert {o["id"]: o["state"] for o in s["orders"]}["eq-open-1"] == "filled"
    only = tmp_path / "only"
    write_cap(only, "get_portfolio", portfolio())
    write_cap(only, "get_equity_positions", eq_positions())
    write_cap(only, "get_equity_orders", eq_orders(), tool_input={"account_number": ACCT, "symbol": "SPY"})
    s = sn.build_snapshot(only, make_cfg(), NOW)
    assert any("missing capture: get_equity_orders" in e for e in s["errors"])


def test_pagination(tmp_path):
    write_inbox(tmp_path)
    write_cap(tmp_path, "get_equity_positions", eq_positions(eq_position("ETHA", "100"), next_="cur-2"),
              at=NOW - timedelta(minutes=1))
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert any("more pages" in e for e in s["errors"])
    write_cap(tmp_path, "get_equity_positions", eq_positions(eq_position("SPY", "1")),
              tool_input={"account_number": ACCT, "cursor": "cur-2"}, at=NOW - timedelta(seconds=50))
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert not any("more pages" in e for e in s["errors"])
    assert set(s["equity_positions"]) == {"ETHA", "SPY"}


def test_error_response_is_unreadable(tmp_path):
    write_inbox(tmp_path)
    write_cap(tmp_path, "get_portfolio", {"isError": True, "content": [{"type": "text", "text": "upstream timeout"}]},
              at=NOW - timedelta(minutes=1))
    s = sn.build_snapshot(tmp_path, make_cfg(), NOW)
    assert any("get_portfolio" in e and "unreadable" in e for e in s["errors"])


def test_quote_problem_and_mid():
    fresh = {"bid": 10.0, "ask": 10.2, "last": 10.1, "ts": iso(NOW - timedelta(minutes=1))}
    assert sn.quote_problem(fresh, "X", NOW, 15) is None
    assert sn.mid(fresh) == pytest.approx(10.1)
    assert "min old" in sn.quote_problem(dict(fresh, ts=iso(NOW - timedelta(minutes=20))), "X", NOW, 15)
    assert "bid/ask <= 0" in sn.quote_problem(dict(fresh, bid=0.0), "X", NOW, 15)
    assert sn.mid(dict(fresh, bid=0.0)) == 10.1
    assert "no quote" in sn.quote_problem(None, "SOL-USD", NOW, 15)
    assert "get_crypto_quotes" in sn.quote_problem(None, "SOL-USD", NOW, 15)
    assert sn.pair_for("SOL") == sn.pair_for("sol-usd") == "SOL-USD" and sn.code_for("SOL-USD") == "SOL"


def test_dated_and_open_order_listings_are_merged(tmp_path):
    """Regression: only the newest listing was read, so an open gtc crypto order older than the dated window was
    invisible (review p11)."""
    write_inbox(tmp_path, crypto=True)
    old_open = cr_order("cr-old-gtc", created=iso(NOW - timedelta(days=40)))
    dated = {"rhs_account_number": RHS, "created_at_gte": "2026-10-12T00:00:00Z"}
    write_cap(tmp_path, "get_crypto_orders", cr_orders(cr_order("cr-new", state="filled", group="closed",
                                                                filled="2.000")), dated, NOW - timedelta(minutes=2))
    write_cap(tmp_path, "get_crypto_orders", cr_orders(old_open), {"rhs_account_number": RHS, "state_group": "open"},
              NOW - timedelta(minutes=1))
    s = sn.build_snapshot(tmp_path, make_cfg(crypto=True), NOW)
    assert s["errors"] == []
    assert {o["id"] for o in s["open_orders"] if o["kind"] == "crypto"} == {"cr-old-gtc"}
    assert {"cr-new", "cr-old-gtc"} <= {o["id"] for o in s["orders"]}
    write_cap(tmp_path, "get_crypto_orders", cr_orders(), {"rhs_account_number": RHS, "created_at_gte": "2026-01-01"},
              NOW - timedelta(minutes=90))                      # an old listing is ignored, not merged
    assert sn.build_snapshot(tmp_path, make_cfg(crypto=True), NOW)["errors"] == []
