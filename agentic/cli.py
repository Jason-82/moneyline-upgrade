"""`.venv/Scripts/python.exe -m agentic <command>` (Git Bash): the operator's entry point (SPEC section 12; runbook
in agentic/README.md).

Exit codes: 0 ok, 1 something needs attention (signal errors, plan errors, reconcile mismatch), 2 cannot run
(no config, no signals, missing data, bad arguments).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentic import ledger
from agentic.config import EXAMPLE, REPO, ConfigError, cli_command, ensure_dirs, load_config, paths, validate

UTC = timezone.utc
CRYPTO_COST, ETF_COST = 0.0095, 0.0002        # per side: Robinhood direct crypto (default route), spot ETF / stock


class CliError(Exception):
    """A bad argument or missing input: one line on stderr, exit 2."""


def _now() -> datetime:
    """Current time; tests monkeypatch this (there is deliberately no --now flag: plans must use real time)."""
    return datetime.now(UTC)


def _rel(f: Path) -> str:
    try:
        return Path(f).relative_to(paths()["base"]).as_posix()       # forward slashes: Git Bash on Windows
    except ValueError:
        return Path(f).as_posix()


def _placeholder(v) -> bool:
    return not v or str(v).upper().startswith("FILL-IN")


def _crypto_vehicles(cfg: dict) -> list[dict]:
    return [a for a in cfg["assets"] if a.get("enabled") and a["vehicle"]["type"] == "crypto"]


# ------------------------------------------------------------------ init / flags / status

def cmd_init(args) -> int:
    p = ensure_dirs()
    if p["config"].exists():
        print(f"config exists, not overwritten: {p['config']}")
    else:
        shutil.copyfile(EXAMPLE, p["config"])
        try:
            os.chmod(p["config"], 0o600)
        except OSError:
            pass
        print(f"created {p['config']} from the example (live=false, shadow mode)")
    base = p["base"].resolve()
    if base.is_relative_to(REPO) and not base.is_relative_to(REPO / "private"):
        print(f"WARNING: {base} is inside the public repo but not under private/: make sure git ignores it")
    print("next: fill in account.account_number and account.rhs_account_number there (from get_accounts, the "
          f"account with agentic_allowed=true), choose assets and modes, then run `{cli_command()} doctor` and "
          f"`{cli_command()} fetch-list`")
    return 0


def cmd_flag(args) -> int:
    name = args.cmd.upper()
    reason = f"{ledger.iso_z(_now())} " + (" ".join(args.reason) or f"set by `{cli_command()} {args.cmd}`")
    prior = ledger.read_flags().get(name)                # keep e.g. a STOP reason written by the hook
    ledger.set_flag(name, f"{prior}\n{reason}" if prior else reason)
    if name == "STOP":
        print("STOP set: the hook blocks every place call. To pull open orders: `fetch-list`, make the reads, then "
              "`plan` - it lists a cancel for each of this system's open orders; make those cancel calls.")
    else:
        print("FLATTEN set: every target is 0 and only sells of the sleeve's own shares are allowed. Run `fetch-list` "
              "and `run` to get the exit orders; the new plan replaces the current one and cancels its open buys. "
              "Reject any buy proposals still waiting in the Robinhood app.")
    return 0


def cmd_resume(args) -> int:
    active = ledger.read_flags()
    names = [args.flag.upper()] if args.flag else list(active)
    names = [n for n in names if n in active]
    if not names:
        print("no flags set")
        return 0
    for n in names:
        print(f"{n}: {active[n] or '(no reason recorded)'}")
    if "STOP" in names:
        print("Before resuming after a STOP: check the Robinhood app for unexpected orders and confirm Trade approvals "
              "are ON (Agent Settings -> Safety Controls).")
    if "BLOCK_BUYS" in names:
        print("BLOCK_BUYS usually comes from reconcile: check positions, then `reconcile --accept` to adopt them.")
    if not sys.stdin.isatty():                    # an agent's shell has no terminal: only the user may clear flags
        print("refusing to clear flags without an interactive terminal: the user must run this in a terminal",
              file=sys.stderr)
        return 2
    if input(f"type 'resume' to clear {', '.join(names)}: ").strip().lower() != "resume":
        print("not cleared")
        return 1
    for n in names:
        ledger.clear_flag(n)
    print(f"cleared {', '.join(names)}")
    return 0


def cmd_status(args) -> int:
    from agentic.signals import latest_signals
    p = paths()
    now = _now()
    try:
        cfg = load_config()
        print(f"config: ok, {'LIVE' if cfg['live'] else 'SHADOW (live=false)'}, "
              f"{sum(1 for a in cfg['assets'] if a.get('enabled'))} enabled assets, "
              f"capital max ${float(cfg['capital']['max_usd']):,.0f}, max_day_usd {cfg['limits']['max_day_usd']}, "
              f"allocation {cfg['allocation']['method']}, entry {cfg['entry']['policy']}")
    except ConfigError as e:
        cfg = None
        print(f"config: {e}")
    flags = ledger.read_flags()
    print("flags: " + (", ".join(f"{k} ({v})" if v else k for k, v in flags.items()) if flags else "none"))
    sig, f = latest_signals()
    if sig:
        print(f"signals: {f.name} generated {sig.get('generated_at')}")
        for a in sig.get("assets", []):
            err = f"  ERRORS {len(a['errors'])}" if a.get("errors") else ""
            print(f"  {a['name']:<9} bar {a.get('bar_date')}  target {a.get('target_frac')}  "
                  f"prev {a.get('prev_target_frac')}{'  NEW' if a.get('changed') else ''}{err}")
    else:
        print(f"signals: none yet (`{cli_command()} signals`)")
    plan = ledger.read_json(p["plan_current"], None)
    if isinstance(plan, dict):
        vu = ledger.parse_ts(plan.get("valid_until"))
        state = "expired" if vu is None or now >= vu else "valid"
        print(f"plan: {plan.get('plan_id')} created {plan.get('created_at')} valid until {plan.get('valid_until')} "
              f"({state}), {'LIVE' if plan.get('live') else 'SHADOW'}, {len(plan.get('orders') or [])} orders, "
              f"{len(plan.get('cancels') or [])} cancels, {len(plan.get('errors') or [])} errors")
    else:
        print("plan: none")
    cap = f" of max_day_usd {cfg['limits']['max_day_usd']}" if cfg else ""
    print(f"ledger {ledger.day_key(now)} (ET): ${ledger.placed_usd(now):,.2f} placed{cap}")
    caps = sorted(p["inbox"].glob("*.json")) if p["inbox"].is_dir() else []
    print(f"inbox: {len(caps)} captures" + (f", newest {caps[-1].name.split('_', 1)[0]}" if caps else ""))
    tail = ledger.read_journal()[-args.n:]
    print(f"journal (last {len(tail)}):")
    for e in tail:
        bits = [str(e.get(k)) for k in ("event", "tool", "key", "state") if e.get(k) not in (None, "")]
        usd = f" ${float(e['notional_usd']):,.2f}" if ledger.num(e.get("notional_usd")) is not None else ""
        err = " ERROR" if e.get("error") else ""
        print(f"  {e.get('ts')} {' '.join(bits)}{usd}{err}")
    return 0


# ------------------------------------------------------------------ fetch-list

def _orders_since(now: datetime) -> str:
    ref = ledger.read_json(paths()["positions_ref"], None)
    as_of = ledger.parse_ts(ref.get("as_of")) if isinstance(ref, dict) else None
    start = now - timedelta(days=30) if as_of is None else min(as_of - timedelta(days=1), now - timedelta(days=7))
    return f"{start.date().isoformat()}T00:00:00Z"


def fetch_calls(cfg: dict, now_utc=None) -> list[dict]:
    """The Robinhood MCP read calls for this run, in order, with exact arguments ({tool, params, why})."""
    from agentic.data import history_days
    from agentic.snapshot import pair_for
    now = now_utc or _now()
    acct = cfg["account"]
    an, rhs = str(acct.get("account_number") or ""), str(acct.get("rhs_account_number") or "")
    enabled = [a for a in cfg["assets"] if a.get("enabled")]
    crypto = bool(_crypto_vehicles(cfg))
    since = _orders_since(now)
    calls = [dict(tool="get_accounts", params={}, why="confirm the agentic account (agentic_allowed=true)"),
             dict(tool="get_portfolio", params={"account_number": an}, why="total value, cash, buying power"),
             dict(tool="get_equity_orders", params={"account_number": an, "created_at_gte": since},
                  why="open orders and recent fills (orders before positions)")]
    if crypto:
        calls.append(dict(tool="get_crypto_orders", params={"rhs_account_number": rhs, "created_at_gte": since},
                          why="recent crypto orders and fills"))
        calls.append(dict(tool="get_crypto_orders", params={"rhs_account_number": rhs, "state_group": "open"},
                          why="every open crypto order, however old (gtc lasts 90 days)"))
    calls.append(dict(tool="get_equity_positions", params={"account_number": an}, why="stock/ETF positions"))
    if crypto:
        calls.append(dict(tool="get_crypto_positions", params={"rhs_account_number": rhs}, why="crypto positions"))
        calls.append(dict(tool="get_currency_pairs", params={"limit": 100},
                          why="crypto order size and price increments"))
    rh = [a for a in enabled if a["signal"].get("source") == "computed" and a["signal"].get("feed") == "robinhood"]
    if rh:
        start = (now - timedelta(days=max(history_days(a, cfg) for a in rh))).date().isoformat()
        syms = sorted({str(a["signal"]["symbol"]).upper() for a in rh})
        for i in range(0, len(syms), 10):
            calls.append(dict(tool="get_equity_historicals",
                              params={"symbols": syms[i:i + 10], "start_time": f"{start}T00:00:00Z",
                                      "interval": "day", "bounds": "regular", "adjustment_type": "split"},
                              why="daily split-adjusted bars for stock signals"))
    eq = sorted({str(a["vehicle"]["symbol"]).upper() for a in enabled if a["vehicle"]["type"] == "equity"})
    if eq:
        calls.append(dict(tool="get_equity_quotes", params={"symbols": eq}, why="prices for sizing (fetch last)"))
    if crypto:
        pairs = sorted({pair_for(a["vehicle"]["symbol"]) for a in _crypto_vehicles(cfg)})
        calls.append(dict(tool="get_crypto_quotes", params={"symbols": pairs, "rhs_account_number": rhs},
                          why="crypto prices on this account's routing (fetch last)"))
    return calls


def cmd_fetch_list(args) -> int:
    cfg = load_config()
    acct = cfg["account"]
    missing = [k for k in ("account_number", "rhs_account_number")
               if _placeholder(acct.get(k)) and (k == "account_number" or _crypto_vehicles(cfg))]
    if missing:
        print(f"account.{' and account.'.join(missing)} not filled in. Make this call first, then put the agentic "
              "account's account_number and rhs_account_number (agentic_allowed=true) into config.json:\n"
              " 1. get_accounts {}")
        return 2
    calls = fetch_calls(cfg)
    if args.json:
        print(json.dumps(calls, indent=1))
        return 0
    print("Make these Robinhood MCP read calls now, in this order, with exactly these arguments (the PostToolUse hook "
          "saves every result to the inbox). If a result has a non-empty \"next\", repeat the same call with "
          "\"cursor\" set to that value, verbatim, until \"next\" is empty.")
    for i, c in enumerate(calls, 1):
        print(f"{i:>2}. {c['tool']} {json.dumps(c['params'])}    # {c['why']}")
    print(f"Then run: {cli_command()} run")
    return 0


# ------------------------------------------------------------------ signals / plan / run / reconcile

def _signals(args, cfg, now) -> tuple[dict, int]:
    from agentic.signals import compute_signals, format_digest, write_digest, write_signals
    classes = [args.cls] if getattr(args, "cls", None) else None
    sig = compute_signals(cfg, now, paths()["inbox"], include_disabled=getattr(args, "all", False), classes=classes)
    f = write_signals(sig)
    text = format_digest(sig)
    d = write_digest(sig, text)
    print(text)
    print(f"signals: {_rel(f)}  digest: {_rel(d)}")
    bad = [a["name"] for a in sig["assets"] if a["enabled"] and a["errors"]]
    if bad:
        print(f"ALERT: signal errors for {', '.join(bad)}: these assets will not trade today", file=sys.stderr)
    return sig, 1 if bad else 0


def cmd_signals(args) -> int:
    cfg = load_config()
    ensure_dirs()
    return _signals(args, cfg, _now())[1]


def plan_calls(plan: dict) -> list[dict]:
    """Tool calls in execution order: cancels, then per order its preview and its place (sells before buys)."""
    out = [dict(tool=c["tool"], params=c["params"], kind="cancel", note=f"{c.get('symbol')} {c.get('side')}: "
                                                                        f"{c.get('reason')}")
           for c in plan.get("cancels") or []]
    for o in plan.get("orders") or []:
        out.append(dict(tool=o["preview_tool"], params=o["preview_params"], kind="preview", note=o["key"]))
        out.append(dict(tool=o["tool"], params=o["params"], kind="place",
                        note=f"{o['key']} ${float(o['notional_usd']):,.2f}"))
    return out


def format_calls(plan: dict) -> str:
    calls = plan_calls(plan)
    if not calls:
        return "EXACT TOOL CALLS: none"
    live = bool(plan.get("live"))
    lines = ["EXACT TOOL CALLS - copy each params object verbatim (all values are strings; never edit, round or "
             "re-type them). Preview before place. Stop at the first hook block or tool error."]
    if not live:
        lines.append("SHADOW MODE: make ONLY the preview calls. Cancels and places below are what a live run would "
                     "do; do not make them.")
    for i, c in enumerate(calls, 1):
        skip = not live and c["kind"] != "preview"
        tag = "  (shadow: do not call)" if skip else ""
        lines.append(f"[{i}] {c['tool']} {json.dumps(c['params'])}{tag}    # {c['note']}")
    return "\n".join(lines)


def _valid_plan(now) -> dict | None:
    plan = ledger.read_json(paths()["plan_current"], None)
    if not isinstance(plan, dict):
        return None
    vu = ledger.parse_ts(plan.get("valid_until"))
    return plan if vu is not None and now < vu else None


def default_attempt(now) -> int:
    """`plan` without --attempt: the current plan's attempt while it is valid and held orders back behind cancels
    (the re-plan after those cancels settle must keep the wider collar), else 1."""
    from agentic.planner import CANCEL_MSG
    plan = _valid_plan(now)
    if plan and any(isinstance(x, dict) and CANCEL_MSG in str(x.get("reason")) for x in plan.get("skipped") or []):
        return min(max(int(plan.get("attempt") or 1), 1), 3)
    return 1


def replan_problem(now, attempt: int) -> str | None:
    """Why a new plan must not replace the current one: it is still valid and has placed orders at this attempt
    (a new plan would cancel or duplicate proposals still awaiting approval). None if re-planning is fine: no valid
    plan, a higher attempt, or the flags changed since it was made (STOP and FLATTEN must always re-plan)."""
    plan = _valid_plan(now)
    if plan is None or attempt > int(plan.get("attempt") or 1):
        return None
    flags = ledger.read_flags()
    if "STOP" in flags or "FLATTEN" in flags or sorted(flags) != sorted(plan.get("flags") or []):
        return None
    placed = [e for e in ledger.read_journal() if e.get("event") == "place" and e.get("plan_id") == plan.get("plan_id")
              and (not e.get("error") or e.get("state") == ledger.FAILED)]
    if not placed:
        return None
    return (f"plan {plan.get('plan_id')} is valid until {plan.get('valid_until')} and {len(placed)} of its orders "
            "were placed (awaiting approval or fills): a new plan would cancel or duplicate them. Use `calls` or "
            f"`status`; to re-quote unfilled orders run `plan --attempt {attempt + 1}`")


def _plan(args, cfg, now) -> tuple[dict | None, int]:
    from agentic.planner import format_plan, make_plan, write_plan
    from agentic.signals import latest_signals
    from agentic.snapshot import build_snapshot
    attempt = args.attempt or default_attempt(now)
    why = None if getattr(args, "replan", False) else replan_problem(now, attempt)
    if why:
        print(f"NOT RE-PLANNING: {why}", file=sys.stderr)
        return None, 1
    sig, f = latest_signals()
    if sig is None:
        print(f"no signals file: run `{cli_command()} signals` (or `run`)", file=sys.stderr)
        return None, 2
    snap = build_snapshot(paths()["inbox"], cfg, now)
    plan = make_plan(sig, snap, cfg, now, attempt=attempt)
    pf = write_plan(plan)
    print(format_plan(plan))
    print(format_calls(plan))
    print(f"plan: {_rel(pf)} (copied to plan_current.json); signals: {f.name}")
    if plan["orders"] or plan["cancels"]:
        print("Do not re-run `plan` while these orders await approval or fills: a new plan cancels them. "
              f"Use `{cli_command()} calls` to show this plan again.")
    return plan, 1 if plan["errors"] else 0


def cmd_plan(args) -> int:
    return _plan(args, load_config(), _now())[1]


def _reconcile(cfg, now, accept: bool) -> int:
    from agentic.snapshot import build_snapshot
    snap = build_snapshot(paths()["inbox"], cfg, now)
    res = ledger.reconcile_snapshot(snap, now_utc=now, accept=accept, initial_sleeve=cfg.get("sleeve_initial_qty"))
    if res.get("skipped"):
        print("RECONCILE SKIPPED (missing or stale captures: nothing compared)")
        for line in res["report"]:
            print(f"  {line}")
        return 1
    print("RECONCILE " + ("ok" if res["ok"] else "accepted" if accept else "MISMATCH"))
    for line in res["report"] + res["notes"]:
        print(f"  {line}")
    for fl in res["fills"]:
        print(f"  fill: {fl['kind']} {fl['symbol']} {fl['side']} {fl['filled_delta']:g} "
              f"(order {str(fl['order_id'])[:8]})")
    if res["block_buys"]:
        print("  BLOCK_BUYS written: exits stay allowed. Check positions in the app, then `reconcile --accept`.")
    if res["baseline_written"]:
        print("  baseline updated (positions_reconciled.json)")
    return 0 if res["ok"] or accept else 1


def cmd_reconcile(args) -> int:
    return _reconcile(load_config(), _now(), args.accept)


def cmd_run(args) -> int:
    cfg = load_config()
    ensure_dirs()
    now = _now()
    _, rc_sig = _signals(args, cfg, now)
    print()
    rc_rec = _reconcile(cfg, now, False)
    print()
    _, rc_plan = _plan(args, cfg, now)
    return max(rc_sig, rc_rec, rc_plan)


def cmd_doctor(args) -> int:
    from agentic.doctor import run
    return run()


def cmd_calls(args) -> int:
    plan = ledger.read_json(paths()["plan_current"], None)
    if not isinstance(plan, dict):
        print(f"no plan_current.json: run `{cli_command()} plan`", file=sys.stderr)
        return 2
    vu = ledger.parse_ts(plan.get("valid_until"))
    if vu is None or _now() >= vu:
        print(f"plan {plan.get('plan_id')} expired at {plan.get('valid_until')}: fetch again and re-run the plan; "
              "never re-send an old plan", file=sys.stderr)
        return 1
    print(f"plan {plan.get('plan_id')} valid until {plan.get('valid_until')}")
    print(format_calls(plan))
    return 0


# ------------------------------------------------------------------ backtest

def _find_asset(cfg: dict, args) -> dict:
    if args.symbol:
        cls = args.cls or "equity"
        feed = "coinbase" if cls == "crypto" else "csv"
        sym = args.symbol.upper()
        return validate({"capital": {"max_usd": 1}, "assets": [{
            "name": args.asset or sym, "class": cls, "signal": {"source": "computed", "feed": feed, "symbol": sym},
            "vehicle": {"type": "equity", "symbol": sym}}]})["assets"][0]
    for a in cfg["assets"]:
        if a["name"].upper() == str(args.asset).upper():
            return a
    raise CliError(f"no asset named {args.asset!r} in the config ({', '.join(a['name'] for a in cfg['assets'])}); "
                   "or pass --symbol SYM [--class crypto|equity]")


def cmd_backtest(args) -> int:
    import pandas as pd
    from agentic.backtest import compare_modes, compare_tv_modes, load_history
    from agentic.indicator import TV_MODES
    if not args.asset and not args.symbol:
        raise CliError("backtest needs --asset NAME (or --symbol SYM)")
    try:
        cfg = load_config()
    except ConfigError:
        cfg = validate(json.loads(EXAMPLE.read_text(encoding="utf-8")))
        print("(no config in the state dir: using agentic/config.example.json)")
    asset = _find_asset(cfg, args)
    modes = {k: v for k, v in cfg["modes"].items() if not k.startswith("_")}
    if args.modes:
        want = [m.strip() for m in args.modes.split(",") if m.strip()]
        unknown = [m for m in want if m not in modes]
        if unknown:
            raise CliError(f"unknown modes {unknown}; defined: {sorted(modes)}")
        modes = {m: modes[m] for m in want}
    if args.cost is not None and not 0 <= args.cost < 0.05:
        raise CliError("--cost is a fraction per side, e.g. 0.0015 for 0.15%")
    direct = asset["vehicle"]["type"] == "crypto"
    cost = args.cost if args.cost is not None else CRYPTO_COST if direct else ETF_COST
    crypto = asset["class"] == "crypto"
    ppy = 365 if crypto else 252
    tax = cfg.get("tax") or {}
    st, lt = float(tax.get("st_rate", 0.35)), float(tax.get("lt_rate", 0.20))
    hist = load_history(asset, cfg, csv=args.csv)
    if hist.attrs.get("note"):
        print(f"WARNING: {hist.attrs['note']}", file=sys.stderr)
    if asset["signal"].get("source") == "tv_export" and not args.csv:
        tv_modes = [m for m in modes if m in TV_MODES]
        how = str(asset["signal"].get("tv_confirm", "count")).lower()
        table = compare_tv_modes(hist, cost, ppy, modes=tv_modes, start=args.start, st_rate=st, lt_rate=lt,
                                 tv_confirm=how)
        src = f"TradingView export {Path(hist.attrs.get('path', '')).name} (new MoneyLine, tv_confirm={how})"
    else:
        table = compare_modes(hist, modes, cost, ppy, start=args.start, st_rate=st, lt_rate=lt)
        src = f"{asset['signal'].get('symbol') or args.csv} computed (old MoneyLine)"
    a = table.attrs
    print(f"{asset['name']}: {src}, {pd.Timestamp(a['start']).date()} to {pd.Timestamp(a['end']).date()}, "
          f"cost {cost * 100:.2f}%/side, {ppy} bars/yr, tax {st:.0%} short-term yearly / {lt:.0%} long-term once (B&H)")
    with pd.option_context("display.width", 200):
        print(table.round(2).to_string())
    if crypto and not direct:
        print("note: fills at the next crypto open, 7 days a week; the ETF route waits for the next NYSE session "
              "(analysis_2026/gate.py models that)")
    return 0


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=cli_command(), description="MoneyLine execution on the Robinhood agentic "
                                 "account. Runbook: agentic/README.md. State: private/agentic (or AGENTIC_STATE_DIR).")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")
    sub.add_parser("init", help="create the state dirs; copy the example config if missing").set_defaults(func=cmd_init)
    s = sub.add_parser("signals", help="compute signals (phase 1) and write the digest")
    s.add_argument("--all", action="store_true", help="include disabled assets")
    s.add_argument("--class", dest="cls", choices=("crypto", "equity"), help="only this asset class (cron: crypto)")
    s.set_defaults(func=cmd_signals)
    s = sub.add_parser("fetch-list", help="print the Robinhood read calls Claude must make now")
    s.add_argument("--json", action="store_true", help="machine-readable list")
    s.set_defaults(func=cmd_fetch_list)
    for name, fn, hlp in (("plan", cmd_plan, "build the snapshot and the plan; print the exact tool calls"),
                          ("run", cmd_run, "signals, then reconcile, then plan")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("--attempt", type=int, choices=(1, 2, 3), default=None,
                       help="re-quote attempt 1-3 (wider collar, new ref_ids); default 1, or the current plan's "
                            "attempt when it held orders back behind cancels")
        s.add_argument("--replan", action="store_true",
                       help="replace a valid plan that has placed orders (user only: cancels or duplicates them)")
        if name == "run":
            s.add_argument("--all", action="store_true", help=argparse.SUPPRESS)
        s.set_defaults(func=fn)
    sub.add_parser("calls", help="show the current plan's exact tool calls again").set_defaults(func=cmd_calls)
    sub.add_parser("doctor", help="check the install: Python, packages, AGENTIC_PYTHON, config, hooks, Git Bash "
                   "(README section 1)").set_defaults(func=cmd_doctor)
    s = sub.add_parser("reconcile", help="compare captured positions with expected; BLOCK_BUYS on mismatch")
    s.add_argument("--accept", action="store_true", help="adopt the captured positions as the new baseline")
    s.set_defaults(func=cmd_reconcile)
    s = sub.add_parser("status", help="flags, last signals and plan, today's ledger, journal tail")
    s.add_argument("-n", type=int, default=10, help="journal lines to show")
    s.set_defaults(func=cmd_status)
    for name, hlp in (("stop", "kill switch: block every place call"), ("flatten", "sell everything toward 0")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("reason", nargs="*")
        s.set_defaults(func=cmd_flag)
    s = sub.add_parser("resume", help="remove flag files (in a terminal only; asks for confirmation)")
    s.add_argument("--flag", choices=ledger.FLAGS, help="clear only this flag")
    s.set_defaults(func=cmd_resume)
    s = sub.add_parser("backtest", help="compare modes vs buy & hold for one asset")
    s.add_argument("--asset", help="asset name from the config")
    s.add_argument("--symbol", help="ad-hoc symbol instead of a config asset")
    s.add_argument("--class", dest="cls", choices=("crypto", "equity"), help="class of --symbol (default equity)")
    s.add_argument("--modes", help="comma-separated mode names (default: all in the config)")
    s.add_argument("--csv", help="local OHLC CSV instead of repo data / the live feed")
    s.add_argument("--start", help="YYYY-MM-DD (after the 120-bar warm-up)")
    s.add_argument("--cost", type=float, help="fraction per side (default 0.0095 direct crypto, 0.0002 otherwise)")
    s.set_defaults(func=cmd_backtest)
    return ap


def _utf8_output() -> None:
    """Windows: output to a pipe or file (Git Bash, Claude Code's Bash tool, cron.log) defaults to the ANSI code page,
    which cannot encode every character in a digest or an error. Write UTF-8 and never fail on a character."""
    if os.name != "nt":
        return
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None) -> int:
    _utf8_output()
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    except (CliError, FileNotFoundError, ValueError) as e:      # incl. agentic.data.DataError
        print(f"error: {e}", file=sys.stderr)
        return 2
