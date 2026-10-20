"""Defences after the first live day, when Robinhood executed an agent order directly, without the user's approval,
once 5 proposals were already pending: the per-plan order cap (planner), the pending-proposal guard (PreToolUse
hook), re-planning the deferred rest, `resume` records in hook.log, the STOP / APPROVAL BYPASS banner in `status`
and the digest, and get_currency_pairs paging. Synthetic data only; state under tmp_path; no network."""
import io
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import cli, hooks, ledger, planner, universe  # noqa: E402
from agentic import config as cfgmod  # noqa: E402
from agentic import snapshot as sn  # noqa: E402
from agentic.config import ConfigError, paths, validate  # noqa: E402
from agentic.hooks import post_tool_use  # noqa: E402
from tests import test_agentic_hooks as th  # noqa: E402
from tests.test_agentic_planner import fresh, owned, quote, snap  # noqa: E402
from tests.test_agentic_snapshot import make_cfg as snap_cfg  # noqa: E402
from tests.test_agentic_snapshot import write_cap  # noqa: E402
from tests.test_agentic_universe import pair_row, uni_cfg  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)          # Monday 11:00 ET, market open
ACCT, RHS = "TESTACCT01", "100000001"                     # synthetic, as in test_agentic_planner
BYPASS = "an agent order went live without approval (placed_agent=agentic, state=unconfirmed)"
PROPOSAL = {"data": {"order": None}, "guide": "The proposal is waiting for the user's approval."}


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    d.mkdir()
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(d))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return d


def env(data):
    return {"data": data, "guide": "synthetic guide text"}


# ------------------------------------------------------------------ config

def test_new_limits_defaults_validation_and_example():
    lim = validate({"capital": {"max_usd": 100}})["limits"]
    assert lim["max_orders_per_plan"] == 4 and lim["max_pending_proposals"] == 4
    for k in ("max_orders_per_plan", "max_pending_proposals"):
        for bad in (0, 21, -1, 2.5, "4", True, None):
            with pytest.raises(ConfigError, match=f"limits.{k} must be a whole number from 1 to 20"):
                validate({"capital": {"max_usd": 100}, "limits": {k: bad}})
        assert validate({"capital": {"max_usd": 100}, "limits": {k: 1}})["limits"][k] == 1
        assert validate({"capital": {"max_usd": 100}, "limits": {k: 20}})["limits"][k] == 20
    raw = json.loads(cfgmod.EXAMPLE.read_text())
    assert raw["limits"]["max_orders_per_plan"] == 4 and raw["limits"]["max_pending_proposals"] == 4
    note = raw["limits"]["_comment_approval_caps"]
    assert "robot icon" in note and "5 proposals" in note and "deferred" in note
    assert validate(raw)["limits"]["max_pending_proposals"] == 4


def test_init_update_adds_the_new_limits(state):
    raw = json.loads(cfgmod.EXAMPLE.read_text())
    for k in ("max_orders_per_plan", "max_pending_proposals", "_comment_approval_caps"):
        del raw["limits"][k]
    f = state / "config.json"
    f.write_text(json.dumps(raw))
    merged, added = cli.init_update(f)
    assert {"limits.max_orders_per_plan", "limits.max_pending_proposals"} <= set(added)
    assert merged["limits"]["max_orders_per_plan"] == 4 and "_comment_approval_caps" in merged["limits"]


# ------------------------------------------------------------------ 1. the plan cap

SYMS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"]


def eq_asset(sym):
    return {"name": f"S{sym}", "class": "equity", "enabled": True, "alloc_frac": 0.1, "mode": "immediate",
            "signal": {"source": "computed", "feed": "robinhood", "symbol": sym},
            "vehicle": {"type": "equity", "symbol": sym, "fractional": False}}


def cap_cfg(syms, **limits):
    lim = {"max_order_usd": 5000, "max_day_usd": 20000, **limits}
    return validate({"account": {"account_number": ACCT, "rhs_account_number": RHS}, "capital": {"max_usd": 10000},
                     "limits": lim, "assets": [eq_asset(s) for s in syms]})


def eq_sig(sym, tf):
    bar = "2026-10-16"
    return {"name": f"S{sym}", "class": "equity", "target_frac": tf, "prev_target_frac": None, "bar_date": bar,
            "close": 20.0, "tranches": [fresh(tf > 0, bar)], "errors": [], "warnings": []}


def cap_plan(cfg, buys=(), sells=(), open_orders=(), journal=None):
    q = {s: quote(20.00, 20.05) for s in SYMS}
    s = snap(quotes=q, eq={sym: {"qty": 10.0, "sellable": 10.0, "avg_buy_price": 19.0} for sym in sells},
             open_orders=open_orders)
    sigs = [eq_sig(x, 1.0) for x in buys] + [eq_sig(x, 0.0) for x in sells]
    return planner.make_plan({"date": "2026-10-19", "generated_at": "2026-10-19T01:00:00Z", "assets": sigs}, s, cfg,
                             NOW, 1, {}, placed_today_usd=0.0, journal=journal or [], sleeve=owned(s))


def deferred(plan):
    return [x for x in plan["skipped"] if x["reason"].startswith("deferred: max_orders_per_plan")]


def test_six_buys_give_four_orders_and_two_deferred():
    syms = SYMS[:6]
    plan = cap_plan(cap_cfg(syms), buys=syms)
    assert plan["errors"] == []
    assert [o["params"]["symbol"] for o in plan["orders"]] == ["AAA", "BBB", "CCC", "DDD"]     # priority order kept
    assert all(o["params"]["side"] == "buy" for o in plan["orders"])
    assert plan["deferred"] == 2 and plan["max_orders_per_plan"] == 4
    d = deferred(plan)
    assert [x["asset"] for x in d] == ["SEEE", "SFFF"]
    assert all("(Robinhood may execute agent orders beyond about 5 pending approvals without approval): run "
               "/moneyline again after approving these" in x["reason"] for x in d)
    assert "SEEE|EEE|buy|0" in d[0]["reason"]
    text = planner.format_plan(plan)
    assert "DEFERRED 2 orders beyond max_orders_per_plan 4" in text and "place the 4 below" in text
    assert text.count("place_equity_order") == 4
    assert "SKIPPED: SEEE: deferred: max_orders_per_plan 4" in text
    calls = cli.plan_calls(plan)
    assert [c["kind"] for c in calls].count("place") == 4
    for o in plan["orders"]:                                     # ref_ids are still the planner's
        assert o["params"]["ref_id"] == planner.ref_id(plan["plan_id"], o["key"], 1)


def test_cap_is_configurable_and_no_deferral_under_it():
    syms = SYMS[:6]
    plan = cap_plan(cap_cfg(syms, max_orders_per_plan=6), buys=syms)
    assert len(plan["orders"]) == 6 and plan["deferred"] == 0 and deferred(plan) == []
    assert "DEFERRED" not in planner.format_plan(plan)
    assert any("max_orders_per_plan 6 > max_pending_proposals 4: the hook blocks" in w for w in plan["warnings"])
    plan = cap_plan(cap_cfg(syms, max_orders_per_plan=6, max_pending_proposals=6), buys=syms)
    assert not any("max_pending_proposals" in w for w in plan["warnings"])
    plan = cap_plan(cap_cfg(syms, max_orders_per_plan=1), buys=syms)
    assert [o["params"]["symbol"] for o in plan["orders"]] == ["AAA"] and plan["deferred"] == 5


def test_sells_come_first_under_the_cap():
    # the sells' assets come last in the config: they are still placed first, and buys are what is deferred
    buys, sells = ["AAA", "BBB", "CCC", "DDD"], ["FFF", "GGG"]
    plan = cap_plan(cap_cfg(buys + sells), buys=buys, sells=sells)
    sides = [(o["params"]["side"], o["params"]["symbol"]) for o in plan["orders"]]
    assert sides == [("sell", "FFF"), ("sell", "GGG"), ("buy", "AAA"), ("buy", "BBB")]
    assert [x["asset"] for x in deferred(plan)] == ["SCCC", "SDDD"] and plan["deferred"] == 2
    assert not any("sell order(s) deferred" in w for w in plan["warnings"])


def test_more_sells_than_the_cap_keeps_the_first_sells():
    buys, sells = ["AAA"], ["DDD", "EEE", "FFF"]
    plan = cap_plan(cap_cfg(buys + sells, max_orders_per_plan=2), buys=buys, sells=sells)
    assert [(o["params"]["side"], o["params"]["symbol"]) for o in plan["orders"]] == [("sell", "DDD"),
                                                                                      ("sell", "EEE")]
    d = deferred(plan)
    assert [x["asset"] for x in d] == ["SFFF", "SAAA"] and "SFFF|FFF|sell|0" in d[0]["reason"]
    assert any("1 sell order(s) deferred" in w for w in plan["warnings"])


def test_cancels_are_not_capped():
    stale = [{"id": f"own-{k}", "ref_id": None, "symbol": f"ZZ{k}", "side": "buy", "state": "confirmed", "qty": 1.0,
              "filled": 0.0, "price": 10.0, "kind": "equity", "type": "limit", "open": True, "cancel_pending": False,
              "created_at": "2026-10-19T14:00:00Z", "agent_initiated": True} for k in range(6)]
    journal = [{"event": "place", "tool": "place_equity_order", "order_id": f"own-{k}", "ts": "2026-10-19T14:00:00Z",
                "params": {"symbol": f"ZZ{k}", "side": "buy", "quantity": "1", "limit_price": "10"}}
               for k in range(6)]
    syms = SYMS[:6]
    plan = cap_plan(cap_cfg(syms), buys=syms, open_orders=stale, journal=journal)
    assert len(plan["cancels"]) == 6 and len(plan["orders"]) == 4 and plan["deferred"] == 2


def test_stop_and_error_plans_have_no_deferral():
    syms = SYMS[:6]
    q = {s: quote(20.00, 20.05) for s in SYMS}
    s = snap(quotes=q)
    sigs = {"date": "2026-10-19", "assets": [eq_sig(x, 1.0) for x in syms]}
    plan = planner.make_plan(sigs, s, cap_cfg(syms), NOW, 1, {"STOP": "x"}, placed_today_usd=0.0, journal=[],
                             sleeve=owned(s))
    assert plan["orders"] == [] and plan["deferred"] == 0


# ------------------------------------------------------------------ 2. the pending-proposal guard (real hooks)

def five_orders():
    out = []
    for k, sym in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE"]):
        key = f"S{sym}|{sym}|buy|0"
        p = th.params(symbol=sym, quantity="10", limit_price="20.15", ref_id=hooks.ref_id_for(th.PLAN_ID, key, 1))
        out.append(th.plan_order(p, notional=201.5, key=key))
    return out


def listing(orders, state="filled", agent="user", at=None):
    created = (at or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rows = [{"id": f"appr-{k}", "ref_id": None, "symbol": o["params"]["symbol"], "side": "buy", "type": "limit",
             "state": state, "quantity": "10.00000000", "cumulative_quantity": "10.00000000" if state == "filled"
             else "0.00000000", "price": "20.15000000", "placed_agent": agent, "agent_initiated": False,
             "created_at": created} for k, o in enumerate(orders)]
    return env({"orders": rows, "next": ""})


def test_hook_blocks_the_fifth_place_while_four_proposals_are_pending(state):
    th.write_config(state)
    orders = five_orders()
    th.write_plan(state, orders=orders)
    for o in orders[:4]:                                         # four proposals, as on the first live day
        assert th.run(th.PRE, state, th.ev("place_equity_order", o["params"])).returncode == 0
        assert th.run(th.POST, state, th.ev("place_equity_order", o["params"], PROPOSAL)).returncode == 0
    assert [e["state"] for e in th.journal(state)] == [hooks.PROPOSAL_STATE] * 4
    r = th.run(th.PRE, state, th.ev("place_equity_order", orders[4]["params"]))
    err = r.stderr.decode()
    assert r.returncode == 2 and "4 proposals are still pending approval" in err
    assert "approve or reject them in the Robinhood app, then run /moneyline again" in err
    assert "limits.max_pending_proposals 4" in err and "Do not edit or retry" in err
    log = [json.loads(x) for x in (state / "hook.log").read_text().splitlines()]
    assert log[-1]["decision"] == "block" and "pending approval" in log[-1]["reason"]
    # reads and cancels are never blocked by it
    assert th.run(th.PRE, state, th.ev("get_equity_orders", {"account_number": th.ACCT})).returncode == 0
    assert th.run(th.PRE, state, th.ev("review_equity_order", th.params())).returncode == 0
    th.write_plan(state, orders=orders, cancels=[{"tool": "cancel_equity_order",
                                                   "params": {"account_number": th.ACCT, "order_id": "old-1"}}])
    assert th.run(th.PRE, state, th.ev("cancel_equity_order", {"account_number": th.ACCT,
                                                               "order_id": "old-1"})).returncode == 0
    # the user approves them; a later order listing shows them filled (approved orders read placed_agent 'user')
    post = th.run(th.POST, state, th.ev("get_equity_orders", {"account_number": th.ACCT}, listing(orders[:4])))
    assert post.returncode == 0 and not (state / "STOP").exists()
    r = th.run(th.PRE, state, th.ev("place_equity_order", orders[4]["params"]))
    assert r.returncode == 0, r.stderr.decode()


def test_hook_guard_threshold_is_the_config_value(state):
    th.write_config(state, max_pending_proposals=2)
    orders = five_orders()
    th.write_plan(state, orders=orders)
    for o in orders[:2]:
        assert th.run(th.PRE, state, th.ev("place_equity_order", o["params"])).returncode == 0
        th.run(th.POST, state, th.ev("place_equity_order", o["params"], PROPOSAL))
    r = th.run(th.PRE, state, th.ev("place_equity_order", orders[2]["params"]))
    assert r.returncode == 2 and b"2 proposals are still pending approval" in r.stderr


def test_hook_guard_still_open_orders_and_unreadable_listings_count(state):
    th.write_config(state)
    orders = five_orders()
    th.write_plan(state, orders=orders)
    for o in orders[:4]:
        th.run(th.PRE, state, th.ev("place_equity_order", o["params"]))
        th.run(th.POST, state, th.ev("place_equity_order", o["params"], PROPOSAL))
    # approved but not filled yet: still counted (conservative)
    th.run(th.POST, state, th.ev("get_equity_orders", {"account_number": th.ACCT},
                                 listing(orders[:4], state="confirmed")))
    assert th.run(th.PRE, state, th.ev("place_equity_order", orders[4]["params"])).returncode == 2
    # an unreadable listing capture settles nothing and never crashes the guard into allowing
    (state / "inbox" / f"{datetime.now(UTC):%Y%m%dT%H%M%S.%f}Z_get_equity_orders.json").write_text("{not json")
    r = th.run(th.PRE, state, th.ev("place_equity_order", orders[4]["params"]))
    assert r.returncode == 2 and b"4 proposals are still pending approval" in r.stderr
    # a corrupt journal fails closed
    with open(state / "journal.jsonl", "a") as f:
        f.write("{oops\n")
    r = th.run(th.PRE, state, th.ev("place_equity_order", orders[4]["params"]))
    assert r.returncode == 2 and b"hook error" in r.stderr


def entry(sym, ts, state=hooks.PROPOSAL_STATE, tool="place_equity_order", order_id=None, qty="10", px="20.15"):
    prm = {"symbol": sym, "side": "buy", "type": "limit", "quantity": qty, "limit_price": px}
    return {"ts": hooks.iso_z(ts), "event": "place", "tool": tool, "plan_id": "p", "key": f"{sym}|buy",
            "ref_id": f"ref-{sym}", "params": prm, "state": state, "order_id": order_id, "error": None}


def row(oid, sym, state="filled", qty="10.000", px="20.15", created=None, **kw):
    return {"id": oid, "ref_id": None, "symbol": sym, "side": "buy", "state": state, "quantity": qty, "price": px,
            "placed_agent": "user", "created_at": hooks.iso_z(created) if created else None, **kw}


def cap(inbox, tool, rows, at, kind="equity"):
    key = "orders" if kind == "equity" else "results"
    hooks.save_capture(inbox, f"mcp__robinhood__{tool}", {}, {"content": [{"type": "text", "text": json.dumps(
        env({key: rows, "next": ""}))}]}, at)


def test_awaiting_approval_rules(tmp_path):
    inbox, now = tmp_path / "inbox", datetime.now(UTC)
    t0 = now - timedelta(minutes=30)
    es = [entry("AAA", t0), entry("BBB", t0), entry("CCC", t0, state=hooks.FAILED_STATE),
          entry("DDD", t0, state="error"), entry("EEE", t0, state="queued", order_id="live-1"),
          entry("FFF", now - timedelta(days=8)),                    # older than PENDING_LOOKBACK (7 days): not counted
          entry("GGG", t0, tool="place_crypto_order", qty="1.5", px="150.25")]
    pend = hooks.awaiting_approval(es, inbox, now)
    assert [e["params"]["symbol"] for e in pend] == ["AAA", "BBB", "CCC", "GGG"]
    # a listing taken before the calls settles nothing; one after them settles a matching order once
    cap(inbox, "get_equity_orders", [row("o-a", "AAA")], t0 - timedelta(minutes=1))
    assert len(hooks.awaiting_approval(es, inbox, now)) == 4
    cap(inbox, "get_equity_orders", [row("o-a", "AAA", created=t0 + timedelta(minutes=2)),
                                     row("o-b", "BBB", state="cancelled"),
                                     row("o-x", "CCC", qty="11")], t0 + timedelta(minutes=5))
    assert [e["params"]["symbol"] for e in hooks.awaiting_approval(es, inbox, now)] == ["CCC", "GGG"]
    # crypto rows: currency_code, rejected; a wrong price does not match
    cap(inbox, "get_crypto_orders", [{"id": "c-1", "currency_code": "GGG", "side": "buy", "state": "rejected",
                                      "quantity": "1.50", "price": "150.26"}], t0 + timedelta(minutes=6), "crypto")
    assert len(hooks.awaiting_approval(es, inbox, now)) == 2
    cap(inbox, "get_crypto_orders", [{"id": "c-2", "symbol": "GGG-USD", "side": "buy", "state": "rejected",
                                      "quantity": "1.50", "price": "150.25"}], t0 + timedelta(minutes=7), "crypto")
    assert [e["params"]["symbol"] for e in hooks.awaiting_approval(es, inbox, now)] == ["CCC"]
    # one filled order settles one of two identical proposals; an order created well before the call none
    twins = [entry("HHH", t0), entry("HHH", t0 + timedelta(seconds=1))]
    cap(inbox, "get_equity_orders", [row("o-h", "HHH")], t0 + timedelta(minutes=8))
    assert len(hooks.awaiting_approval(twins, inbox, now)) == 1
    old = [entry("III", t0)]
    cap(inbox, "get_equity_orders", [row("o-i", "III", created=t0 - timedelta(hours=1))], t0 + timedelta(minutes=9))
    assert len(hooks.awaiting_approval(old, inbox, now)) == 1
    # the newest listing of an order wins: filled, then shown again as filled later, stays settled
    assert hooks.awaiting_approval([entry("AAA", t0)], inbox, now) == []
    # an unreadable timestamp always counts
    assert len(hooks.awaiting_approval([dict(entry("JJJ", t0), ts="garbage")], inbox, now)) == 1


def test_journal_fill_events_settle_and_live_orders_match_by_id(tmp_path):
    inbox, now = tmp_path / "inbox", datetime.now(UTC)
    t0 = now - timedelta(minutes=30)
    es = [entry("AAA", t0), {"ts": hooks.iso_z(t0 + timedelta(minutes=10)), "event": "fill", "kind": "equity",
                             "symbol": "AAA", "side": "buy", "order_id": "appr-9", "cumulative_quantity": 10.0,
                             "state": "filled"}]
    assert hooks.awaiting_approval(es, inbox, now) == []
    live = [entry("BBB", t0, state="queued", order_id="live-7")]
    assert hooks.unsettled(live, live, inbox) == live
    cap(inbox, "get_equity_orders", [row("live-7", "BBB", state="filled", qty="99")], t0 + timedelta(minutes=1))
    assert hooks.unsettled(live, live, inbox) == []
    assert post_tool_use.FAILED == hooks.FAILED_STATE


# ------------------------------------------------------------------ 2b. the guard across midnight; `resume --proposals`
# The real PreToolUse decide() and PostToolUse handle(), in process, with a controlled clock.

@pytest.fixture
def inproc(state, monkeypatch):
    from agentic.hooks import pre_tool_use
    monkeypatch.setattr(pre_tool_use, "H", hooks)
    monkeypatch.setattr(post_tool_use, "H", hooks)
    th.write_config(state)
    return pre_tool_use


def g_order(plan_id, sym, attempt=1, side="buy", crypto=False, px="20"):
    key = f"S{sym}|{sym}|{side}|0"
    ref = hooks.ref_id_for(plan_id, key, attempt)
    if crypto:
        p = th.crypto_params(symbol=sym, side=side, quantity="1", limit_price=px, ref_id=ref)
        return th.plan_order(p, notional=float(px), key=key, tool="place_crypto_order")
    return th.plan_order(th.params(symbol=sym, side=side, quantity="10", limit_price=px, ref_id=ref),
                         notional=10 * float(px), key=key)


def g_plan(state, plan_id, orders, created, valid_h=6, attempt=1, flags=()):
    plan = {"plan_id": plan_id, "signals_date": plan_id[:10], "created_at": hooks.iso_z(created),
            "valid_until": hooks.iso_z(created + timedelta(hours=valid_h)), "live": True, "attempt": attempt,
            "account_number": th.ACCT, "rhs_account_number": th.RHS, "capital_usd": 1000.0, "orders": orders,
            "cancels": [], "skipped": [], "warnings": [], "errors": [], "flags": list(flags)}
    (state / "plan_current.json").write_text(json.dumps(plan))
    return plan


def g_place(pre, order, now):
    """PreToolUse; if allowed, PostToolUse with a proposal result (data.order null). (allowed, reason)."""
    ok, why = pre.decide(th.ev(order["tool"], order["params"]), now=now)
    if ok:
        post_tool_use.handle(th.ev(order["tool"], order["params"], PROPOSAL), now=now)
    return ok, why


def pending(now):
    return hooks.awaiting_approval(hooks.read_journal(paths()["journal"]), paths()["inbox"], now)


def resolve(monkeypatch, now, typed="resolved\n", tty=True):
    monkeypatch.setattr(cli, "_now", lambda: now)
    monkeypatch.setattr(sys, "stdin", Tty(typed) if tty else io.StringIO(typed))
    return cli.main(["resume", "--proposals"])


COINS = ["ZZA", "ZZB", "ZZC", "ZZD"]                              # synthetic coin codes


def test_guard_still_counts_crypto_proposals_placed_before_et_midnight(state, inproc):
    pre = inproc
    t0 = datetime(2026, 10, 20, 3, 40, tzinfo=UTC)                # 23:40 ET Monday (EDT)
    a = "2026-10-19-aaaaaaaa"
    g_plan(state, a, [g_order(a, c, crypto=True, px="100") for c in COINS], t0)
    for i, c in enumerate(COINS):                                  # 23:45-23:48 ET: four gtc proposals
        assert g_place(pre, g_order(a, c, crypto=True, px="100"), t0 + timedelta(minutes=5 + i))[0]
    b = "2026-10-19-bbbbbbbb"                                      # a re-quote of the same coins
    orders_b = [g_order(b, c, attempt=2, crypto=True, px="101") for c in COINS]
    g_plan(state, b, orders_b, t0 + timedelta(minutes=12), attempt=2)
    ok, why = g_place(pre, orders_b[0], t0 + timedelta(minutes=13))
    assert not ok and "4 proposals are still pending approval" in why
    after = datetime(2026, 10, 20, 4, 1, tzinfo=UTC)               # 00:01 ET: a new ET date, nothing settled
    assert len(pending(after)) == 4
    for i, o in enumerate(orders_b):
        ok, why = g_place(pre, o, after + timedelta(minutes=i))
        assert not ok and "4 proposals are still pending approval" in why
    assert sum(1 for e in th.journal(state) if e.get("state") == hooks.PROPOSAL_STATE) == 4
    # the window is rolling: 7 days after the calls they stop counting
    assert len(pending(t0 + timedelta(days=7, minutes=4))) == 4
    assert pending(t0 + timedelta(days=7, minutes=9)) == []


def test_guard_counts_last_evenings_proposals_the_next_morning(state, inproc, monkeypatch):
    pre = inproc
    t0 = datetime(2026, 10, 19, 22, 0, tzinfo=UTC)                 # 18:00 ET Monday
    a = "2026-10-19-aaaaaaaa"
    g_plan(state, a, [g_order(a, c, crypto=True, px="100") for c in COINS], t0)
    assert all(g_place(pre, g_order(a, c, crypto=True, px="100"), t0 + timedelta(minutes=1 + i))[0]
               for i, c in enumerate(COINS))
    t1 = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)                 # 09:00 ET Tuesday: the old plan has expired
    assert cli.replan_problem(t1, 1) is None                       # so the planner plans the same coins again
    c = "2026-10-20-cccccccc"
    orders_c = [g_order(c, x, crypto=True, px="99") for x in COINS]
    g_plan(state, c, orders_c, t1)
    ok, why = g_place(pre, orders_c[0], t1 + timedelta(minutes=1))
    assert not ok and "4 proposals are still pending approval" in why and "resume --proposals" in why
    # the user rejected them in the app (no listing shows that) and acknowledges it in a terminal
    assert resolve(monkeypatch, t1 + timedelta(minutes=2)) == 0 and pending(t1 + timedelta(minutes=2)) == []
    assert all(g_place(pre, o, t1 + timedelta(minutes=3 + i))[0] for i, o in enumerate(orders_c))
    assert len(pending(t1 + timedelta(minutes=8))) == 4            # the new ones count; the guard blocks a 5th
    assert sum(1 for e in th.journal(state) if e.get("state") == hooks.PROPOSAL_STATE) == 8


def test_rejected_proposals_block_a_flatten_exit_until_the_user_resolves_them(state, inproc, monkeypatch, capsys):
    pre = inproc
    t0 = datetime(2026, 10, 19, 14, 0, tzinfo=UTC)                 # 10:00 ET Monday
    a = "2026-10-19-aaaaaaaa"
    buys = [g_order(a, s) for s in ("AAA", "BBB", "CCC", "DDD")]
    g_plan(state, a, buys, t0)
    assert all(g_place(pre, o, t0 + timedelta(minutes=i))[0] for i, o in enumerate(buys))
    # the user rejects all four in the app (no order listing ever shows them) and sets FLATTEN
    assert cli.main(["flatten", "get out"]) == 0
    out = capsys.readouterr().out
    assert "Reject any buy proposals" in out and "does not clear" in out and "resume --proposals" in out
    t1 = t0 + timedelta(hours=2)                                   # 12:00 ET: the FLATTEN plan has only sells
    c = "2026-10-19-cccccccc"
    sell = g_order(c, "XXX", side="sell")
    g_plan(state, c, [sell], t1, valid_h=4, flags=["FLATTEN"])
    for at in (t1 + timedelta(minutes=1), datetime(2026, 10, 19, 19, 40, tzinfo=UTC)):     # and still at 15:40 ET
        ok, why = g_place(pre, sell, at)
        assert not ok and "4 proposals are still pending approval" in why       # sells are not exempt
        assert "Rejecting a proposal in the app does not by itself clear the count" in why
        assert "resume --proposals` in their own terminal" in why
    now = t1 + timedelta(minutes=5)
    monkeypatch.setattr(cli, "_now", lambda: now)
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "proposals pending approval (last 7 days): 4" in out and "resume --proposals" in out
    assert "last proposals resolved" not in out
    # Claude's shell has no terminal: nothing is resolved; a wrong word changes nothing either
    assert resolve(monkeypatch, now, tty=False) == 2
    assert resolve(monkeypatch, now, typed="yes\n") == 1
    assert len(pending(now)) == 4 and not g_place(pre, sell, now)[0]
    assert not any(e.get("event") == hooks.RESOLVED_EVENT for e in th.journal(state))
    capsys.readouterr()
    assert resolve(monkeypatch, now) == 0
    out = capsys.readouterr().out
    assert out.count(" equity buy 10 ") == 4 and "resolved 4" in out
    res = [e for e in th.journal(state) if e.get("event") == hooks.RESOLVED_EVENT]
    places = [e for e in th.journal(state) if e.get("event") == "place"]
    assert len(res) == 1 and res[0]["count"] == 4 and res[0]["places"] == [hooks.place_id(e) for e in places]
    rec = [json.loads(x) for x in (state / "hook.log").read_text().splitlines()]
    rec = [r for r in rec if r.get("hook") == "cli"]
    assert [(r["tool"], r["decision"]) for r in rec] == [("flatten", "FLATTEN"), ("resume", "RESOLVE")]   # flatten
    rec = rec[1:]                                                  # records itself too (sticky STOP change)
    assert len(rec) == 1 and (rec[0]["tool"], rec[0]["decision"], rec[0]["ref_id"]) == ("resume", "RESOLVE", None)
    assert rec[0]["reason"].startswith("resolved 4 proposal(s)") and "SAAA|AAA|buy|0" in rec[0]["reason"]
    assert set(ledger.read_flags()) == {"FLATTEN"}                 # flags are not touched
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "proposals pending approval (last 7 days): 0" in out and "last proposals resolved: " in out
    assert resolve(monkeypatch, now) == 0 and "nothing to resolve" in capsys.readouterr().out
    ok, why = g_place(pre, sell, now + timedelta(minutes=1))       # the exit goes out
    assert ok, why
    assert len(pending(now + timedelta(minutes=2))) == 1           # and counts itself
    with pytest.raises(SystemExit):                                # --flag and --proposals exclude each other
        cli.main(["resume", "--proposals", "--flag", "STOP"])


def test_resolve_releases_only_the_listed_entries():
    inbox, now = Path("/nonexistent-inbox"), datetime.now(UTC)
    t0 = now - timedelta(hours=1)
    failed = entry("AAA", t0, state=hooks.FAILED_STATE)
    retry = dict(entry("AAA", t0 + timedelta(minutes=1)))          # a failed place may be retried with its ref_id
    odd = dict(entry("BBB", t0), ts="garbage")                     # an unreadable timestamp counts until resolved
    assert failed["ref_id"] == retry["ref_id"]
    ack = {"event": hooks.RESOLVED_EVENT, "places": [hooks.place_id(failed), hooks.place_id(odd)], "count": 2}
    assert hooks.awaiting_approval([failed, retry, odd], inbox, now) == [failed, retry, odd]
    assert hooks.awaiting_approval([failed, retry, odd, ack], inbox, now) == [retry]
    later = entry("CCC", now)                                      # placed after the acknowledgement: counts
    assert hooks.awaiting_approval([failed, retry, odd, ack, later], inbox, now) == [retry, later]
    bad = {"event": hooks.RESOLVED_EVENT, "places": "everything"}  # a malformed entry releases nothing
    assert len(hooks.awaiting_approval([failed, bad], inbox, now)) == 1


# ------------------------------------------------------------------ re-planning the deferred rest

def plan_with(orders, deferred_n, valid_min=60):
    now = datetime.now(UTC)
    plan = {"plan_id": "2026-10-19-abcdef12", "created_at": hooks.iso_z(now), "attempt": 1, "flags": [],
            "valid_until": hooks.iso_z(now + timedelta(minutes=valid_min)), "live": True, "deferred": deferred_n,
            "max_orders_per_plan": 4, "orders": [{"key": e["key"], "params": e["params"]} for e in orders]}
    ledger.write_json(paths()["plan_current"], plan)
    for e in orders:
        ledger.append_journal(dict(e, plan_id=plan["plan_id"]))
    return plan


def test_replan_after_the_placed_orders_settle_when_orders_were_deferred(state):
    now = datetime.now(UTC)
    t0 = now - timedelta(minutes=20)
    es = [entry(s, t0) for s in ("AAA", "BBB", "CCC", "DDD")]
    plan_with(es, 2)
    why = cli.replan_problem(now, 1)
    assert why and "4 of its orders were placed" in why and "Its 2 orders not placed yet" in why
    assert "approve them in the Robinhood app, then run /moneyline again" in why
    cap(paths()["inbox"], "get_equity_orders", [row(f"a{k}", s, state="confirmed") for k, s in
                                                enumerate(("AAA", "BBB", "CCC", "DDD"))], t0 + timedelta(minutes=5))
    assert cli.replan_problem(now, 1)                           # approved but not filled: still refused
    cap(paths()["inbox"], "get_equity_orders", [row(f"a{k}", s) for k, s in enumerate(("AAA", "BBB", "CCC"))]
        + [row("a3", "DDD", state="confirmed")], t0 + timedelta(minutes=6))
    assert cli.replan_problem(now, 1)                           # one still open
    cap(paths()["inbox"], "get_equity_orders", [row(f"a{k}", s) for k, s in
                                                enumerate(("AAA", "BBB", "CCC", "DDD"))], t0 + timedelta(minutes=7))
    assert cli.replan_problem(now, 1) is None                   # all filled: the deferred rest may be planned


def test_replan_stays_refused_when_nothing_was_left_unplaced(state):
    now = datetime.now(UTC)
    t0 = now - timedelta(minutes=20)
    es = [entry(s, t0) for s in ("AAA", "BBB")]
    plan_with(es, 0)
    cap(paths()["inbox"], "get_equity_orders", [row("a0", "AAA"), row("a1", "BBB")], t0 + timedelta(minutes=5))
    why = cli.replan_problem(now, 1)
    assert why and "not placed yet" not in why                  # unchanged: the plan is done, nothing to re-plan
    assert cli.replan_problem(now, 2) is None                   # a re-quote is allowed as before


def test_replan_after_a_blocked_place_once_the_placed_ones_settle(state):
    now = datetime.now(UTC)
    t0 = now - timedelta(minutes=20)
    es = [entry(s, t0) for s in ("AAA", "BBB")]
    plan = plan_with(es, 0)
    plan["orders"].append({"key": "CCC|buy", "params": {"symbol": "CCC"}})       # its place call was blocked
    ledger.write_json(paths()["plan_current"], plan)
    assert "Its 1 order not placed yet" in cli.replan_problem(now, 1)
    cap(paths()["inbox"], "get_equity_orders", [row("a0", "AAA"), row("a1", "BBB", state="rejected")],
        t0 + timedelta(minutes=5))
    assert cli.replan_problem(now, 1) is None


def test_replan_of_the_deferred_rest_after_the_user_resolves_rejected_proposals(state, monkeypatch):
    now = datetime.now(UTC)
    t0 = now - timedelta(minutes=20)
    es = [entry(s, t0) for s in ("AAA", "BBB", "CCC", "DDD")]
    plan_with(es, 2)
    cap(paths()["inbox"], "get_equity_orders", [row("a0", "AAA"), row("a1", "BBB")], t0 + timedelta(minutes=5))
    assert cli.replan_problem(now, 1)                           # CCC and DDD were rejected: no listing shows them
    assert resolve(monkeypatch, now) == 0                       # the user acknowledges them in a terminal
    assert cli.replan_problem(now, 1) is None


# ------------------------------------------------------------------ 3. resume records, status and digest banners

class Tty(io.StringIO):
    def isatty(self):
        return True


def test_resume_writes_a_hook_log_line_and_status_shows_it(state, monkeypatch, capsys):
    assert cli.main(["init"]) == 0
    stop = f"2026-10-19T14:10:00.123456Z {BYPASS} (order 0a1b2c3d, state filled)\n"
    (state / "STOP").write_text(stop)
    ledger.set_flag("BLOCK_BUYS", "reconcile: equity AAA: expected 1, captured 2 (account 123456789)")
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].startswith("!!! STOP is set") and "without approval" in lines[0]
    assert lines[1].startswith("!!! APPROVAL BYPASS") and "robot icon" in lines[1] and "report it to Robinhood" in out
    assert "!!! BLOCK_BUYS is set" in out and "last flag clear: none recorded in hook.log" in out
    assert "proposals pending approval (last 7 days): 0" in out
    monkeypatch.setattr(sys, "stdin", io.StringIO("resume\n"))            # no terminal: nothing cleared or logged
    assert cli.main(["resume"]) == 2 and not (state / "hook.log").exists()
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(sys, "stdin", Tty("resume\n"))
    assert cli.main(["resume"]) == 0 and ledger.read_flags() == {}
    rec = [json.loads(x) for x in (state / "hook.log").read_text().splitlines()]
    assert len(rec) == 1
    r = rec[0]
    assert r["ts"] == "2026-10-19T15:00:00.000000Z" and r["hook"] == "cli" and r["tool"] == "resume"
    assert r["decision"] == "CLEAR" and r["ref_id"] is None
    assert r["reason"].startswith("cleared STOP (was: 2026-10-19T14:10:00.")       # 6+ digit runs masked, as
    assert "an agent order went live without approval" in r["reason"]              # in the hooks' own lines
    assert "BLOCK_BUYS (was: " in r["reason"] and "123456789" not in r["reason"]     # long digit runs masked
    assert len(r["reason"]) <= cli.CLEAR_REASON_MAX
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "!!!" not in out and "flags: none" in out
    assert "last flag clear: 2026-10-19T15:00:00.000000Z cleared STOP (was: " in out


def test_resume_reason_is_truncated_and_the_newest_clear_wins(state, monkeypatch):
    assert cli.main(["init"]) == 0
    ledger.set_flag("STOP", "x" * 5000)
    monkeypatch.setattr(sys, "stdin", Tty("resume\n"))
    assert cli.main(["resume"]) == 0
    ledger.set_flag("FLATTEN", "second")
    monkeypatch.setattr(sys, "stdin", Tty("resume\n"))
    assert cli.main(["resume"]) == 0
    first, second = [json.loads(x) for x in (state / "hook.log").read_text().splitlines()]
    assert len(first["reason"]) < cli.FLAG_TEXT_MAX + 40
    assert cli.last_flag_clear()["reason"] == "cleared FLATTEN (was: second)"
    hooks.log("post", "mcp__robinhood__get_portfolio", "captured", "saved")        # later hook lines are skipped
    assert cli.last_flag_clear()["reason"] == "cleared FLATTEN (was: second)"


def test_resume_records_the_flags_it_cleared_when_a_later_clear_fails(state, monkeypatch, capsys):
    assert cli.main(["init"]) == 0
    (state / "STOP").write_text(f"2026-10-19T13:53:59Z {BYPASS}\n")
    ledger.set_flag("BLOCK_BUYS", "reconcile: mismatch")
    real = ledger.clear_flag

    def held_open(name, base=None):                              # Windows: the file is open elsewhere (WinError 32)
        if name == "BLOCK_BUYS":
            raise PermissionError(32, "The process cannot access the file because it is being used by another "
                                      "process")
        return real(name, base)
    monkeypatch.setattr(ledger, "clear_flag", held_open)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(sys, "stdin", Tty("resume\n"))
    capsys.readouterr()
    assert cli.main(["resume"]) == 1
    cap_ = capsys.readouterr()
    assert set(ledger.read_flags()) == {"BLOCK_BUYS"}             # STOP is gone ...
    assert "cleared STOP" in cap_.out and "could not clear BLOCK_BUYS (PermissionError" in cap_.err
    rec = cli.last_flag_clear()                                   # ... and hook.log says so
    assert rec and rec["reason"].startswith("cleared STOP (was: ") and "BLOCK_BUYS" not in rec["reason"]
    assert "went live without approval" in rec["reason"]
    capsys.readouterr()
    assert cli.main(["status"]) == 0 and "last flag clear: 2026-10-19T15:00:00.000000Z cleared STOP" in \
        capsys.readouterr().out
    # any other error still records what was cleared before it propagates
    ledger.set_flag("STOP", "set again")

    def broken(name, base=None):
        if name == "BLOCK_BUYS":
            raise RuntimeError("unexpected")
        return real(name, base)
    monkeypatch.setattr(ledger, "clear_flag", broken)
    monkeypatch.setattr(sys, "stdin", Tty("resume\n"))
    with pytest.raises(RuntimeError):
        cli.main(["resume"])
    assert cli.last_flag_clear()["reason"] == "cleared STOP (was: set again)"
    assert set(ledger.read_flags()) == {"BLOCK_BUYS"}


def test_digest_shows_the_stop_banner_until_cleared(state, monkeypatch, capsys):
    from agentic import signals as sg
    written = []
    monkeypatch.setattr(sg, "compute_signals", lambda *a, **k: {"assets": []})
    monkeypatch.setattr(sg, "format_digest", lambda sig, full=False: "MONEYLINE DIGEST synthetic")
    monkeypatch.setattr(sg, "write_signals", lambda sig: paths()["base"] / "signals" / "s.json")
    monkeypatch.setattr(sg, "write_digest", lambda sig, text: written.append(text) or paths()["base"] / "d.txt")
    args = cli.build_parser().parse_args(["signals"])
    (state / "STOP").write_text(f"2026-10-19T14:05:00.000000Z {BYPASS}\n")
    cli._signals(args, {}, NOW)
    first = written[-1].splitlines()
    assert first[0].startswith("!!! STOP is set") and first[1].startswith("!!! APPROVAL BYPASS")
    assert first[2] == "MONEYLINE DIGEST synthetic" and capsys.readouterr().out.startswith("!!! STOP is set")
    (state / "STOP").write_text("2026-10-19T13:00:00Z set by the user\n")       # a plain STOP: no bypass advice
    cli._signals(args, {}, NOW)
    assert written[-1].splitlines()[0].startswith("!!! STOP") and "APPROVAL BYPASS" not in written[-1]
    (state / "STOP").unlink()
    cli._signals(args, {}, NOW)
    assert written[-1] == "MONEYLINE DIGEST synthetic"


def test_the_post_hook_stop_is_shown_by_status(state, capsys):
    """End to end: a place result that carries a live order makes the PostToolUse hook write STOP; `status` shows the
    APPROVAL BYPASS banner first."""
    th.write_config(state)
    th.write_plan(state)
    assert th.run(th.POST, state, th.ev("place_equity_order", th.params(), th.place_resp())).returncode == 0
    assert (state / "STOP").exists()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("!!! STOP is set") and out[1].startswith("!!! APPROVAL BYPASS")


# ------------------------------------------------------------------ 4. get_currency_pairs paging

CODES = [f"C{k:03d}" for k in range(93)]


def write_pair_pages(inbox, n_pages=3, at=None):
    at = at or NOW - timedelta(minutes=10)
    pages = [CODES[0:40], CODES[40:80], CODES[80:93]][:n_pages]
    for k, codes in enumerate(pages):
        nxt = f"cur-{k + 2}" if k < 2 else ""
        ti = {"limit": 40} if k == 0 else {"limit": 40, "cursor": f"cur-{k + 1}"}
        write_cap(inbox, "get_currency_pairs", env({"results": [pair_row(c) for c in codes], "next": nxt}), ti,
                  at + timedelta(seconds=k), "text")


def test_fetch_list_pages_currency_pairs():
    assert cli.pairs_page_limit() == 40
    # a pair row of the official shape is about 600-700 characters (indented): 40 stay far below 50,000
    page = env({"results": [pair_row(c) for c in CODES[:40]], "next": "cur-2"})
    assert len(json.dumps(page, indent=2)) < 40_000
    for needs in ({"stage1": True, "pairs_stage1": True, "tradability": []}, {"stage1": False}):
        calls = cli.fetch_calls(validate(uni_cfg()), NOW, needs=needs)
        pc = [c for c in calls if c["tool"] == "get_currency_pairs"]
        assert len(pc) == 1 and pc[0]["params"] == {"limit": 40} and 'follow "next"' in pc[0]["why"]
    calls = cli.fetch_calls(snap_cfg(crypto=True), NOW, needs={})                   # direct crypto, no universe
    pc = [c for c in calls if c["tool"] == "get_currency_pairs"]
    assert pc == [{"tool": "get_currency_pairs", "params": {"limit": 40},
                   "why": 'crypto order size and price increments; 40 per page: follow "next"'}]


def test_currency_pairs_pages_merge_in_both_loaders(state):
    inbox = state / "inbox"
    write_pair_pages(inbox, n_pages=2)
    pc = universe.pairs_capture(inbox, NOW)
    assert pc["pages"] == 2 and not pc["complete"] and len(pc["pairs"]) == 80
    write_pair_pages(inbox, n_pages=3, at=NOW - timedelta(minutes=5))         # a newer complete fetch
    pc = universe.pairs_capture(inbox, NOW)
    assert pc["pages"] == 3 and pc["complete"] and set(pc["pairs"]) == set(CODES)
    s = sn.build_snapshot(inbox, snap_cfg(crypto=True), NOW)
    assert {f"{c}-USD" for c in CODES} <= set(s["pairs"])
    assert s["pairs"]["C092-USD"]["asset_increment"] == "0.01"
    assert s["pairs"]["C092-USD"]["quote_increment"] == "0.000001"


# ------------------------------------------------------------------ 5. docs

def test_docs_describe_the_defences():
    readme = (REPO / "agentic" / "README.md").read_text(encoding="utf-8")
    spec = (REPO / "agentic" / "SPEC.md").read_text(encoding="utf-8")
    cmd = (REPO / ".claude" / "commands" / "moneyline.md").read_text(encoding="utf-8")
    for text in (readme, spec):
        assert "max_orders_per_plan" in text and "max_pending_proposals" in text
    assert "robot icon" in readme and "report" in readme.lower() and "5th pending proposal" in readme
    assert "proposals are still pending approval" in cmd and "DEFERRED" in cmd
    assert "limit 40" in readme or '"limit": 40' in readme
    # rejecting does not clear the pending count; `resume --proposals` (the user's, in a terminal) does
    for text in (readme, cmd):
        assert "resume --proposals" in text and "does not clear the count" in text
    assert "`resume` (`resume --proposals` included)" in cmd and "Never run it yourself" in cmd
    assert "last 7 days" in readme and "proposals_resolved" in spec and "PENDING_LOOKBACK" in spec
    assert "current ET date" not in spec and "until the ET day ends" not in readme
