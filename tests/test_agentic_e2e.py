"""End-to-end offline dry run of agentic/: init -> config -> fetch-list reads through the real hooks -> signals
(Coinbase mocked at urllib, stock bars from inbox captures) -> reconcile -> plan -> every plan order through the real
PreToolUse hook as a subprocess -> PostToolUse place results -> fills -> reconcile. Plus unit tests of signals.py and
cli.py. All data and account numbers are synthetic; no network; state only under tmp_path.

The hooks check plan expiry against the real clock, so the end-to-end tests run on the real time too.
"""
import io
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import calendar as cal  # noqa: E402
from agentic import cli, ledger  # noqa: E402
from agentic import data as feeds  # noqa: E402
from agentic import signals as sg  # noqa: E402
from agentic.config import paths, validate  # noqa: E402
from agentic.indicator import tranche_targets  # noqa: E402

PRE = REPO / "agentic" / "hooks" / "pre_tool_use.py"
POST = REPO / "agentic" / "hooks" / "post_tool_use.py"
UTC = timezone.utc
ET = ZoneInfo("America/New_York")
ACCT, RHS = "E2EACCT0Q7", "913370042"          # synthetic account numbers
SRV = "mcp__robinhood-trading__"
SPY_BID, SPY_ASK, SOL_BID, SOL_ASK = "99.95", "100.05", "150.00", "150.10"
EPOCH = pd.Timestamp("1970-01-01")


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(d))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return d


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def real_now():
    """The real time, skipping the few minutes around a bar close or plan cutoff (the hooks use the real clock)."""
    now = datetime.now(UTC)
    et = now.astimezone(ET)
    m_et, m_utc = et.hour * 60 + et.minute, now.hour * 60 + now.minute
    if any(abs(m_et - b) <= 3 for b in (15 * 60 + 45, 16 * 60 + 20)) or m_utc <= 3 or m_utc >= 24 * 60 - 3:
        pytest.skip("too close to a bar close / plan cutoff for a real-clock end-to-end run")
    return now


# ------------------------------------------------------------------ synthetic bars and feeds

def trend(days, end_px, drift=0.002, dip=None):
    """Smooth uptrend ending near end_px: green on every tranche after warm-up, no data-check findings. `dip`: bars
    before the end where a 15% dip starts (5 bars down, 5 back up): every tranche flips red, then green again
    about dip - 8 bars before the end, so the default entry policy (join_recent, 20 bars) may buy."""
    k = np.arange(len(days), dtype=float)
    c = end_px * np.exp(drift * (k - k[-1]) + 0.01 * np.sin(k / 5.0))
    if dip:
        f = np.ones(len(c))
        f[len(c) - dip:len(c) - dip + 10] = np.r_[np.linspace(0.97, 0.85, 5), np.linspace(0.88, 1.0, 5)]
        c = c * f
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99, "close": c},
                        index=pd.DatetimeIndex(pd.to_datetime(days), name="date"))


def walk(n, seed):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.03, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.01, n)))
    lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.01, n)))
    return np.c_[o, h, lo, c]


def redate(values, last: date):
    days = pd.date_range(end=pd.Timestamp(last), periods=len(values), freq="D", name="date")
    return pd.DataFrame(values, columns=["open", "high", "low", "close"], index=days)


class FakeCoinbase:
    """GET /products/{p}/candles from a frame: <= 300 rows of [time, low, high, open, close, volume], newest first,
    including the forming bar (as the real API does)."""

    def __init__(self, frames):
        self.frames = frames
        self.urls = []

    def __call__(self, req, timeout=None):
        u = urlparse(req.full_url)
        assert u.netloc == "api.exchange.coinbase.com", req.full_url
        self.urls.append(req.full_url)
        product = u.path.split("/")[2]
        q = parse_qs(u.query)
        s = pd.Timestamp(q["start"][0]).tz_convert(None)
        e = pd.Timestamp(q["end"][0]).tz_convert(None)
        assert (e - s).days + 1 <= 300
        f = self.frames[product]
        f = f[(f.index >= s) & (f.index <= e)]
        rows = [[int((d - EPOCH).total_seconds()), r.low, r.high, r.open, r.close, 10.0]
                for d, r in f.iloc[::-1].iterrows()]
        return io.BytesIO(json.dumps(rows).encode())


# ------------------------------------------------------------------ config and Robinhood responses (official shapes)

def cfg_dict(live=True, spy_fractional=False):
    return {"account": {"account_number": ACCT, "rhs_account_number": RHS, "approvals_required": True},
            "live": live, "capital": {"max_usd": 2000},
            "limits": {"max_order_usd": 500, "max_day_usd": 1500, "max_asset_frac": 0.30, "max_crypto_frac": 0.60,
                       "min_order_usd": 5},
            "assets": [
                {"name": "SOL", "class": "crypto", "enabled": True, "alloc_frac": 0.25, "mode": "immediate",
                 "signal": {"source": "computed", "feed": "coinbase", "symbol": "SOL-USD"},
                 "vehicle": {"type": "crypto", "symbol": "SOL"}},
                {"name": "SPY", "class": "equity", "enabled": True, "alloc_frac": 0.25, "mode": "split",
                 "signal": {"source": "computed", "feed": "robinhood", "symbol": "SPY"},
                 "vehicle": {"type": "equity", "symbol": "SPY", "fractional": spy_fractional}}]}


def env(data):
    return {"data": data, "guide": "synthetic guide text"}


def rh_bars(frame):
    return [{"begins_at": f"{d.date().isoformat()}T13:30:00Z", "open_price": f"{r.open:.4f}",
             "close_price": f"{r.close:.4f}", "high_price": f"{r.high:.4f}", "low_price": f"{r.low:.4f}",
             "volume": 1000, "session": "reg", "interpolated": False} for d, r in frame.iterrows()]


def read_response(tool, params, w):
    """Synthetic result for one fetch-list call. `w`: world state (frames, fills, quote time)."""
    qts = iso(w["quote_time"])
    f = w.get("fills")
    spy_q, sol_q = (f["spy_qty"], f["sol_qty"]) if f else ("0", "0")
    cash = 2000.0 - (f["spent"] if f else 0.0)
    total = cash + float(spy_q) * 100.0 + float(sol_q) * 150.05
    usd = {"currency": {"code": "USD", "type": "fiat"}, "quantity": f"{cash:.2f}", "quantity_transferable": "0"}
    if tool == "get_accounts":
        return env({"accounts": [{"account_number": ACCT, "rhs_account_number": RHS, "type": "cash",
                                  "brokerage_account_type": "individual", "agentic_allowed": True}]})
    if tool == "get_portfolio":
        return env({"total_value": f"{total:.2f}", "cash": f"{cash:.2f}",
                    "buying_power": {"buying_power": f"{cash:.2f}", "unleveraged_buying_power": f"{cash:.2f}"},
                    "crypto_buying_power": {"buying_power": f"{cash:.2f}"}})
    if tool == "get_equity_positions":
        rows = [{"symbol": "SPY", "quantity": spy_q, "shares_available_for_sells": spy_q,
                 "average_buy_price": "100.05", "type": "long"}] if f else []
        return env({"positions": rows, "next": ""})
    if tool == "get_crypto_positions":
        rows = [{"currency": {"code": "SOL", "type": "cryptocurrency"}, "currency_pair_id": "pair-sol",
                 "quantity": sol_q, "quantity_transferable": sol_q}] if f else []
        return env({"results": [usd, *rows], "next": ""})
    if tool == "get_equity_orders":
        rows = [{"id": "ord-spy-1", "ref_id": None, "symbol": "SPY", "side": "buy", "type": "limit",
                 "state": "filled", "quantity": spy_q, "cumulative_quantity": spy_q, "price": f["spy_limit"],
                 "average_price": "100.05", "time_in_force": "gfd", "market_hours": "regular_hours",
                 "placed_agent": "user", "agent_initiated": True, "created_at": f["created"]}] if f else []
        return env({"orders": rows, "next": ""})
    if tool == "get_crypto_orders":
        rows = [{"id": "ord-sol-1", "ref_id": "approval-sol-1", "currency_pair_id": "pair-sol", "currency_code": "SOL",
                 "side": "buy", "type": "limit", "state": "filled", "state_group": "closed", "quantity": sol_q,
                 "cumulative_quantity": sol_q, "price": f["sol_limit"], "limit_price": f["sol_limit"],
                 "average_price": "150.10", "created_at": f["created"], "updated_at": f["created"]}] if f else []
        return env({"rhs_account_number": RHS, "results": rows, "next": ""})
    if tool == "get_currency_pairs":
        return env({"results": [{"id": "pair-sol", "symbol": "SOL-USD", "asset_currency": {"code": "SOL"},
                                 "tradability": "tradable", "min_order_size": "0.0001",
                                 "min_order_quantity_increment": "0.0001", "min_order_price_increment": "0.01",
                                 "min_order_quote_amount": "1.00", "halted": False, "display_only": False,
                                 "market_orders_only": False}], "next": ""})
    if tool == "get_equity_historicals":
        assert params["symbols"] == ["SPY"] and params["adjustment_type"] == "split" and params["interval"] == "day"
        return env({"results": [{"symbol": "SPY", "interval": "day", "bounds": "regular",
                                 "bars": rh_bars(w["spy"])}]})
    if tool == "get_equity_quotes":
        return env({"results": [{"quote": {"symbol": "SPY", "bid_price": SPY_BID, "ask_price": SPY_ASK,
                                           "last_trade_price": "100.00", "venue_bid_time": qts,
                                           "venue_ask_time": qts, "has_traded": True, "state": "active"}}]})
    if tool == "get_crypto_quotes":
        return env({"results": [{"symbol": "SOLUSD", "id": "pair-sol", "bid_price": SOL_BID, "ask_price": SOL_ASK,
                                 "mark_price": "150.05", "updated_at": qts}]})
    raise AssertionError(f"unexpected read {tool}")


# ------------------------------------------------------------------ hooks as subprocesses

def hook(script, state, short, ti, resp=None):
    e = {"session_id": "e2e", "cwd": str(REPO), "tool_name": SRV + short, "tool_input": ti,
         "hook_event_name": "PreToolUse" if resp is None else "PostToolUse"}
    if resp is not None:
        e["tool_response"] = resp
    env_ = dict(os.environ, AGENTIC_STATE_DIR=str(state))
    return subprocess.run([sys.executable, "-I", str(script)], input=json.dumps(e).encode(), env=env_,
                          capture_output=True, timeout=60)


def mcp_call(state, short, ti, resp):
    """What Claude Code does around one Robinhood tool call: PreToolUse, the call, PostToolUse."""
    pre = hook(PRE, state, short, ti)
    assert pre.returncode == 0, pre.stderr.decode()
    post = hook(POST, state, short, ti, resp)
    assert post.returncode == 0
    return post


def journal(state):
    f = state / "journal.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def world(now):
    crypto_end = cal.last_closed_crypto_bar(now)
    eq_end = cal.last_closed_equity_session(now)
    sol = trend(pd.date_range(end=pd.Timestamp(crypto_end) + pd.Timedelta(days=1), periods=900, freq="D"), 150.0,
                dip=20)
    spy = trend(cal.trading_days(eq_end - timedelta(days=700), eq_end), 100.0, dip=20)
    return {"sol": sol, "spy": spy, "quote_time": now - timedelta(minutes=1), "fills": None,
            "crypto_end": crypto_end, "eq_end": eq_end}


def prepare(state, monkeypatch, now, live=True):
    """init, the test config, mocked Coinbase, and every fetch-list read made through the real hooks."""
    assert cli.main(["init"]) == 0
    assert (state / "config.json").exists() and (state / "inbox").is_dir()
    (state / "config.json").write_text(json.dumps(cfg_dict(live=live)))
    w = world(now)
    fake = FakeCoinbase({"SOL-USD": w["sol"]})
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    w["coinbase"] = fake
    do_reads(state, w)
    return w


def do_reads(state, w, only=None):
    calls = cli.fetch_calls(validate(cfg_dict()), datetime.now(UTC))
    for c in calls:
        if only is None or c["tool"] in only:
            mcp_call(state, c["tool"], c["params"], read_response(c["tool"], c["params"], w))
    return calls


# ------------------------------------------------------------------ end to end

def test_full_offline_dry_run(state, monkeypatch, capsys):
    now = real_now()
    w = prepare(state, monkeypatch, now)
    caps = sorted(p.name for p in (state / "inbox").glob("*.json"))
    hist = [n for n in caps if n.endswith("_get_equity_historicals.json")]
    sessions = len(cal.trading_days((now - timedelta(days=700)).date(), w["eq_end"]))
    assert len(hist) == -(-sessions // 120) and len(caps) == 10 + len(hist)    # backfill windows of <= 120 sessions

    # phase 1: signals (Coinbase through the fake urlopen, stock bars from the inbox capture)
    assert cli.main(["signals"]) == 0
    assert len(w["coinbase"].urls) >= 3                     # 900 days in 300-candle pages
    sig = json.loads((state / "signals" / f"signals_{now.date().isoformat()}.json").read_text())
    by = {a["name"]: a for a in sig["assets"]}
    assert by["SOL"]["bar_date"] == by["SOL"]["expected_bar_date"] == w["crypto_end"].isoformat()
    assert by["SPY"]["bar_date"] == by["SPY"]["expected_bar_date"] == w["eq_end"].isoformat()
    for a in by.values():
        assert a["errors"] == [] and a["target_frac"] == 1.0 and a["prev_target_frac"] == 1.0 and not a["changed"]
        assert a["line_n1"] < a["close"] and a["dist_to_line_pct"] < 0 and a["atr10"] > 0
    assert [t["n_entry"] for t in by["SPY"]["tranches"]] == [1, 5] and all(t["green"] for t in by["SPY"]["tranches"])
    assert abs(by["SOL"]["close"] - w["sol"]["close"].iloc[-2]) < 1e-9        # forming bar dropped
    assert list((state / "digests").glob("digest_*.txt"))

    # phase 2: baseline, plan
    assert cli.main(["reconcile"]) == 0
    assert (state / "positions_reconciled.json").exists()
    capsys.readouterr()
    assert cli.main(["plan"]) == 0
    out = capsys.readouterr().out
    assert "EXACT TOOL CALLS" in out and ACCT in out          # exact params, accounts included, for Claude to copy
    plan = json.loads((state / "plan_current.json").read_text())
    assert plan["live"] is True and plan["errors"] == [] and plan["cancels"] == []
    orders = {o["key"]: o for o in plan["orders"]}
    assert set(orders) == {"SOL|SOL|buy|0", "SPY|SPY|buy|0"}
    spy, sol = orders["SPY|SPY|buy|0"], orders["SOL|SOL|buy|0"]
    assert (spy["params"]["type"], spy["params"]["quantity"], spy["params"]["limit_price"]) == ("limit", "4", "100.55")
    assert sol["tool"] == "place_crypto_order" and sol["params"]["rhs_account_number"] == RHS
    assert sol["params"]["limit_price"] == "151.60" and sol["params"]["time_in_force"] == "gtc"
    assert all(isinstance(v, str) for o in plan["orders"] for v in o["params"].values())

    # every plan order passes its own guard; tampered ones do not
    for o in plan["orders"]:
        r = hook(PRE, state, o["preview_tool"], o["preview_params"])
        assert r.returncode == 0, r.stderr.decode()
        assert hook(POST, state, o["preview_tool"], o["preview_params"], env({"estimate": "ok"})).returncode == 0
        assert hook(PRE, state, o["tool"], o["params"]).returncode == 0
    for change in ({"quantity": "5"}, {"limit_price": "100.56"}, {"side": "sell"}, {"symbol": "QQQ"},
                   {"ref_id": "00000000-0000-5000-8000-000000000000"}, {"dollar_amount": "400.00"},
                   {"account_number": "OTHERACCT1"}):
        r = hook(PRE, state, spy["tool"], {**spy["params"], **change})
        assert r.returncode == 2 and b"BLOCKED" in r.stderr, change
    r = hook(PRE, state, "place_equity_order", sol["params"])           # right params, wrong tool
    assert r.returncode == 2

    # place: approvals ON, so each place returns a pending proposal (data.order null)
    for o in plan["orders"]:
        post = hook(POST, state, o["tool"], o["params"], env({"order": None}))
        assert post.returncode == 0 and b"STOP" not in post.stdout
    assert not (state / "STOP").exists()
    places = [e for e in journal(state) if e["event"] == "place"]
    assert [e["key"] for e in places] == [o["key"] for o in plan["orders"]]
    assert all(e["state"] == "proposal_pending_approval?" and e["plan_id"] == plan["plan_id"] for e in places)
    total = round(sum(o["notional_usd"] for o in plan["orders"]), 2)
    assert ledger.placed_usd(datetime.now(UTC)) == pytest.approx(total)
    r = hook(PRE, state, spy["tool"], spy["params"])                    # never re-send a placed ref_id
    assert r.returncode == 2 and b"already placed" in r.stderr
    capsys.readouterr()
    assert cli.main(["plan"]) == 1                                      # no re-plan over waiting proposals
    assert "NOT RE-PLANNING" in capsys.readouterr().err
    assert json.loads((state / "plan_current.json").read_text())["plan_id"] == plan["plan_id"]

    # the user approves, both fill; the next reads show it and reconcile explains every share
    w["fills"] = {"spy_qty": spy["params"]["quantity"], "spy_limit": spy["params"]["limit_price"],
                  "sol_qty": sol["params"]["quantity"], "sol_limit": sol["params"]["limit_price"],
                  "sol_ref": sol["params"]["ref_id"], "spent": total, "created": iso(datetime.now(UTC))}
    w["quote_time"] = datetime.now(UTC)
    do_reads(state, w, only={"get_portfolio", "get_equity_positions", "get_crypto_positions", "get_equity_orders",
                             "get_crypto_orders", "get_equity_quotes", "get_crypto_quotes"})
    capsys.readouterr()
    assert cli.main(["reconcile"]) == 0
    out = capsys.readouterr().out
    assert "RECONCILE ok" in out and "fill: equity SPY buy 4" in out
    ref = json.loads((state / "positions_reconciled.json").read_text())
    assert ref["equity"]["SPY"]["qty"] == 4.0
    assert ref["crypto"]["SOL"]["qty"] == pytest.approx(float(sol["params"]["quantity"]))
    assert len([e for e in journal(state) if e["event"] == "fill"]) == 2
    assert not (state / "BLOCK_BUYS").exists()
    assert cli.main(["plan", "--attempt", "2"]) == 0                    # an explicit re-quote may re-plan
    again = json.loads((state / "plan_current.json").read_text())
    assert again["attempt"] == 2 and again["orders"] == []              # positions now at target

    # status never shows account numbers; STOP blocks places at the hook
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert ACCT not in out and RHS not in out and "proposal_pending_approval?" in out
    assert cli.main(["stop", "e2e", "test"]) == 0
    r = hook(PRE, state, sol["tool"], sol["params"])
    assert r.returncode == 2 and b"STOP" in r.stderr
    for f in (state / "journal.jsonl", state / "hook.log", state / "ledger.json"):
        assert ACCT not in f.read_text() and RHS not in f.read_text()


def test_run_is_signals_reconcile_plan(state, monkeypatch, capsys):
    now = real_now()
    prepare(state, monkeypatch, now)
    assert cli.main(["run"]) == 0
    out = capsys.readouterr().out
    assert out.index("MONEYLINE DIGEST") < out.index("RECONCILE ok") < out.index("PLAN ")
    assert "no baseline yet" in out
    plan = json.loads((state / "plan_current.json").read_text())
    assert len(plan["orders"]) == 2
    assert cli.main(["calls"]) == 0
    assert "[1] preview_crypto_order" in capsys.readouterr().out


def test_run_slots_join_recent_waits_for_an_old_run(state, monkeypatch, capsys):
    """Slots + join_recent end to end: SPY flipped green recently and takes a slot; SOL has been green since its
    history began, so it takes no slot and waits for the next flip, and the digest and plan say why."""
    now = real_now()
    w = prepare(state, monkeypatch, now)
    w["coinbase"].frames["SOL-USD"] = trend(pd.date_range(end=pd.Timestamp(w["crypto_end"]) + pd.Timedelta(days=1),
                                                          periods=900, freq="D"), 150.0)
    raw = cfg_dict()
    raw["allocation"] = {"method": "slots", "slot_frac": 0.25, "priority": "crypto_first",
                         "class_max_frac": {"crypto": 0.60}}
    raw["entry"] = {"policy": "join_recent", "max_join_bars": 20}
    (state / "config.json").write_text(json.dumps(raw))
    assert cli.main(["run"]) == 0
    out = capsys.readouterr().out
    assert "entry join_recent: green" in out and "too late to join (max 20): waiting for the next flip" in out
    assert "SLOTS $500.00 each (0.25 x capital, crypto_first): held -; new SPY $500.00; waiting -" in out
    plan = json.loads((state / "plan_current.json").read_text())
    (o,) = plan["orders"]
    assert o["key"] == "SPY|SPY|buy|0" and o["params"]["quantity"] == "4"
    assert "new slot $500.00 (#1 by crypto_first)" in o["reason"]
    assert any(x["asset"] == "SOL" and "too late to join" in x["reason"] for x in plan["skipped"])
    assert hook(PRE, state, o["tool"], o["params"]).returncode == 0           # the hook checks plan orders only
    assert json.loads((state / "strategy_start.json").read_text())["date"] == plan["signals_date"]


def test_shadow_mode_previews_only_and_hook_blocks_place(state, monkeypatch, capsys):
    now = real_now()
    prepare(state, monkeypatch, now, live=False)
    assert cli.main(["run"]) == 0
    out = capsys.readouterr().out
    assert "SHADOW MODE: make ONLY the preview calls" in out
    plan = json.loads((state / "plan_current.json").read_text())
    calls = cli.plan_calls(plan)
    assert [c["kind"] for c in calls] == ["preview", "place", "preview", "place"]
    for line in out.splitlines():
        if line.startswith("[") and "place_" in line:
            assert "(shadow: do not call)" in line
    o = plan["orders"][0]
    assert hook(PRE, state, o["preview_tool"], o["preview_params"]).returncode == 0
    r = hook(PRE, state, o["tool"], o["params"])
    assert r.returncode == 2 and b"shadow" in r.stderr


def test_reconcile_unexplained_change_blocks_buys(state, monkeypatch, capsys):
    now = real_now()
    w = prepare(state, monkeypatch, now)
    assert cli.main(["reconcile"]) == 0                   # baseline: no positions
    w["fills"] = {"spy_qty": "3", "spy_limit": "100.00", "sol_qty": "0", "sol_limit": "150.00", "sol_ref": None,
                  "spent": 300.0, "created": iso(datetime.now(UTC))}
    do_reads(state, w, only={"get_portfolio", "get_equity_positions", "get_crypto_positions", "get_equity_orders",
                             "get_crypto_orders"})
    assert cli.main(["reconcile"]) == 1                   # a filled order this system never placed
    assert (state / "BLOCK_BUYS").exists()
    assert cli.main(["reconcile", "--accept"]) == 0
    assert json.loads((state / "positions_reconciled.json").read_text())["equity"]["SPY"]["qty"] == 3.0


# ------------------------------------------------------------------ signals.py

def asset(name, cls="crypto", mode="immediate", enabled=True, **signal):
    sig = {"source": "computed", "feed": "coinbase", "symbol": f"{name}-USD"} if not signal else signal
    return {"name": name, "class": cls, "enabled": enabled, "alloc_frac": 0.1, "mode": mode, "signal": sig,
            "vehicle": {"type": "equity", "symbol": f"{name}X"}}


def mkcfg(*assets, min_bars=300):
    return validate({"account": {"account_number": ACCT, "rhs_account_number": RHS}, "capital": {"max_usd": 1000},
                     "limits": {"min_bars": min_bars}, "assets": list(assets)})


NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)          # Monday 11:00 ET: crypto bar 10-18, stock session 10-16


def patch_bars(monkeypatch, frames):
    def get_bars(a, cfg, now_utc=None, inbox_dir=None):
        f = frames[a["name"]]
        if isinstance(f, Exception):
            raise f
        return f
    monkeypatch.setattr(feeds, "get_bars", get_bars)


def test_signal_record_has_spec_fields_and_split_tranches(monkeypatch):
    values = walk(700, seed=7)
    tt = tranche_targets(redate(values, date(2026, 10, 18)), [(0.5, 1, 1), (0.5, 5, 5)])
    i = int(np.flatnonzero((tt["target_frac"].to_numpy() == 0.5) & tt["g0"].to_numpy())[-1])
    df = redate(values[: i + 1], date(2026, 10, 18))               # ends on a half-in bar
    patch_bars(monkeypatch, {"ETH": df})
    cfg = mkcfg(asset("ETH", mode="split"))
    s = sg.compute_signals(cfg, NOW)
    a = s["assets"][0]
    for k in ("name", "class", "mode", "source", "signal_symbol", "vehicle_type", "vehicle_symbol", "bar_date",
              "expected_bar_date", "close", "tranches", "target_frac", "prev_target_frac", "changed", "line_n1",
              "dist_to_line_pct", "atr10", "errors", "warnings"):
        assert k in a, k
    assert a["bar_date"] == a["expected_bar_date"] == "2026-10-18" and a["errors"] == []
    assert a["target_frac"] == 0.5 and [t["green"] for t in a["tranches"]] == [True, False]
    for t in a["tranches"]:
        assert set(t) == {"weight", "n_entry", "n_exit", "green", "pending", "line", "last_flip_date",
                          "last_green_flip_date", "bars_since_green_flip", "flip_close"}
    assert a["tranches"][1]["n_entry"] == 5 and 0 <= a["tranches"][1]["pending"] <= 4
    assert a["tranches"][0]["line"] == pytest.approx(a["line_n1"])
    assert a["dist_to_line_pct"] == pytest.approx((a["line_n1"] / a["close"] - 1) * 100, abs=1e-3)
    json.dumps(s)                                                     # serialisable
    text = sg.format_digest(s)
    assert "PARTIAL" in text and "tranche 2 (w 0.50, N 5/5): red" in text


def test_signal_flip_on_last_bar_is_new_and_exit(monkeypatch):
    days = pd.date_range(end="2026-10-18", periods=500, freq="D")
    df = trend(days, 100.0)
    df.iloc[-1] = [df.close.iloc[-2], df.close.iloc[-2], df.close.iloc[-2] * 0.84, df.close.iloc[-2] * 0.85]
    patch_bars(monkeypatch, {"ETH": df})
    s = sg.compute_signals(mkcfg(asset("ETH")), NOW)
    a = s["assets"][0]
    assert a["target_frac"] == 0.0 and a["prev_target_frac"] == 1.0 and a["changed"]
    assert a["tranches"][0]["last_flip_date"] == "2026-10-18" and a["bars_in_state"] == 0
    assert any("big wick" in x for x in a["warnings"])
    text = sg.format_digest(s)
    assert "NEW" in text and "1.00->0.00" in text and "EXIT" not in text and sg.SIGNAL_NOTE in text


def test_signal_errors_never_raise_and_block_the_asset(monkeypatch, capsys):
    days = pd.date_range(end="2026-10-17", periods=500, freq="D")      # one bar short of the closed bar 10-18
    patch_bars(monkeypatch, {"STALE": trend(days, 50.0), "DOWN": feeds.DataError("coinbase down"),
                             "OK": trend(pd.date_range(end="2026-10-18", periods=500, freq="D"), 50.0),
                             "OFF": feeds.DataError("not asked")})
    cfg = mkcfg(asset("STALE"), asset("DOWN"), asset("OK"), asset("OFF", enabled=False))
    s = sg.compute_signals(cfg, NOW)
    by = {a["name"]: a for a in s["assets"]}
    assert set(by) == {"STALE", "DOWN", "OK"}
    assert any("expected 2026-10-18" in e for e in by["STALE"]["errors"])
    assert by["DOWN"]["errors"] == ["data: DataError: coinbase down"] and by["DOWN"]["target_frac"] is None
    assert by["OK"]["errors"] == [] and by["OK"]["target_frac"] == 1.0
    assert "ERROR: no trade" in sg.format_digest(s) and "-%" not in sg.format_digest(s)
    assert {a["name"] for a in sg.compute_signals(cfg, NOW, include_disabled=True)["assets"]} >= {"OFF"}
    from agentic.planner import make_plan
    snap = {"total_value": 1000.0, "cash": 1000.0, "buying_power": 1000.0, "quotes": {}, "errors": [],
            "warnings": [], "equity_positions": {}, "crypto_positions": {}, "open_orders": [], "orders": []}
    plan = make_plan(s, snap, cfg, NOW, flags={}, placed_today_usd=0.0, journal=[])
    assert {x["asset"] for x in plan["skipped"]} >= {"STALE", "DOWN"}


def test_signals_class_filter_and_equity_expected_session(monkeypatch):
    eq = trend(cal.trading_days(date(2024, 10, 1), date(2026, 10, 16)), 400.0)
    patch_bars(monkeypatch, {"SPY": eq, "ETH": feeds.DataError("not asked")})
    cfg = mkcfg(asset("SPY", cls="equity", source="computed", feed="robinhood", symbol="SPY"), asset("ETH"))
    s = sg.compute_signals(cfg, NOW, classes=["equity"])
    assert [a["name"] for a in s["assets"]] == ["SPY"]
    assert s["assets"][0]["expected_bar_date"] == "2026-10-16" and s["assets"][0]["errors"] == []
    assert s["equity_bar_date"] == "2026-10-16" and s["crypto_bar_date"] == "2026-10-18"


def tv_csv(path, last_closed: date, final=(-1, 5), forming=(1, 0), n=400, saved=NOW):
    """A TradingView export saved at `saved`: bull regime, then closes below the level counting up to `final`;
    plus a forming bar."""
    days = pd.date_range(end=pd.Timestamp(last_closed) + pd.Timedelta(days=1), periods=n, freq="D")
    d = np.full(n, -1.0)
    cnt = np.zeros(n)
    close = np.full(n, 110.0)
    d[-2], cnt[-2] = final
    for k in range(1, int(final[1]) + 1):                 # the counting closes before the final closed bar
        cnt[-2 - (int(final[1]) - k)] = k
        close[-2 - (int(final[1]) - k)] = 95.0
    d[-1], cnt[-1] = forming
    close[-1] = 94.0
    t = ((days - EPOCH) // pd.Timedelta(seconds=1)).astype(int)
    pd.DataFrame({"time": t, "open": close, "high": close + 1, "low": close - 1, "close": close,
                  "MoneyLine Level": 100.0, "Direction": d, "ConfirmCount": cnt}).to_csv(path, index=False)
    os.utime(path, (saved.timestamp(), saved.timestamp()))


@pytest.mark.parametrize("how, target", [("direction", 0.5), ("count", 0.0)])
def test_tv_export_signal_and_confirm_convention(tmp_path, how, target):
    f = tmp_path / "COINBASE_ETHUSD_1D_test.csv"
    tv_csv(f, date(2026, 10, 18))
    a = asset("ETH-TV", mode="split", source="tv_export", path=str(tmp_path / "COINBASE_ETHUSD_1D*.csv"),
              tv_confirm=how)
    s = sg.compute_signals(mkcfg(a), NOW)
    r = s["assets"][0]
    assert r["errors"] == [], r["errors"]
    assert r["bar_date"] == "2026-10-18" and r["signal_file"] == f.name and r["close"] == 95.0   # forming bar dropped
    assert r["target_frac"] == target and r["line_n1"] == 100.0
    assert [t["n_entry"] for t in r["tranches"]] == [1, 5] and r["tranches"][1]["pending"] == 5
    assert r["tranches"][0]["green"] is False


def test_tv_export_stale_early_or_missing_is_an_error(tmp_path):
    f = tmp_path / "COINBASE_ETHUSD_1D.csv"
    tv_csv(f, date(2026, 10, 16))                          # rows end 10-17; bar 10-18 has closed
    a = asset("ETH-TV", mode="immediate", source="tv_export", path=str(f))
    r = sg.compute_signals(mkcfg(a), NOW)["assets"][0]
    assert any("export a fresh CSV" in e for e in r["errors"])
    tv_csv(f, date(2026, 10, 17), saved=datetime(2026, 10, 18, 23, 50, tzinfo=UTC))   # 10-18 row still forming
    r = sg.compute_signals(mkcfg(a), NOW)["assets"][0]
    assert r["bar_date"] == "2026-10-18" and any("before bar 2026-10-18 closed" in e for e in r["errors"])
    tv_csv(f, date(2026, 10, 17), saved=datetime(2026, 10, 19, 0, 5, tzinfo=UTC))
    assert sg.compute_signals(mkcfg(a), NOW)["assets"][0]["errors"] == []
    a["signal"]["path"] = str(tmp_path / "nothing*.csv")
    r = sg.compute_signals(mkcfg(a), NOW)["assets"][0]
    assert r["errors"] and r["errors"][0].startswith("data: FileNotFoundError")


def test_write_and_latest_signals(state, monkeypatch):
    patch_bars(monkeypatch, {"ETH": trend(pd.date_range(end="2026-10-18", periods=400, freq="D"), 10.0)})
    s = sg.compute_signals(mkcfg(asset("ETH")), NOW)
    f = sg.write_signals(s)
    assert f == paths()["signals"] / "signals_2026-10-19.json"
    old = dict(s, date="2026-10-01", signals_file="signals/signals_2026-10-01.json")
    sg.write_signals(old)
    got, gf = sg.latest_signals()
    assert gf == f and got["date"] == "2026-10-19"


# ------------------------------------------------------------------ cli.py

def test_init_never_overwrites_config(state, capsys):
    assert cli.main(["init"]) == 0
    cfgf = state / "config.json"
    cfgf.write_text('{"mine": 1}')
    assert cli.main(["init"]) == 0
    assert cfgf.read_text() == '{"mine": 1}' and "not overwritten" in capsys.readouterr().out
    for d in ("inbox", "signals", "plans", "digests"):
        assert (state / d).is_dir()


def test_fetch_list_order_params_and_chunking(state, monkeypatch, capsys):
    raw = cfg_dict()
    for k in range(11):
        raw["assets"].append({"name": f"S{k}", "class": "equity", "enabled": True, "alloc_frac": 0.02,
                              "signal": {"source": "computed", "feed": "robinhood", "symbol": f"S{k:02d}"},
                              "vehicle": {"type": "equity", "symbol": f"S{k:02d}"}})
    cfg = validate(raw)
    calls = cli.fetch_calls(cfg, NOW)
    tools = [c["tool"] for c in calls if c["tool"] != "get_equity_historicals"]
    assert tools == ["get_accounts", "get_portfolio", "get_equity_orders", "get_crypto_orders", "get_crypto_orders",
                     "get_equity_positions", "get_crypto_positions", "get_currency_pairs", "get_equity_quotes",
                     "get_crypto_quotes"]                                                    # orders before positions
    assert calls[4]["params"] == {"rhs_account_number": RHS, "state_group": "open"}     # open gtc orders of any age
    hist = [c["params"] for c in calls if c["tool"] == "get_equity_historicals"]
    assert len(hist) == 12 * 4 and all(len(h["symbols"]) == 1 for h in hist)          # no cache: backfill windows
    assert hist[0]["start_time"] == "2024-11-18T00:00:00Z" and hist[0]["bounds"] == "regular"
    by = {c["tool"]: c["params"] for c in calls}
    assert by["get_equity_orders"] == {"account_number": ACCT, "created_at_gte": "2026-09-19T00:00:00Z"}
    assert by["get_crypto_quotes"] == {"symbols": ["SOL-USD"], "rhs_account_number": RHS}
    ledger.write_json(paths()["positions_ref"], {"as_of": "2026-08-20T12:00:00Z", "equity": {}, "crypto": {}})
    assert cli.fetch_calls(cfg, NOW)[2]["params"]["created_at_gte"] == "2026-08-19T00:00:00Z"
    paths()["base"].mkdir(parents=True, exist_ok=True)
    paths()["config"].write_text(json.dumps(raw))
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    assert cli.main(["fetch-list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[1]["params"] == {"account_number": ACCT}
    raw["account"]["rhs_account_number"] = "FILL-IN-PRIVATE-CONFIG-ONLY"          # SOL is a direct-crypto vehicle
    paths()["config"].write_text(json.dumps(raw))
    assert cli.main(["fetch-list"]) == 2
    assert "rhs_account_number" in (out := capsys.readouterr().out) and "FILL-IN" not in out.split("get_accounts")[1]
    raw["account"]["account_number"] = "FILL-IN-PRIVATE-CONFIG-ONLY"
    paths()["config"].write_text(json.dumps(raw))
    assert cli.main(["fetch-list"]) == 2
    assert "get_accounts {}" in capsys.readouterr().out


def test_stop_flatten_resume(state, monkeypatch, capsys):
    assert cli.main(["init"]) == 0
    (state / "STOP").write_text("2026-10-19T14:00:00.000000Z an agent order went live without approval\n")
    assert cli.main(["stop", "testing"]) == 0 and cli.main(["flatten"]) == 0
    assert set(ledger.read_flags()) == {"STOP", "FLATTEN"}
    assert "testing" in ledger.read_flags()["STOP"] and "without approval" in ledger.read_flags()["STOP"]
    monkeypatch.setattr(sys, "stdin", io.StringIO("resume\n"))              # no terminal, as in an agent's shell
    assert cli.main(["resume"]) == 2 and set(ledger.read_flags()) == {"STOP", "FLATTEN"}
    err = capsys.readouterr().err
    assert "terminal" in err and "--yes" not in err                       # no hint at a bypass
    with pytest.raises(SystemExit):
        cli.main(["resume", "--yes"])                                     # the flag is gone
    assert set(ledger.read_flags()) == {"STOP", "FLATTEN"}

    class Tty(io.StringIO):
        def isatty(self):
            return True
    monkeypatch.setattr(sys, "stdin", Tty("resume\n"))
    assert cli.main(["resume", "--flag", "FLATTEN"]) == 0 and set(ledger.read_flags()) == {"STOP"}
    monkeypatch.setattr(sys, "stdin", Tty("no\n"))
    assert cli.main(["resume"]) == 1 and set(ledger.read_flags()) == {"STOP"}
    monkeypatch.setattr(sys, "stdin", Tty("resume\n"))
    assert cli.main(["resume"]) == 0 and ledger.read_flags() == {}
    assert "no flags set" in (cli.main(["resume"]) == 0 and capsys.readouterr().out)


def test_plan_without_signals_or_config(state, capsys):
    assert cli.main(["plan"]) == 2                          # no config
    assert cli.main(["init"]) == 0
    assert cli.main(["plan"]) == 2                          # no signals yet
    assert "no signals file" in capsys.readouterr().err
    assert cli.main(["calls"]) == 2


def test_backtest_cli_on_a_csv(state, tmp_path, capsys):
    v = walk(900, seed=3)
    df = redate(v, date(2026, 10, 16)).reset_index()
    f = tmp_path / "TEST.csv"
    df.to_csv(f, index=False)
    assert cli.main(["backtest", "--symbol", "TEST", "--csv", str(f), "--cost", "0.0002"]) == 0
    out = capsys.readouterr().out
    assert "using agentic/config.example.json" in out and "cost 0.02%/side" in out
    for m in ("immediate", "split", "confirm5", "BUY & HOLD"):
        assert m in out
    assert cli.main(["backtest", "--symbol", "TEST", "--csv", str(f), "--modes", "confirm5"]) == 0
    assert "immediate" not in capsys.readouterr().out
    for bad in (["--symbol", "TEST", "--csv", str(f), "--cost", "0.15"], ["--asset", "NOPE"], [],
                ["--symbol", "TEST", "--csv", str(f), "--modes", "split,bogus"], ["--symbol", "ZZQX"],
                ["--asset", "ETH-TV"]):
        assert cli.main(["backtest", *bad]) == 2, bad                     # one line, no traceback
        err = capsys.readouterr().err
        assert err.startswith("error: ") and "Traceback" not in err, bad


def test_module_entry_point_help():
    r = subprocess.run([sys.executable, "-m", "agentic", "--help"], cwd=REPO, capture_output=True, timeout=60)
    assert r.returncode == 0 and b"fetch-list" in r.stdout and b"backtest" in r.stdout


def _placed_plan(state, flags=(), attempt=1, skipped=()):
    now = datetime.now(UTC)
    plan = {"plan_id": "2026-10-18-aaaaaaaa", "created_at": iso(now), "valid_until": iso(now + timedelta(hours=5)),
            "attempt": attempt, "flags": list(flags), "orders": [], "cancels": [], "skipped": list(skipped)}
    state.mkdir(parents=True, exist_ok=True)
    (state / "plan_current.json").write_text(json.dumps(plan))
    ledger.append_journal({"event": "place", "plan_id": plan["plan_id"], "state": "proposal_pending_approval?"})
    return plan


def test_flatten_and_flag_changes_always_re_plan(state):
    """Regression: FLATTEN could not produce exit orders while today's plan had placed orders (review ops)."""
    now = datetime.now(UTC)
    _placed_plan(state)
    assert "NOT RE-PLANNING" not in str(cli.replan_problem(now, 1)) and cli.replan_problem(now, 1)
    assert cli.replan_problem(now, 2) is None
    ledger.set_flag("FLATTEN", "emergency exit")
    assert cli.replan_problem(now, 1) is None
    ledger.clear_flag("FLATTEN")
    ledger.set_flag("BLOCK_BUYS", "reconcile")
    assert cli.replan_problem(now, 1) is None                      # the flags changed since the plan was made
    _placed_plan(state, flags=["BLOCK_BUYS"])
    assert cli.replan_problem(now, 1)
    ledger.clear_flag("BLOCK_BUYS")
    _placed_plan(state)
    (state / "journal.jsonl").unlink()
    ledger.append_journal({"event": "place", "plan_id": "2026-10-18-aaaaaaaa", "state": "failed_or_unknown",
                           "error": "failed_or_unknown: timeout"})
    assert "1 of its orders" in cli.replan_problem(now, 1)         # an unknown outcome counts as placed


def test_replan_after_cancels_keeps_the_attempt(state):
    """Regression: the step-4 re-plan dropped --attempt and rebuilt the attempt-1 order (review p9 / ops requote)."""
    from agentic.planner import CANCEL_MSG
    now = datetime.now(UTC)
    assert cli.default_attempt(now) == 1
    held = {"asset": "ETH", "reason": f"ETH|ETHA|buy|0: ETHA has an open order; cancel first, {CANCEL_MSG}"}
    _placed_plan(state, attempt=2, skipped=[held])
    assert cli.default_attempt(now) == 2
    _placed_plan(state, attempt=2)
    assert cli.default_attempt(now) == 1
    for bad in ("0", "4"):
        with pytest.raises(SystemExit):
            cli.main(["plan", "--attempt", bad])


def test_reconcile_with_missing_captures_is_skipped_not_a_mismatch(state, capsys):
    assert cli.main(["init"]) == 0
    (state / "config.json").write_text(json.dumps(cfg_dict()))
    assert cli.main(["reconcile"]) == 1
    out = capsys.readouterr().out
    assert "RECONCILE SKIPPED" in out and "MISMATCH" not in out and not (state / "BLOCK_BUYS").exists()


def test_csv_feed_saved_mid_session_is_an_error(tmp_path):
    """Regression: a CSV saved at 11:00 ET passed as the closed bar at 16:30 ET (review check_csv_partial)."""
    f = tmp_path / "SPY.csv"
    eq = trend(cal.trading_days(date(2024, 10, 1), date(2026, 10, 16)), 400.0)
    eq.reset_index().to_csv(f, index=False)
    a = asset("SPY", cls="equity", source="computed", feed="csv", path=str(f))
    at_1630 = datetime(2026, 10, 16, 20, 30, tzinfo=UTC)
    for saved, bad in ((datetime(2026, 10, 16, 15, 0, tzinfo=UTC), True), (datetime(2026, 10, 16, 20, 25, tzinfo=UTC),
                                                                           False)):
        os.utime(f, (saved.timestamp(), saved.timestamp()))
        r = sg.compute_signals(mkcfg(a), at_1630)["assets"][0]
        assert any("before bar 2026-10-16 closed" in e for e in r["errors"]) is bad, r["errors"]


def test_tv_confirm_defaults_to_count(tmp_path):
    """Regression: the default read the 5-close tranche from Direction, one bar after ConfirmCount reached 5."""
    f = tmp_path / "COINBASE_ETHUSD_1D_test.csv"
    tv_csv(f, date(2026, 10, 18))
    a = asset("ETH-TV", mode="split", source="tv_export", path=str(tmp_path / "COINBASE_ETHUSD_1D*.csv"))
    r = sg.compute_signals(mkcfg(a), NOW)["assets"][0]
    assert r["tv_confirm"] == "count" and r["target_frac"] == 0.0
