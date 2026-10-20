"""Tests for agentic/hooks: the PreToolUse guard and the PostToolUse capture/journal/approval hook, run as
subprocesses with crafted hook JSON on stdin, plus .claude/settings.json."""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import hooks  # noqa: E402

PRE = REPO / "agentic" / "hooks" / "pre_tool_use.py"
POST = REPO / "agentic" / "hooks" / "post_tool_use.py"
SETTINGS = REPO / ".claude" / "settings.json"
UTC = timezone.utc
ACCT, RHS = "TESTACCT9Z", "778899001"           # fake account numbers
SRV = "mcp__robinhood-trading__"
PLAN_ID = "2026-10-17-abcdef12"
REF = hooks.ref_id_for(PLAN_ID, "ETH|ETHA|buy|0", 1)          # the ref_id a genuine plan gives this order
SOL_REF = hooks.ref_id_for(PLAN_ID, "SOL|SOL|buy|0", 1)
SELL_REF = hooks.ref_id_for(PLAN_ID, "ETH|ETHA|sell|0", 1)


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    d.mkdir()
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(d))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return d


def run(script, state, event=None, raw=None):
    env = dict(os.environ, AGENTIC_STATE_DIR=str(state))
    data = raw if raw is not None else json.dumps(event).encode()
    return subprocess.run([sys.executable, "-I", str(script)], input=data, env=env, capture_output=True, timeout=60)


def ev(short, ti, resp=None, server=SRV):
    e = {"session_id": "t", "cwd": str(REPO), "tool_name": server + short, "tool_input": ti,
         "hook_event_name": "PreToolUse" if resp is None else "PostToolUse"}
    if resp is not None:
        e["tool_response"] = resp
    return e


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def write_config(state, live=True, approvals=True, acct=ACCT, **limits):
    cfg = {"account": {"account_number": acct, "rhs_account_number": RHS, "approvals_required": approvals},
           "live": live, "capital": {"max_usd": 1000},
           "limits": {"max_order_usd": 500, "max_day_usd": 1500, **limits}, "assets": []}
    (state / "config.json").write_text(json.dumps(cfg))


def params(**kw):
    p = {"account_number": ACCT, "symbol": "ETHA", "side": "buy", "type": "limit", "quantity": "12",
         "limit_price": "25.43", "time_in_force": "gfd", "market_hours": "regular_hours", "ref_id": REF}
    p.update(kw)
    return p


def crypto_params(**kw):
    p = {"rhs_account_number": RHS, "symbol": "SOL", "side": "buy", "type": "limit", "quantity": "1.234567",
         "limit_price": "150.25", "time_in_force": "gtc", "ref_id": SOL_REF}
    p.update(kw)
    return p


def plan_order(p=None, notional=305.16, key="ETH|ETHA|buy|0", tool="place_equity_order"):
    return {"key": key, "asset": "ETH", "tool": tool, "preview_tool": "review_equity_order",
            "params": p or params(), "notional_usd": notional, "reason": "test"}


def write_plan(state, orders=None, cancels=None, valid_min=60, **extra):
    now = datetime.now(UTC)
    plan = {"plan_id": PLAN_ID, "signals_date": PLAN_ID[:10], "created_at": iso(now),
            "valid_until": iso(now + timedelta(minutes=valid_min)),
            "live": True, "attempt": 1, "account_number": ACCT, "rhs_account_number": RHS, "capital_usd": 1000.0,
            "orders": [plan_order()] if orders is None else orders, "cancels": cancels or [],
            "skipped": [], "warnings": [], "errors": []}
    plan.update(extra)
    (state / "plan_current.json").write_text(json.dumps(plan))
    return plan


def place_resp(order_id="ord-1", placed_agent="agentic", with_order=True, ref=REF):
    o = {"id": order_id, "ref_id": ref, "symbol": "ETHA", "side": "buy", "type": "limit", "state": "queued",
         "quantity": "12.00000", "cumulative_quantity": "0.00000", "price": "25.43", "placed_agent": placed_agent,
         "agent_initiated": True}
    return {"data": {"order": o if with_order else None}, "guide": "The order has been submitted."}


def journal(state):
    f = state / "journal.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def today():
    return hooks.et_date(datetime.now(UTC)).isoformat()


def day_usd(state):
    return hooks.ledger_get(state / "ledger.json", hooks.et_date(datetime.now(UTC)))


def ready(state, **cfg):
    write_config(state, **cfg)
    return write_plan(state)


# ------------------------------------------------------------------ routing and reads

@pytest.mark.parametrize("tool", ["Bash", "Write", "mcp__github__create_issue", "mcp__foo__robinhood_lookup"])
def test_non_robinhood_tools_pass_untouched(state, tool):
    e = {"tool_name": tool, "tool_input": {"x": 1}, "tool_response": {"y": 2}}
    assert run(PRE, state, e).returncode == 0
    assert run(POST, state, e).returncode == 0
    assert not (state / "hook.log").exists() and not (state / "inbox").exists()


def test_read_passes_and_post_captures_exact_response(state):
    ti = {"account_number": ACCT}
    assert run(PRE, state, ev("get_equity_positions", ti)).returncode == 0      # no config needed for reads
    resp = {"data": {"positions": [{"symbol": "ETHA", "quantity": "12.000000", "shares_available_for_sells": "12"}],
                     "note": "café ✓", "f": 0.1 + 0.2, "big": 12345678901234567890, "none": None},
            "guide": "x"}
    r = run(POST, state, ev("get_equity_positions", ti, resp))
    assert r.returncode == 0 and r.stdout == b""
    files = list((state / "inbox").iterdir())
    assert len(files) == 1
    assert re.fullmatch(r"\d{8}T\d{6}\.\d{6}Z_get_equity_positions\.json", files[0].name)
    cap = json.loads(files[0].read_text(encoding="utf-8"))
    assert cap["tool"] == SRV + "get_equity_positions" and cap["tool_input"] == ti and cap["response"] == resp
    assert files[0].name.startswith(cap["captured_at"].replace("-", "").replace(":", ""))


def test_capture_keeps_mcp_wrapper_verbatim(state):
    text = json.dumps({"data": {"total_value": "100.00"}}, indent=3)
    resp = {"content": [{"type": "text", "text": text}], "structuredContent": None}
    run(POST, state, ev("get_portfolio", {"account_number": ACCT}, resp))
    for short in ("search", "review_equity_order", "preview_crypto_order", "run_scan"):
        run(POST, state, ev(short, {"q": short}, {"data": {}}))
    caps = sorted((state / "inbox").glob("*.json"))
    assert len(caps) == 5
    first = json.loads(caps[0].read_text())
    assert first["response"] == resp and first["response"]["content"][0]["text"] == text


@pytest.mark.parametrize("short", ["get_portfolio", "search", "preview_scan", "run_scan", "get_crypto_quotes",
                                   "get_crypto_account_onboarding_info"])
def test_read_tools_allowed_even_without_config(state, short):
    assert run(PRE, state, ev(short, {"symbols": ["ETHA"]})).returncode == 0


# ------------------------------------------------------------------ place

def test_place_without_plan_blocked(state):
    write_config(state)
    r = run(PRE, state, ev("place_equity_order", params()))
    assert r.returncode == 2 and b"plan_current.json" in r.stderr


def test_place_with_live_false_blocked(state):
    ready(state, live=False)
    r = run(PRE, state, ev("place_equity_order", params()))
    assert r.returncode == 2 and b"live=false" in r.stderr


def test_place_with_no_config_blocked(state):
    write_plan(state)
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2


def test_place_matching_plan_allowed(state):
    ready(state)
    r = run(PRE, state, ev("place_equity_order", params()))
    assert r.returncode == 0, r.stderr
    log = [json.loads(x) for x in (state / "hook.log").read_text().splitlines()]
    assert log[-1]["decision"] == "allow" and log[-1]["ref_id"] == REF and log[-1]["hook"] == "pre"


def test_place_crypto_matching_plan_allowed(state):
    write_config(state)
    write_plan(state, orders=[plan_order(crypto_params(), 185.5, "SOL|SOL|buy|0", "place_crypto_order")])
    assert run(PRE, state, ev("place_crypto_order", crypto_params())).returncode == 0
    assert run(PRE, state, ev("place_equity_order", crypto_params())).returncode == 2     # tool must match too


def test_place_compares_strings_with_whitespace_stripped(state):
    ready(state)
    assert run(PRE, state, ev("place_equity_order", params(quantity=" 12 ", side="buy "))).returncode == 0
    assert run(PRE, state, ev("place_equity_order", params(quantity=12))).returncode == 0
    assert run(PRE, state, ev("place_equity_order", params(quantity="12.0"))).returncode == 2


DROP = object()


@pytest.mark.parametrize("change", [
    {"quantity": "13"}, {"limit_price": "25.44"}, {"symbol": "ETHE"}, {"side": "sell"}, {"type": "market"},
    {"time_in_force": "gtc"}, {"ref_id": "5d0c7d1e-0000-5000-8000-0000000000ff"}, {"ref_id": DROP},
    {"ref_id": ""}, {"dollar_amount": "100.00"}, {"tax_lots": None}, {"account_number": "OTHERACCT1"},
    {"market_hours": DROP},
])
def test_place_any_param_mismatch_blocked(state, change):
    ready(state)
    ti = params()
    for k, v in change.items():
        if v is DROP:
            del ti[k]
        else:
            ti[k] = v                                 # includes extra keys, even null ones
    r = run(PRE, state, ev("place_equity_order", ti))
    assert r.returncode == 2, change
    assert b"BLOCKED" in r.stderr


def test_place_mismatch_reason_names_fields_not_values(state):
    ready(state)
    r = run(PRE, state, ev("place_equity_order", params(quantity="13", limit_price="99.99")))
    assert r.returncode == 2
    assert b"limit_price, quantity" in r.stderr and b"99.99" not in r.stderr and b"13" not in r.stderr


def test_expired_plan_blocked(state):
    write_config(state)
    write_plan(state, valid_min=-1)
    r = run(PRE, state, ev("place_equity_order", params()))
    assert r.returncode == 2 and b"expired" in r.stderr


@pytest.mark.parametrize("extra", [{"account_number": "OTHERACCT1"}, {"rhs_account_number": "111"},
                                   {"live": False}, {"valid_until": None}])
def test_plan_header_problems_blocked(state, extra):
    write_config(state)
    write_plan(state, **extra)
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2


def test_placeholder_account_in_config_blocked(state):
    write_config(state, acct="FILL-IN-PRIVATE-CONFIG-ONLY")
    write_plan(state, account_number="FILL-IN-PRIVATE-CONFIG-ONLY",
               orders=[plan_order(params(account_number="FILL-IN-PRIVATE-CONFIG-ONLY"))])
    r = run(PRE, state, ev("place_equity_order", params(account_number="FILL-IN-PRIVATE-CONFIG-ONLY")))
    assert r.returncode == 2 and b"not set" in r.stderr


def test_max_order_usd_blocked(state):
    write_config(state)
    write_plan(state, orders=[plan_order(notional=500.01)])
    r = run(PRE, state, ev("place_equity_order", params()))
    assert r.returncode == 2 and b"max_order_usd" in r.stderr


def test_max_day_usd_exceeded_via_ledger_blocked(state):
    ready(state)
    (state / "ledger.json").write_text(json.dumps({today(): 1194.85, "2020-01-01": 0.0}))
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2
    (state / "ledger.json").write_text(json.dumps({today(): 1194.84}))
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 0
    (state / "ledger.json").write_text(json.dumps({"2020-01-01": 1500.0}))          # other days do not count
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 0


def test_ledger_formats_of_agentic_ledger_are_read(state):
    ready(state)
    for day in ({"placed_usd": 1200.0, "refs": {"a": 1200.0}}, {"refs": {"a": 700.0, "b": 500.0}},
                [{"notional_usd": 1200.0}]):
        (state / "ledger.json").write_text(json.dumps({today(): day}))
        assert run(PRE, state, ev("place_equity_order", params())).returncode == 2, day
    (state / "ledger.json").write_text(json.dumps({today(): {"placed_usd": 1000.0, "refs": {"a": 1000.0}}}))
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 0


def test_ledger_is_compatible_with_agentic_ledger(state):
    ledger = pytest.importorskip("agentic.ledger")
    ready(state, approvals=False)
    ledger.add_placed(100.0, "earlier-ref", base=state)
    run(POST, state, ev("place_equity_order", params(), place_resp()))
    assert ledger.placed_usd(base=state) == pytest.approx(405.16) == day_usd(state)
    ledger.add_placed(305.16, REF, base=state)                          # the same ref_id counts once
    assert ledger.placed_usd(base=state) == pytest.approx(405.16)
    assert REF in ledger.journal_index(ledger.read_journal(base=state))["ref_ids"]
    ledger.add_placed(1000.0, "big", base=state)
    assert run(PRE, state, ev("place_equity_order", params(ref_id="another"))).returncode == 2


@pytest.mark.parametrize("change, notional", [
    ({"quantity": "1000", "limit_price": "500.00"}, 10.0),          # real notional $500,000
    ({"type": "market", "quantity": "5000"}, 1.0),
    ({"dollar_amount": "100000"}, 1.0),
    ({"market_hours": "all_day_hours"}, 305.16),
    ({"time_in_force": "gtc"}, 305.16),
    ({"stop_price": "20.00"}, 305.16),
])
def test_caps_and_shape_do_not_trust_the_plan(state, change, notional):
    """Regression: the hook capped on the plan's own notional_usd and allowed any params a plan listed (review t2)."""
    write_config(state)
    p = params(**change)
    if change.get("type") == "market":
        p.pop("limit_price")
    write_plan(state, orders=[plan_order(p, notional)])
    (state / "inbox").mkdir()
    (state / "inbox" / "20261019T150000.000000Z_get_equity_quotes.json").write_text(json.dumps(
        {"captured_at": "2026-10-19T15:00:00.000000Z", "tool": SRV + "get_equity_quotes", "tool_input": {},
         "response": {"data": {"results": [{"quote": {"symbol": "ETHA", "bid_price": "24.95", "ask_price": "25.00",
                                                      "last_trade_price": "24.97"}}]}}}))
    r = run(PRE, state, ev("place_equity_order", p))
    assert r.returncode == 2 and b"BLOCKED" in r.stderr, change


@pytest.mark.parametrize("extra", [
    {"live": None}, {"created_at": "2099-01-01T00:00:00Z"}, {"valid_until": "2031-01-01T00:00:00Z"},
    {"valid_until": "2099-01-01T00:00:00-23:59"}, {"plan_id": "anything"}, {"attempt": 2},
])
def test_plan_header_sanity(state, extra):
    write_config(state)
    plan = write_plan(state, **extra)
    if extra.get("live", 1) is None:
        plan.pop("live")
        (state / "plan_current.json").write_text(json.dumps(plan))
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2, extra


@pytest.mark.parametrize("today_value", [{"placed_usd": -100000}, {"placed_usd": float("nan")}, -5,
                                         {"refs": {"a": float("inf")}}])
def test_negative_or_non_finite_ledger_fails_closed(state, today_value):
    ready(state)
    (state / "ledger.json").write_text(json.dumps({today(): today_value}))
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2


def test_market_order_bounded_by_captured_quote_and_hours(state, monkeypatch):
    sys.path.insert(0, str(REPO / "agentic" / "hooks"))
    import pre_tool_use as pre
    pre.H = hooks
    write_config(state)
    mkt = params(type="market", quantity="10")
    mkt.pop("limit_price")
    open_t = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)                 # Monday 11:00 ET
    write_plan(state, orders=[plan_order(mkt, 240.0)], created_at=iso(open_t - timedelta(minutes=5)),
               valid_until=iso(open_t + timedelta(hours=1)))
    from agentic.config import load_config, paths
    cfg, p = load_config(), paths()
    monkeypatch.setattr(hooks, "ledger_get", lambda *a: 0.0)
    ok, why = pre._check_trade(cfg, p, "place_equity_order", mkt, open_t)
    assert not ok and "no captured quote" in why
    (state / "inbox").mkdir()
    (state / "inbox" / "20261019T145900.000000Z_get_equity_quotes.json").write_text(json.dumps(
        {"response": {"data": {"results": [{"quote": {"symbol": "ETHA", "bid_price": "24.95", "ask_price": "25.10"}}]}}}))
    plan = json.loads((state / "plan_current.json").read_text())
    plan.update(created_at=iso(open_t - timedelta(minutes=5)), valid_until=iso(open_t + timedelta(hours=1)))
    (state / "plan_current.json").write_text(json.dumps(plan))
    assert pre._check_trade(cfg, p, "place_equity_order", mkt, open_t)[0]
    late = datetime(2026, 10, 19, 19, 50, tzinfo=UTC)                   # 15:50 ET: open, but past the cutoff
    plan.update(created_at=iso(late - timedelta(minutes=5)), valid_until=iso(late + timedelta(hours=1)))
    (state / "plan_current.json").write_text(json.dumps(plan))
    ok, why = pre._check_trade(cfg, p, "place_equity_order", mkt, late)
    assert not ok and "15:45" in why
    write_plan(state, orders=[plan_order(mkt, 240.0)], created_at=iso(open_t), valid_until=iso(open_t + timedelta(hours=1)))
    write_config(state, max_order_usd=250)
    ok, why = pre._check_trade(load_config(), p, "place_equity_order", mkt, open_t)
    assert not ok and "251.00" in why                                   # 10 x the captured ask 25.10


def test_config_live_must_be_a_real_boolean(state):
    """Regression: "live": "false" (quoted) meant live (review t2)."""
    write_plan(state)
    raw = json.loads(json.dumps({"account": {"account_number": ACCT, "rhs_account_number": RHS}, "live": "false",
                                 "capital": {"max_usd": 1000}, "assets": []}))
    (state / "config.json").write_text(json.dumps(raw))
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2


def test_relative_state_dir_resolves_against_the_repo(state, tmp_path):
    """Regression: a relative AGENTIC_STATE_DIR followed the hook's cwd (review t4)."""
    from agentic import config
    rel = os.path.relpath(state, REPO)
    ready(state)
    (state / "STOP").write_text("x\n")
    other = tmp_path / "elsewhere"
    (other / rel).mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, AGENTIC_STATE_DIR=rel)
    r = subprocess.run([sys.executable, "-I", str(PRE)], input=json.dumps(ev("place_equity_order", params())).encode(),
                       env=env, cwd=other, capture_output=True, timeout=60)
    assert r.returncode == 2 and b"STOP" in r.stderr
    old = os.environ.get("AGENTIC_STATE_DIR")
    try:
        os.environ["AGENTIC_STATE_DIR"] = rel
        assert config.state_dir() == state.resolve()
    finally:
        os.environ["AGENTIC_STATE_DIR"] = old


def test_corrupt_ledger_or_journal_fails_closed(state):
    ready(state)
    for bad in ("{not json", "[1, 2]", json.dumps({today(): {"placed_usd": "lots"}})):
        (state / "ledger.json").write_text(bad)
        assert run(PRE, state, ev("place_equity_order", params())).returncode == 2, bad
    (state / "ledger.json").unlink()
    (state / "journal.jsonl").write_text('{"event": "place"}\n{truncated')
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2


def test_ref_id_already_placed_blocked_but_transport_retry_allowed(state):
    ready(state, approvals=False)
    assert run(POST, state, ev("place_equity_order", params(), {"isError": True, "content": [
        {"type": "text", "text": "Error: upstream timeout"}]})).returncode == 0
    assert journal(state)[-1]["error"] and journal(state)[-1]["state"] == "error"
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 0         # retry of a failure
    run(POST, state, ev("place_equity_order", params(), place_resp()))
    r = run(PRE, state, ev("place_equity_order", params()))
    assert r.returncode == 2 and b"already placed" in r.stderr


# ------------------------------------------------------------------ flags and cancels

def test_stop_blocks_place_but_allows_cancel_of_journaled_order(state):
    ready(state, approvals=False)
    run(POST, state, ev("place_equity_order", params(), place_resp(order_id="ord-77")))
    (state / "STOP").write_text("manual\n")
    r = run(PRE, state, ev("place_equity_order", params(ref_id="5d0c7d1e-0000-5000-8000-0000000000aa")))
    assert r.returncode == 2 and b"STOP" in r.stderr
    assert run(PRE, state, ev("cancel_equity_order", {"account_number": ACCT, "order_id": "ord-77"})).returncode == 0
    for ti in ({"account_number": ACCT, "order_id": "someone-elses"},
               {"account_number": "OTHERACCT1", "order_id": "ord-77"}, {"account_number": ACCT}):
        assert run(PRE, state, ev("cancel_equity_order", ti)).returncode == 2


def test_cancel_listed_in_plan_allowed(state):
    write_config(state)
    write_plan(state, cancels=[{"tool": "cancel_crypto_order", "reason": "stale",
                                "params": {"rhs_account_number": RHS, "order_id": "old-1"}}])
    assert run(PRE, state, ev("cancel_crypto_order", {"rhs_account_number": RHS, "order_id": "old-1"})).returncode == 0
    assert run(PRE, state, ev("cancel_equity_order", {"account_number": ACCT, "order_id": "old-1"})).returncode == 2
    (state / "plan_current.json").write_text("{corrupt")
    assert run(PRE, state, ev("cancel_crypto_order", {"rhs_account_number": RHS, "order_id": "old-1"})).returncode == 2


@pytest.mark.parametrize("flag", ["FLATTEN", "BLOCK_BUYS"])
def test_sell_only_flags(state, flag):
    sell = params(side="sell", quantity="5", limit_price="25.10", ref_id=SELL_REF)
    write_config(state)
    write_plan(state, orders=[plan_order(), plan_order(sell, 125.5, "ETH|ETHA|sell|0")])
    (state / flag).write_text("")
    r = run(PRE, state, ev("place_equity_order", params()))
    assert r.returncode == 2 and flag.encode() in r.stderr
    assert run(PRE, state, ev("place_equity_order", sell)).returncode == 0


# ------------------------------------------------------------------ other tools and malformed input

@pytest.mark.parametrize("short", ["create_alert", "place_option_order", "review_option_order", "exercise_option",
                                   "update_watchlist", "create_scan", "mark_alerts_read", "brand_new_tool", ""])
def test_unknown_and_unused_write_tools_blocked(state, short):
    ready(state)
    for server in (SRV, "mcp__Robinhood__", "mcp__robinhood-for-agents__"):
        assert run(PRE, state, ev(short, params(), server=server)).returncode == 2


@pytest.mark.parametrize("raw", [
    b'{"tool_name": "mcp__robinhood-trading__place_equity_order", "tool_input": {"symbol": "ETHA"',
    b"\xff\xfe not json", b"", b"[1, 2]", b'{"tool_input": {}}',
    json.dumps({"tool_name": SRV + "place_equity_order", "tool_input": "symbol=ETHA"}).encode(),
    json.dumps({"tool_name": SRV + "cancel_equity_order", "tool_input": ["x"]}).encode(),
])
def test_malformed_stdin_blocks_trade_tools(state, raw):
    ready(state)
    r = run(PRE, state, raw=raw)
    assert r.returncode == 2 and b"BLOCKED" in r.stderr
    assert run(POST, state, raw=raw).returncode == 0                               # the post hook never blocks


def test_simulate_requires_configured_account(state):
    write_config(state, live=False)
    prev = {k: v for k, v in params().items() if k != "ref_id"}
    assert run(PRE, state, ev("review_equity_order", prev)).returncode == 0
    assert run(PRE, state, ev("review_equity_order", dict(prev, account_number="OTHERACCT1"))).returncode == 2
    assert run(PRE, state, ev("preview_crypto_order", {"rhs_account_number": RHS, "symbol": "SOL"})).returncode == 0
    assert run(PRE, state, ev("preview_crypto_order", {"symbol": "SOL"})).returncode == 2


# ------------------------------------------------------------------ post: journal, ledger, approvals

def test_post_journals_place_adds_ledger_and_stops_on_unapproved_agent_order(state):
    ready(state, approvals=True)
    (state / "ledger.json").write_text(json.dumps({today(): 100.0}))
    r = run(POST, state, ev("place_equity_order", params(), place_resp(order_id="ord-9")))
    assert r.returncode == 0
    e = journal(state)[-1]
    assert e["event"] == "place" and e["tool"] == "place_equity_order" and e["plan_id"] == "2026-10-17-abcdef12"
    assert e["key"] == "ETH|ETHA|buy|0" and e["ref_id"] == REF and e["order_id"] == "ord-9" and e["state"] == "queued"
    assert e["placed_agent"] == "agentic" and e["agent_initiated"] is True and e["error"] is None
    assert "account_number" not in e["params"] and e["params"]["quantity"] == "12"
    assert day_usd(state) == pytest.approx(405.16)
    assert "went live without approval" in (state / "STOP").read_text()
    out = json.loads(r.stdout)
    assert "AGENTIC STOP" in out["systemMessage"] and out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert b"AGENTIC STOP" in r.stderr
    assert run(PRE, state, ev("place_equity_order", params(ref_id="another-ref"))).returncode == 2


def test_post_unwraps_mcp_content_for_the_approval_check(state):
    ready(state)
    wrapped = {"content": [{"type": "text", "text": json.dumps(place_resp(order_id="ord-w"))}]}
    run(POST, state, ev("place_equity_order", params(), wrapped))
    assert (state / "STOP").exists() and journal(state)[-1]["order_id"] == "ord-w"
    cap = json.loads(next((state / "inbox").glob("*_place_equity_order.json")).read_text())
    assert cap["response"] == wrapped


def test_post_null_order_is_a_pending_proposal(state):
    ready(state, approvals=True)
    r = run(POST, state, ev("place_equity_order", params(), place_resp(with_order=False)))
    assert r.returncode == 0 and r.stdout == b""
    e = journal(state)[-1]
    assert e["state"] == "proposal_pending_approval?" and e["order_id"] is None and e["error"] is None
    assert not (state / "STOP").exists()
    assert day_usd(state) == pytest.approx(305.16)
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 2          # never re-send a proposal


def test_post_no_stop_when_approvals_off(state):
    ready(state, approvals=False)
    run(POST, state, ev("place_equity_order", params(), place_resp()))
    assert not (state / "STOP").exists()
    run(POST, state, ev("place_equity_order", params(ref_id="r2"), place_resp(placed_agent="user", ref="r2")))
    assert "matches no plan order" in (state / "STOP").read_text()      # r2 is not in the plan: STOP for that
    assert "without approval" not in (state / "STOP").read_text()


@pytest.mark.parametrize("agent", ["agentic", "Agentic", "AGENTIC", "agentic ", "", "mcp", "api", "user", None])
def test_post_any_live_order_in_a_place_result_stops_when_approvals_required(state, agent):
    """Regression: only placed_agent None/'agentic' used to STOP (review t3_post)."""
    ready(state, approvals=True)
    r = run(POST, state, ev("place_equity_order", params(), place_resp(placed_agent=agent)))
    assert r.returncode == 0 and b"AGENTIC STOP" in r.stderr and json.loads(r.stdout)["systemMessage"]
    assert "went live without approval" in (state / "STOP").read_text()


def test_post_order_fields_without_data_order_is_not_a_proposal(state):
    """Regression: {data: {id, ref_id, state, placed_agent}} was journaled as a pending proposal (review t7)."""
    ready(state, approvals=True)
    resp = {"data": {"id": "ord-x", "ref_id": REF, "state": "queued", "placed_agent": "agentic"}, "guide": "g"}
    r = run(POST, state, ev("place_equity_order", params(), resp))
    assert journal(state)[-1]["state"] == "unrecognised_response"
    assert "unrecognised place response" in (state / "STOP").read_text() and b"AGENTIC STOP" in r.stderr


def orders_listing(*rows, crypto=False):
    return {"data": {("results" if crypto else "orders"): list(rows), "next": ""}, "guide": "g"}


def listed(oid="ord-r1", ref=None, agent="user", initiated=True, state="filled", created=None):
    return {"id": oid, "ref_id": ref, "symbol": "ETHA", "side": "buy", "state": state, "quantity": "12",
            "cumulative_quantity": "12", "placed_agent": agent, "agent_initiated": initiated,
            "created_at": created or iso(datetime.now(UTC))}


def test_readback_of_our_ref_or_direct_agent_order_stops(state):
    """Regression: get_*_orders captures were never checked for orders that skipped the approval (review t7)."""
    ready(state, approvals=True)
    run(POST, state, ev("place_equity_order", params(), place_resp(with_order=False)))     # a pending proposal
    assert not (state / "STOP").exists()
    ti = {"account_number": ACCT, "created_at_gte": "2026-10-10T00:00:00Z"}
    approved = listed("ord-ok", ref="approval-uuid-1", agent="user")        # approved in the app: fine
    old_direct = listed("ord-old", agent="agentic", created="2026-01-02T15:00:00Z")
    r = run(POST, state, ev("get_equity_orders", ti, orders_listing(approved, old_direct)))
    assert r.returncode == 0 and r.stdout == b"" and not (state / "STOP").exists()
    r = run(POST, state, ev("get_equity_orders", ti, orders_listing(approved, listed("ord-ours", ref=REF))))
    assert b"AGENTIC STOP" in r.stderr and "own ref_id" in (state / "STOP").read_text()
    (state / "STOP").unlink()
    r = run(POST, state, ev("get_equity_orders", ti, orders_listing(approved, listed("ord-ours", ref=REF))))
    assert not (state / "STOP").exists()                                   # reported once per order
    r = run(POST, state, ev("get_crypto_orders", {"rhs_account_number": RHS},
                            orders_listing(dict(listed("c-9", agent=None), initiator_type="agentic_trading",
                                                currency_code="SOL"), crypto=True)))
    assert "submitted directly" in (state / "STOP").read_text()
    write_config(state, approvals=False)
    (state / "STOP").unlink()
    run(POST, state, ev("get_equity_orders", ti, orders_listing(listed("ord-new", agent="agentic"))))
    assert not (state / "STOP").exists()


def test_post_crypto_order_without_placed_agent_stops(state):
    write_config(state)
    write_plan(state, orders=[plan_order(crypto_params(), 185.5, "SOL|SOL|buy|0", "place_crypto_order")])
    resp = {"data": {"order": {"id": "c-1", "currency_code": "SOL", "state": "unconfirmed",
                               "initiator_type": "api_trading"}, "estimated_fee": "0"}, "guide": "g"}
    run(POST, state, ev("place_crypto_order", crypto_params(), resp))
    assert (state / "STOP").exists()
    assert journal(state)[-1]["initiator_type"] == "api_trading"


def test_post_error_response_not_counted(state):
    ready(state)
    run(POST, state, ev("place_equity_order", params(), {"error": f"account {ACCT} is not agentic_allowed"}))
    e = journal(state)[-1]
    assert e["state"] == "error" and ACCT not in e["error"]
    assert not (state / "ledger.json").exists() and not (state / "STOP").exists()


def test_post_unreadable_place_response_stops_when_approvals_required(state):
    ready(state)
    run(POST, state, ev("place_equity_order", params(), "something unexpected"))
    assert journal(state)[-1]["state"] == "unknown_response"
    assert "approval cannot be confirmed" in (state / "STOP").read_text()
    assert day_usd(state) == pytest.approx(305.16)


def test_post_stop_warning_survives_a_failed_stop_write(state):
    """Regression: an unwritable STOP silenced the warning (review t3_post)."""
    ready(state, approvals=True)
    (state / "STOP").mkdir()
    r = run(POST, state, ev("place_equity_order", params(), place_resp()))
    assert r.returncode == 0 and b"AGENTIC STOP" in r.stderr and b"could NOT be written" in r.stderr
    assert "could NOT be written" in json.loads(r.stdout)["systemMessage"]


def test_post_lone_surrogates_keep_journal_capture_and_stop(state):
    """Regression: a lone surrogate in a response dropped the journal entry and the capture (review t6)."""
    ready(state, approvals=True)
    resp = place_resp()
    resp["data"]["order"]["state"] = "queued\udcff"
    raw = json.dumps(ev("place_equity_order", params(), resp)).encode()    # a legal JSON escape
    r = run(POST, state, raw=raw)
    assert r.returncode == 0 and b"AGENTIC STOP" in r.stderr
    assert journal(state)[-1]["order_id"] == "ord-1" and (state / "STOP").read_text().strip()
    assert len(list((state / "inbox").glob("*_place_equity_order.json"))) == 1


def test_post_failure_event_journals_unknown_place_and_counts_it(state):
    """Regression: failed or timed-out place calls left no trace (review: PostToolUseFailure)."""
    ready(state, approvals=True)
    e = ev("place_equity_order", params())
    e.update(hook_event_name="PostToolUseFailure", error="MCP error -32001: Request timed out")
    r = run(POST, state, e)
    assert r.returncode == 0 and b"may still exist" in r.stderr
    assert json.loads(r.stdout)["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"
    j = journal(state)[-1]
    assert j["state"] == "failed_or_unknown" and j["ref_id"] == REF and "timed out" in j["error"]
    assert day_usd(state) == pytest.approx(305.16) and not list((state / "inbox").glob("*.json"))
    assert run(PRE, state, ev("place_equity_order", params())).returncode == 0       # same ref_id: idempotent
    run(POST, state, ev("place_equity_order", params(), place_resp(with_order=False)))
    assert day_usd(state) == pytest.approx(305.16)                                # counted once


def test_post_tool_outside_allowlist_that_ran_writes_stop(state):
    write_config(state)
    r = run(POST, state, ev("place_option_order", {"account_number": ACCT}, {"data": {}}))
    assert b"outside the allowlist" in r.stderr and "outside the allowlist" in (state / "STOP").read_text()


def test_post_journals_cancel(state):
    ready(state, approvals=False)
    run(POST, state, ev("place_equity_order", params(), place_resp(order_id="ord-5")))
    run(POST, state, ev("cancel_equity_order", {"account_number": ACCT, "order_id": "ord-5"},
                        {"data": {"accepted": True}, "guide": "g"}))
    e = journal(state)[-1]
    assert e["event"] == "cancel" and e["order_id"] == "ord-5" and e["state"] == "cancel_requested"
    assert e["key"] == "ETH|ETHA|buy|0" and e["ref_id"] == REF and "account_number" not in e["params"]
    assert day_usd(state) == pytest.approx(305.16)    # cancels add nothing


def test_hook_log_has_no_account_numbers(state):
    ready(state, approvals=True)
    calls = [(PRE, ev("get_portfolio", {"account_number": ACCT})),
             (PRE, ev("place_equity_order", params(account_number="OTHERACCT1"))),
             (PRE, ev("place_equity_order", params(quantity="13"))),
             (PRE, ev("review_equity_order", {"account_number": "999888777666"})),
             (PRE, ev("place_equity_order", {"account_number": ACCT, "999888777666": "x"})),
             (PRE, ev("place_equity_order", params())),
             (POST, ev("place_equity_order", params(), place_resp())),
             (POST, ev("place_equity_order", params(), {"error": f"bad account {RHS} / {ACCT}"})),
             (PRE, ev("cancel_crypto_order", {"rhs_account_number": RHS, "order_id": "x"}))]
    for script, e in calls:
        run(script, state, e)
    log = (state / "hook.log").read_text()
    assert len(log.splitlines()) >= len(calls)
    for secret in (ACCT, RHS, "OTHERACCT1", "999888777666"):
        assert secret not in log
    assert ACCT not in (state / "journal.jsonl").read_text()


# ------------------------------------------------------------------ settings.json

def test_settings_registers_hooks_and_denies_unused_write_tools():
    s = json.loads(SETTINGS.read_text())
    for event, script in (("PreToolUse", PRE), ("PostToolUse", POST), ("PostToolUseFailure", POST)):
        (entry,) = s["hooks"][event]
        m = re.compile(entry["matcher"])
        for tool in ("mcp__robinhood-trading__place_equity_order", "mcp__Robinhood__get_portfolio",
                     "mcp__robinhood-for-agents__cancel_crypto_order", "mcp__claude_ai_Robinhood__search"):
            assert m.search(tool) and hooks.is_robinhood(tool), tool
        for tool in ("Bash", "mcp__github__create_issue", "Edit"):
            assert not m.search(tool)
        (h,) = entry["hooks"]
        want = f'"${{AGENTIC_PYTHON:-python3}}" -I "${{CLAUDE_PROJECT_DIR}}/agentic/hooks/{script.name}"'
        assert h["type"] == "command" and "shell" not in h        # Git Bash on Windows, sh elsewhere
        assert h["command"] == (want + " || exit 2" if script == PRE else want), h["command"]
    deny = s["permissions"]["deny"]
    unused = ["place_option_order", "review_option_order", "cancel_option_order", "exercise_option",
              "cancel_option_exercise", "create_alert", "update_alert", "delete_alert", "mark_alerts_read",
              "create_scan", "update_scan_config", "update_scan_filters", "create_watchlist", "update_watchlist",
              "add_to_watchlist", "remove_from_watchlist", "add_option_to_watchlist", "remove_option_from_watchlist",
              "follow_watchlist", "unfollow_watchlist"]
    servers = ("robinhood-trading", "Robinhood", "robinhood-for-agents", "claude_ai_Robinhood")
    guard = {"Bash(*agentic resume*)", "Bash(*agentic*--replan*)",     # any interpreter path in front
             "Edit(private/agentic/**)", "Bash(*agentic*init*--update*)", "Bash(*private/agentic/STOP*)", "Bash(*private/agentic/FLATTEN*)", "Bash(*private/agentic/BLOCK_BUYS*)", "Bash(*private/agentic/hook.log*)", "Bash(*private/agentic/journal*)", "Bash(*private/agentic/ledger*)", "Bash(*rm *private/agentic*)", "Bash(*mv *private/agentic*)"}
    expected = {f"mcp__{srv}__{t}" for srv in servers for t in unused} | guard
    assert set(deny) == expected and len(deny) == 92
    assert not any(d.startswith("Write(") for d in deny)    # Claude Code: only Edit(path) rules cover file edits
    used = ("place_equity", "place_crypto", "cancel_equity", "cancel_crypto", "get_", "review_equity", "preview_crypto")
    assert not any(t in d for d in deny for t in used)
    for script in (PRE, POST):
        assert hooks.RH_TOOL.pattern == re.search(r'RH_TOOL = re.compile\(r"([^"]+)"', script.read_text()).group(1)


if os.name == "nt":                                # Claude Code runs hooks in Git Bash (never WSL's bash.exe)
    from agentic.doctor import find_git_bash
    SHELL = find_git_bash()[0]
else:
    SHELL = shutil.which("bash") or ("/bin/sh" if os.path.exists("/bin/sh") else None)


@pytest.mark.skipif(SHELL is None, reason="no bash or sh")
def test_settings_commands_run_through_the_shell(state):
    s = json.loads(SETTINGS.read_text())
    pre_cmd = s["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    env = {k: v for k, v in os.environ.items() if k != "AGENTIC_PYTHON"}
    env.update(AGENTIC_STATE_DIR=str(state), CLAUDE_PROJECT_DIR=str(REPO))

    def sh(cmd, event, **extra):
        return subprocess.run([SHELL, "-c", cmd], input=json.dumps(event).encode(), env=dict(env, **extra),
                              capture_output=True, timeout=60).returncode
    if shutil.which("python3"):                                           # AGENTIC_PYTHON unset: python3 on PATH
        assert sh(pre_cmd, ev("get_portfolio", {"account_number": ACCT})) == 0
    assert sh(pre_cmd, ev("get_portfolio", {"account_number": ACCT}), AGENTIC_PYTHON=sys.executable) == 0
    assert sh(pre_cmd, ev("place_equity_order", params()), AGENTIC_PYTHON=sys.executable) == 2
    assert sh(pre_cmd.replace("pre_tool_use.py", "missing.py"), ev("get_portfolio", {}),
              AGENTIC_PYTHON=sys.executable) == 2                         # broken install
    missing = str(state / "no-such-python.exe")
    assert sh(pre_cmd, ev("get_portfolio", {}), AGENTIC_PYTHON=missing) == 2       # wrong AGENTIC_PYTHON: fail closed
    post_cmd = s["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    assert sh(post_cmd, ev("get_portfolio", {"account_number": ACCT}, {"data": {}}), AGENTIC_PYTHON=sys.executable) == 0
    assert len(list((state / "inbox").glob("*_get_portfolio.json"))) == 1
    assert sh(post_cmd, ev("get_portfolio", {}, {"data": {}}), AGENTIC_PYTHON=missing) not in (0, 2)  # non-blocking


@pytest.mark.skipif(SHELL is None or os.name == "nt", reason="needs bash/sh and symlinks")
def test_settings_commands_survive_spaces_in_paths(state, tmp_path):
    """Windows user folders often contain a space (C:/Users/First Last/...): both the project dir and AGENTIC_PYTHON
    are quoted in the hook command."""
    s = json.loads(SETTINGS.read_text())
    pre_cmd = s["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    spaced = tmp_path / "First Last"
    spaced.mkdir()
    (spaced / "moneyline upgrade").symlink_to(REPO, target_is_directory=True)
    (spaced / "py thon").symlink_to(sys.executable)
    env = dict(os.environ, AGENTIC_STATE_DIR=str(state), CLAUDE_PROJECT_DIR=str(spaced / "moneyline upgrade"),
               AGENTIC_PYTHON=str(spaced / "py thon"))
    for event, want in ((ev("get_portfolio", {"account_number": ACCT}), 0), (ev("place_equity_order", params()), 2)):
        r = subprocess.run([SHELL, "-c", pre_cmd], input=json.dumps(event).encode(), env=env, capture_output=True,
                           timeout=60)
        assert r.returncode == want, r.stderr
    assert "BLOCKED by agentic hook (place_equity_order)" in r.stderr.decode()


# ------------------------------------------------------------------ helpers

def test_et_date_fallback_matches_zoneinfo():
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    t = datetime(2024, 1, 1, tzinfo=UTC)
    while t < datetime(2028, 1, 1, tzinfo=UTC):
        assert t + hooks._et_offset_manual(t) == t.astimezone(et).replace(tzinfo=None).replace(tzinfo=UTC), t
        t += timedelta(minutes=30)


def test_norm_unwrap_and_classify():
    assert hooks.norm(" 12 ") == "12" == hooks.norm(12) and hooks.norm(None) == "null" and hooks.norm(True) == "true"
    obj = {"data": {"order": None}}
    text = [{"type": "text", "text": json.dumps(obj)}]
    for wrapped in (obj, json.dumps(obj), {"structuredContent": obj}, {"content": text}, text):
        assert hooks.unwrap(wrapped) == (obj, None)
    assert hooks.unwrap({"isError": True, "content": [{"type": "text", "text": "nope"}]}) == (None, "nope")
    assert hooks.unwrap("Error: bad") == (None, "Error: bad")
    assert hooks.unwrap("weird") == (None, None)
    assert [hooks.classify(s) for s in ("get_accounts", "search", "review_equity_order", "place_crypto_order",
                                        "cancel_equity_order", "review_option_order", "get")] == \
        ["read", "read", "simulate", "trade", "cancel", "other", "other"]
    assert hooks.scrub(f"x {ACCT} 1234567 12345", [ACCT]) == "x *** *** 12345"


@pytest.mark.skipif(SHELL is None, reason="no bash or sh")
def test_config_and_plan_saved_with_a_utf8_bom_are_read(state):
    """Regression: a config.json saved as "UTF-8 with BOM" (a Windows Notepad option) made the hook block every
    preview and place with a JSONDecodeError. The BOM is skipped; every check still applies. Run through the real
    settings command, as Claude Code does."""
    ready(state)
    for name in ("config.json", "plan_current.json", "ledger.json"):
        f = state / name
        if name == "ledger.json":
            f.write_text(json.dumps({today(): 100.0}))
        f.write_bytes(b"\xef\xbb\xbf" + f.read_bytes())
    pre_cmd = json.loads(SETTINGS.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    env = dict(os.environ, AGENTIC_STATE_DIR=str(state), CLAUDE_PROJECT_DIR=str(REPO), AGENTIC_PYTHON=sys.executable)

    def sh(event):
        return subprocess.run([SHELL, "-c", pre_cmd], input=json.dumps(event).encode(), env=env, capture_output=True,
                              timeout=60)
    prev = {k: v for k, v in params().items() if k != "ref_id"}
    for event, want in ((ev("review_equity_order", prev), 0), (ev("place_equity_order", params()), 0),
                        (ev("place_equity_order", params(quantity="13")), 2),               # not the plan's order
                        (ev("review_equity_order", dict(prev, account_number="OTHERACCT1")), 2)):
        r = sh(event)
        assert r.returncode == want, r.stderr
        assert b"BOM" not in r.stderr and b"hook error" not in r.stderr
    write_config(state, max_day_usd=350)                             # the ledger's 100 still counts with a BOM
    f = state / "config.json"
    f.write_bytes(b"\xef\xbb\xbf" + f.read_bytes())
    r = sh(ev("place_equity_order", params()))
    assert r.returncode == 2 and b"max_day_usd" in r.stderr, r.stderr
