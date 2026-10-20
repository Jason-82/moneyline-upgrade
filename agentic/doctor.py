"""`doctor`: check the install (agentic/README.md section 1) and print one PASS / WARN / FAIL line per check.

Exit 0 when nothing FAILs, else 1. Never prints account numbers. The hook checks run the real PreToolUse hook as a
subprocess, with the interpreter the hook command would use, against a throwaway state dir (a fake config and an
empty live plan), so the user's journal, ledger and hook.log are untouched. Standard library only at import time, so
it runs before pandas is installed.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentic.config import (COIN_CODE, DEFAULT_EXCLUDE, EXAMPLE, REPO, STOCK_SUFFIX, ConfigError, cli_command,
                            coin_favorites, crypto_universe, equity_universe, favorite_names, load_config, paths)

UTC = timezone.utc
PRE_HOOK = REPO / "agentic" / "hooks" / "pre_tool_use.py"
PY = '"${AGENTIC_PYTHON:-python3}" -I "${CLAUDE_PROJECT_DIR}/agentic/hooks/'
HOOK_COMMANDS = {                                   # what .claude/settings.json must run (README section 1)
    "PreToolUse": PY + 'pre_tool_use.py" || exit 2',
    "PostToolUse": PY + 'post_tool_use.py"',
    "PostToolUseFailure": PY + 'post_tool_use.py"',
}
SAMPLE_TOOLS = ("mcp__robinhood-trading__place_equity_order", "mcp__claude_ai_Robinhood__get_accounts")
FAKE_ACCT, FAKE_RHS = "DOCTORTEST1", "DOCTORTEST2"   # the throwaway config's accounts: never the user's
GIT_BASH_PATHS = ("C:/Program Files/Git/bin/bash.exe", "C:/Program Files (x86)/Git/bin/bash.exe")
NO_GIT_BASH = ("without Git Bash, Claude Code runs the hooks in PowerShell, where the bash hook command does not run "
               "as written: the guard cannot work and a non-2 exit does not block the call. Install Git for Windows "
               "and do not use /moneyline until doctor passes")


def windows() -> bool:
    """os.name == 'nt' (a function so tests can simulate Windows without breaking pathlib)."""
    return os.name == "nt"


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []

    def add(self, status: str, name: str, detail: str) -> None:
        self.rows.append((status, name, detail))
        print(f"{status:<4}  {name:<15} {detail}", flush=True)

    @property
    def failed(self) -> int:
        return sum(1 for s, _, _ in self.rows if s == "FAIL")


def _posix(p) -> str:
    return Path(p).as_posix()


def _short(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except (ValueError, OSError):
        return _posix(p)


def _read_settings(d: Path, name: str) -> tuple[dict | None, str | None]:
    """(settings, problem). A UTF-8 BOM (an editor's "UTF-8 with BOM") is read past so the other checks still run, but
    it is reported: Claude Code is not known to accept it, and a settings file it cannot parse drops its hooks, deny
    rules or env."""
    f = d / name
    if not f.exists():
        return None, None
    try:
        raw = f.read_bytes()
        s = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as e:
        return None, f".claude/{name} is not valid JSON ({type(e).__name__}: {e})"
    if not isinstance(s, dict):
        return None, f".claude/{name} is not a JSON object"
    if raw.startswith(b"\xef\xbb\xbf"):
        return s, (f".claude/{name} starts with a UTF-8 byte order mark (saved as 'UTF-8 with BOM'): save it as plain "
                   f"UTF-8 so Claude Code is sure to read it (`code .claude/{name}`, then in VS Code click the "
                   "encoding in the status bar, 'Save with Encoding', 'UTF-8')")
    return s, None


def configured_python(local: dict | None, shared: dict | None) -> tuple[str | None, str]:
    """AGENTIC_PYTHON as Claude Code would set it for the hooks: settings env (local over shared) wins over the
    environment Claude Code was started from. (value, where it came from)."""
    for where, s in ((".claude/settings.local.json", local), (".claude/settings.json", shared)):
        env = s.get("env") if isinstance(s, dict) else None
        if isinstance(env, dict) and env.get("AGENTIC_PYTHON"):
            return str(env["AGENTIC_PYTHON"]), where
    v = os.environ.get("AGENTIC_PYTHON")
    return (v, "the environment") if v else (None, "")


def _as_local_path(v: str) -> Path:
    """A path as this Python sees it; on Windows a Git Bash path /c/Users/... becomes C:/Users/..."""
    m = re.fullmatch(r"/([A-Za-z])(/.*)?", v)
    if windows() and m:
        return Path(f"{m.group(1).upper()}:{m.group(2) or '/'}")
    return Path(v)


def find_git_bash() -> tuple[str | None, str]:
    """(bash.exe path, how it was found): CLAUDE_CODE_GIT_BASH_PATH, the usual install folders, or next to git.exe on
    PATH. Never the System32 / WindowsApps bash.exe, which is WSL's launcher."""
    env = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if env:
        return (env, "CLAUDE_CODE_GIT_BASH_PATH") if Path(env).is_file() else (None, f"CLAUDE_CODE_GIT_BASH_PATH "
                                                                                   f"points to a missing file {env}")
    cands = list(GIT_BASH_PATHS)
    if os.environ.get("LOCALAPPDATA"):
        cands.append(_posix(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Git" / "bin" / "bash.exe"))
    git = shutil.which("git")
    if git:
        gp = Path(git).resolve()
        cands += [_posix(parent / "bin" / "bash.exe") for parent in list(gp.parents)[:3]]
    for c in cands:
        low = c.replace("\\", "/").lower()
        if "/system32/" in low or "/windowsapps/" in low:
            continue
        if Path(c).is_file():
            return c, "install folder"
    return None, "not found in CLAUDE_CODE_GIT_BASH_PATH, " + ", ".join(GIT_BASH_PATHS) + " or next to git.exe"


def _fake_state(d: Path) -> None:
    """A throwaway state dir: the example config, live, with fake accounts, and a valid live plan with no orders."""
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    raw["live"] = True
    raw["account"] = dict(raw.get("account") or {}, account_number=FAKE_ACCT, rhs_account_number=FAKE_RHS)
    (d / "config.json").write_text(json.dumps(raw), encoding="utf-8")
    now = datetime.now(UTC)
    day = now.date().isoformat()
    iso = "%Y-%m-%dT%H:%M:%SZ"
    plan = {"plan_id": f"{day}-00000000", "signals_date": day, "created_at": (now - timedelta(minutes=1)).strftime(iso),
            "valid_until": (now + timedelta(hours=1)).strftime(iso), "live": True, "attempt": 1, "orders": [],
            "cancels": [], "account_number": FAKE_ACCT, "rhs_account_number": FAKE_RHS}
    (d / "plan_current.json").write_text(json.dumps(plan), encoding="utf-8")


def _event(short: str, ti: dict) -> bytes:
    return json.dumps({"session_id": "agentic-doctor", "hook_event_name": "PreToolUse", "cwd": str(REPO),
                       "tool_name": f"mcp__robinhood-trading__{short}", "tool_input": ti}).encode("utf-8")


PLACE_EVENT = _event("place_equity_order", {
    "account_number": FAKE_ACCT, "symbol": "SPY", "side": "buy", "type": "limit", "quantity": "1",
    "limit_price": "1.00", "time_in_force": "gfd", "market_hours": "regular_hours",
    "ref_id": "00000000-0000-0000-0000-000000000000"})
READ_EVENT = _event("get_accounts", {})


def _first_line(b: bytes) -> str:
    s = b.decode("utf-8", "replace").strip()
    return s.splitlines()[0][:200] if s else "(no output)"


def _check_hook_runs(rep: Report, name: str, argv: list[str], env: dict) -> None:
    """The hook must block an unplanned place (exit 2, its own BLOCKED message) and let a read through (exit 0)."""
    try:
        place = subprocess.run(argv, input=PLACE_EVENT, env=env, capture_output=True, timeout=60)
        read = subprocess.run(argv, input=READ_EVENT, env=env, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        rep.add("FAIL", name, f"cannot run {_posix(argv[0])}: {type(e).__name__}: {e}")
        return
    err = place.stderr.decode("utf-8", "replace")
    if place.returncode == 2 and "BLOCKED by agentic hook (place_equity_order)" in err and "no plan order" in err:
        rep.add("PASS", name, "place_equity_order with no matching plan order: blocked (exit 2)")
    else:
        rep.add("FAIL", name, f"place_equity_order with no matching plan order: exit {place.returncode}, wanted 2 "
                              f"with the hook's 'no plan order matches' block: {_first_line(place.stderr)}")
    if read.returncode == 0:
        rep.add("PASS", name, "get_accounts: allowed (exit 0)")
    else:
        rep.add("FAIL", name, f"get_accounts: exit {read.returncode}, wanted 0 (every Robinhood call would be "
                              f"blocked): {_first_line(read.stderr)}")


CLI_PROBE = ("import json, sys\n"
             "out = {'v': list(sys.version_info[:3])}\n"
             "try:\n"
             "    import pandas, numpy\n"
             "    out.update(pandas=pandas.__version__, numpy=numpy.__version__)\n"
             "except Exception as e:\n"
             "    out['err'] = type(e).__name__ + ': ' + str(e)\n"
             "print(json.dumps(out))\n")


def _check_cli_python(rep: Report, py: str) -> None:
    """The hooks need only the standard library, but /moneyline runs every CLI command with the same interpreter, so
    it needs Python 3.11+, pandas and numpy too. Run it the way the slash command does (from the repo root, no -I)."""
    shown = _posix(py)
    q = f'"{shown}"' if " " in shown else shown
    venv = ".venv/Scripts/python.exe" if windows() else ".venv/bin/python"
    use_venv = f"point AGENTIC_PYTHON at the repo venv's {venv} (README section 1)"
    fix = f"/moneyline runs every command with it. Run `{q} -m pip install pandas numpy tzdata`, or {use_venv}"
    try:
        r = subprocess.run([py, "-c", CLI_PROBE], cwd=str(REPO), capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        rep.add("FAIL", "CLI python", f"{shown} did not finish importing pandas and numpy within 120 s: {fix}")
        return
    except (OSError, subprocess.SubprocessError) as e:
        rep.add("FAIL", "CLI python", f"cannot run {shown}: {type(e).__name__}: {e}")
        return
    try:
        info = json.loads(r.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        v = tuple(int(x) for x in info["v"])
    except (ValueError, IndexError, KeyError, TypeError):
        rep.add("FAIL", "CLI python", f"cannot run {shown} as Python (exit {r.returncode}): {_first_line(r.stderr)}")
        return
    ver = ".".join(map(str, v))
    if v < (3, 11):
        rep.add("FAIL", "CLI python", f"{shown} is Python {ver}: the CLI needs 3.11 or newer, and /moneyline runs "
                                      f"every command with it: {use_venv}")
    elif info.get("err"):
        rep.add("FAIL", "CLI python", f"{shown} (Python {ver}) cannot import pandas and numpy ({info['err'][:120]}): "
                                      f"{fix}")
    else:
        rep.add("PASS", "CLI python", f"{shown}: Python {ver}, pandas {info.get('pandas')}, numpy {info.get('numpy')}")


def run(settings_dir: Path | None = None) -> int:
    settings_dir = Path(settings_dir) if settings_dir is not None else REPO / ".claude"
    rep = Report()
    cmd = cli_command()
    print(f"agentic doctor: repo {_posix(REPO)}")

    v = sys.version_info
    rep.add("PASS" if v >= (3, 11) else "FAIL", "python", f"{v.major}.{v.minor}.{v.micro}"
            + ("" if v >= (3, 11) else ": needs 3.11 or newer (README section 1)"))
    rep.add("PASS", "interpreter", _posix(sys.executable))

    shared, err_s = _read_settings(settings_dir, "settings.json")
    local, err_l = _read_settings(settings_dir, "settings.local.json")
    for e in (err_s, err_l):
        if e:
            rep.add("FAIL", "settings", e)

    # ---- AGENTIC_PYTHON: the interpreter the hook command runs
    val, where = configured_python(local, shared)
    hook_py = None
    if val:
        p = _as_local_path(val)
        if val.startswith("~") or "$" in val or "%" in val:
            rep.add("FAIL", "AGENTIC_PYTHON", f"{val} (from {where}): settings env values are copied literally, with "
                                              "no ~, $VAR or %VAR% expansion: write the full path, e.g. "
                                              "C:/Users/<you>/moneyline-upgrade/.venv/Scripts/python.exe")
        elif not p.is_file():
            rep.add("FAIL", "AGENTIC_PYTHON", f"{val} (from {where}) does not exist")
        else:
            hook_py = str(p)
            rep.add("PASS", "AGENTIC_PYTHON", f"{val} (from {where})")
    elif windows():
        rep.add("FAIL", "AGENTIC_PYTHON", "not set: the hooks would run `python3`, on Windows usually the Microsoft "
                                          "Store stub. Create .claude/settings.local.json (README section 1)")
        hook_py = sys.executable
    else:
        found = shutil.which("python3")
        hook_py = found or sys.executable
        rep.add("PASS" if found else "FAIL", "AGENTIC_PYTHON",
                f"not set: the hooks run python3 from PATH ({_posix(found)})" if found else
                "not set and no python3 on PATH: the hooks cannot start (set it in .claude/settings.local.json)")

    # ---- the CLI under AGENTIC_PYTHON: /moneyline runs every command as "${AGENTIC_PYTHON:-python3}" -m agentic
    if hook_py and os.path.normcase(os.path.abspath(hook_py)) != os.path.normcase(os.path.abspath(sys.executable)):
        _check_cli_python(rep, hook_py)

    # ---- packages and time zone (this interpreter)
    for mod in ("pandas", "numpy"):
        try:
            m = importlib.import_module(mod)
            rep.add("PASS", mod, getattr(m, "__version__", "importable"))
        except Exception as e:                     # noqa: BLE001 - any import failure is a FAIL line
            rep.add("FAIL", mod, f"not importable ({type(e).__name__}): {cmd.split(' -m ')[0]} -m pip install "
                                 "pandas numpy tzdata")
    from agentic import calendar as cal
    tzdata = importlib.util.find_spec("tzdata") is not None
    if cal.ET_SOURCE == "zoneinfo":
        rep.add("PASS", "time zone", "America/New_York from zoneinfo ("
                + ("tzdata package)" if tzdata else "system tz database; tzdata package not installed)"))
    else:
        rep.add("WARN", "time zone", "no tz database: using the built-in US Eastern rule (2007+ DST). Install "
                                     f"tzdata: {cmd.split(' -m ')[0]} -m pip install tzdata")

    # ---- state dir, config, git ignore
    p = paths()
    base = p["base"]
    if not base.is_dir():
        rep.add("FAIL", "state dir", f"{_short(base)} does not exist: run `{cmd} init`")
    else:
        try:
            fd, tmp = tempfile.mkstemp(dir=base, prefix=".doctor.", suffix=".tmp")
            os.close(fd)
            os.unlink(tmp)
            rep.add("PASS", "state dir", f"{_short(base)} is writable")
        except OSError as e:
            rep.add("FAIL", "state dir", f"{_short(base)} is not writable ({type(e).__name__})")
    cfg = None
    try:
        cfg = load_config()
        acct = cfg["account"]
        crypto = any(a.get("enabled") and a["vehicle"]["type"] == "crypto" for a in cfg["assets"])
        rep.add("PASS", "config", f"valid, {'LIVE' if cfg['live'] else 'SHADOW (live=false)'}, "
                                  f"{sum(1 for a in cfg['assets'] if a.get('enabled'))} enabled assets")
        missing = [k for k in ("account_number", "rhs_account_number") if (k == "account_number" or crypto)
                   and (not acct.get(k) or str(acct.get(k)).strip().upper().startswith("FILL-IN"))]
        if missing:
            rep.add("FAIL", "accounts", f"account.{' and account.'.join(missing)} not filled in: run /moneyline (it "
                                        "calls get_accounts) and copy them into config.json (README section 2)")
        else:
            rep.add("PASS", "accounts", "filled in (not shown)")
    except ConfigError as e:
        rep.add("FAIL", "config", str(e))
    except ValueError as e:                        # invalid JSON: the message names a line and column only
        rep.add("FAIL", "config", f"{_short(p['config'])} is not valid JSON: {e}")
    except Exception as e:                         # noqa: BLE001
        rep.add("FAIL", "config", f"cannot read ({type(e).__name__})")
    _check_ignored(rep, p["config"])
    _check_flags(rep)
    if cfg is not None:
        check_universe(rep, cfg, p)
        check_stocks(rep, cfg, p)

    # ---- settings.json hooks
    problems = []
    if shared is None and not err_s:
        problems.append(".claude/settings.json is missing")
    for event, want in HOOK_COMMANDS.items():
        entries = (shared or {}).get("hooks", {}).get(event) if isinstance((shared or {}).get("hooks"), dict) else None
        ok = False
        for entry in entries if isinstance(entries, list) else []:
            try:
                m = re.compile(str(entry.get("matcher", "")))
            except (re.error, AttributeError):
                continue
            if all(m.search(t) for t in SAMPLE_TOOLS) and any(
                    isinstance(h, dict) and h.get("type") == "command" and h.get("command") == want
                    for h in entry.get("hooks") or []):
                ok = True
        if not ok:
            problems.append(f"{event} does not run `{want}` for the Robinhood tools")
    for name, s in (("settings.json", shared), ("settings.local.json", local)):
        if isinstance(s, dict) and s.get("disableAllHooks"):
            problems.append(f".claude/{name} sets disableAllHooks")
    if problems:
        for prob in problems:
            rep.add("FAIL", "hooks", prob)
    else:
        rep.add("PASS", "hooks", "settings.json registers PreToolUse, PostToolUse and PostToolUseFailure")

    # ---- Git Bash (Windows): Claude Code runs the hooks and the Bash tool in it
    bash = None
    if windows():
        bash, how = find_git_bash()
        if bash:
            rep.add("PASS", "Git Bash", f"{_posix(bash)} ({how})")
        else:
            rep.add("FAIL", "Git Bash", f"{how}: {NO_GIT_BASH}")
    else:
        bash = shutil.which("bash") or "/bin/sh"

    # ---- the real hook, in a throwaway state dir
    with tempfile.TemporaryDirectory(prefix="agentic-doctor-", ignore_cleanup_errors=True) as td:
        _fake_state(Path(td))
        env = dict(os.environ, AGENTIC_STATE_DIR=td, CLAUDE_PROJECT_DIR=str(REPO))
        if hook_py:
            _check_hook_runs(rep, "pre hook", [hook_py, "-I", str(PRE_HOOK)], env)
        else:
            rep.add("FAIL", "pre hook", "not run: fix AGENTIC_PYTHON first")
        if bash:
            benv = dict(env)                       # exactly what Claude Code would run: AGENTIC_PYTHON as set
            if val:
                benv["AGENTIC_PYTHON"] = val
            else:
                benv.pop("AGENTIC_PYTHON", None)
            _check_hook_runs(rep, "hook command", [bash, "-c", HOOK_COMMANDS["PreToolUse"]], benv)

    print(f"doctor: {'all checks passed' if not rep.failed else f'{rep.failed} FAIL'}"
          + ("" if not rep.failed else " (README section 1)"))
    return 1 if rep.failed else 0


def _check_flags(rep: Report) -> None:
    """The `status` banner (ledger.flag_banner) as WARN lines: STOP (the file, or sticky in hook.log with the file
    missing), FLATTEN, BLOCK_BUYS. A set flag is not an install problem, so never a FAIL."""
    try:
        from agentic import ledger
        banner = ledger.flag_banner()
    except Exception as e:                         # noqa: BLE001
        banner = [f"!!! cannot read the flags ({type(e).__name__})"]
    for line in banner:
        rep.add("WARN", "flags", line.removeprefix("!!! "))
    if not banner:
        rep.add("PASS", "flags", "none set (no STOP, FLATTEN or BLOCK_BUYS file, no active STOP in hook.log)")


def _fav_note(cfg: dict) -> str:
    """The universe PASS lines' note: favorites skip the liquidity and max_assets cuts (README section 9)."""
    n = len((cfg.get("allocation") or {}).get("favorites") or [])
    return f" (plus any of the {n} allocation.favorites past those two cuts)" if n else ""


def check_universe(rep: Report, cfg: dict, p: dict) -> None:
    """The crypto universe (README section 10): on/off and source, the newest get_currency_pairs capture, explicit
    crypto assets that bypass a mapped ETF or keep a coin out, favorites that name both a coin and a stock universe
    ticker, and the Coinbase cache. WARN lines only."""
    u = crypto_universe(cfg)
    cmd = cli_command()
    if not u["enabled"]:
        rep.add("PASS", "universe", f"crypto universe off (explicit assets only); a config from before it has no "
                                    f"universe block: `{cmd} init --update` adds it")
    else:
        rep.add("PASS", "universe", f"crypto universe on: source {u['source']}, at most {u['max_assets']} coins with "
                                    f"median volume >= ${u['min_dollar_volume_usd']:,.0f}/day{_fav_note(cfg)}, "
                                    f"{len(u['etf_map'])} coins mapped to spot ETFs "
                                    f"({'preferred' if u['prefer_etf'] else 'not preferred'}), direct crypto "
                                    f"{'on' if u['direct_crypto'] else 'off'}")
        if (cfg.get("allocation") or {}).get("method") != "slots":
            rep.add("WARN", "universe", "allocation.method is fixed: universe coins get alloc_frac 0, so they are "
                                        "never bought, and a held one is kept until its signal turns red (or "
                                        "FLATTEN), then sold; use allocation.method slots (README section 9)")
        gone = [c for c in DEFAULT_EXCLUDE if c not in u["exclude"]]
        if gone:
            rep.add("WARN", "universe", f"universe.crypto.exclude lacks {', '.join(gone)} (stablecoins and wrapped "
                                        "tokens have no trend to follow): add them back unless that is intended")
    try:
        from agentic import universe
        pc = universe.pairs_capture(p["inbox"]) if p["inbox"].is_dir() else None
    except Exception as e:                         # noqa: BLE001 - pandas missing etc.: reported above
        pc, err = None, f"{type(e).__name__}"
    else:
        err = None
    coins = set(u["symbols"]) | set(u["etf_map"]) | set((pc or {}).get("pairs") or {})
    for a in cfg.get("assets", []):
        v = a.get("vehicle") or {}
        code = str(v.get("symbol") or "").upper().split("-")[0]
        if a.get("enabled") and v.get("type") == "crypto" and code in u["etf_map"]:
            rep.add("WARN", "crypto vehicle", f"{a['name']} trades {code} directly (about 0.95% per side) while "
                                              f"universe.crypto.etf_map has {u['etf_map'][code]}: consider "
                                              f'"vehicle": {{"type": "equity", "symbol": "{u["etf_map"][code]}", '
                                              '"fractional": true}')
        name = str(a.get("name") or "").upper()
        if u["enabled"] and COIN_CODE.match(name):                         # as universe._claims (any class)
            if a.get("class") == "crypto" and not a.get("enabled"):
                rep.add("WARN", "universe", f"the disabled explicit asset {a['name']} keeps {name} out of the "
                                            "universe: delete the entry to let the universe trade it, or enable it to "
                                            "trade it with its own settings")
            elif a.get("class") != "crypto" and name in coins:
                rep.add("WARN", "universe", f"the {a.get('class')} asset {a['name']} shares the coin code {name}: the "
                                            f"coin {name} is kept out of the universe; rename the asset (e.g. "
                                            f"{name}-STOCK) to let the universe trade the coin")
    pairs = ((pc or {}).get("pairs") or {}) if u["source"] == "robinhood" else {}
    cands = set(u["symbols"]) | {k for k, v in pairs.items() if v["tradable"]}          # the scan's candidates
    for name in sorted((favorite_names(cfg) - coin_favorites(cfg)) & cands) if u["enabled"] else []:
        rep.add("WARN", "favorites", f"allocation.favorites {name} is both a coin (Robinhood pair list or "
                                     f"universe.crypto.symbols) and a ticker in universe.equity.symbols. To the scans "
                                     f"it means the stock: the coin {name} is not kept past the crypto liquidity or "
                                     f"max_assets cut for it. In the plan it favors whichever asset is named {name}: "
                                     f"the coin when it makes those cuts on its own (the stock is then "
                                     f"{name}{STOCK_SUFFIX}), else the stock. List {name}{STOCK_SUFFIX} to favor the "
                                     "stock in every case (README section 9)")
    if u["enabled"] and u["source"] == "robinhood":
        if err:
            rep.add("WARN", "currency pairs", f"cannot read the inbox ({err})")
        elif pc is None:
            rep.add("WARN", "currency pairs", "no get_currency_pairs capture yet: /moneyline's fetch-list captures "
                                              "it; until then only universe.crypto.symbols are scanned")
        elif not pc["pairs"]:
            rep.add("WARN", "currency pairs", f"the get_currency_pairs capture {pc['empty']} has no USD pairs: only "
                                              "universe.crypto.symbols are scanned until /moneyline captures it again")
        elif pc["age_days"] > universe.PAIRS_STALE_DAYS:
            rep.add("WARN", "currency pairs", f"the newest get_currency_pairs capture is {pc['age_days']:.0f} days "
                                              "old: run /moneyline to refresh the coin list")
        else:
            rep.add("PASS", "currency pairs", f"newest get_currency_pairs capture {pc['age_days'] * 24:.0f} h old, "
                                              f"{len(pc['pairs'])} USD pairs")
    cb = p["cache"] / "coinbase"
    csvs = sorted(cb.glob("*-USD.csv")) if cb.is_dir() else []
    wants = u["enabled"] or any((a.get("signal") or {}).get("feed") == "coinbase" for a in cfg.get("assets", []))
    if csvs:
        rep.add("PASS", "coinbase cache", f"{_short(cb)}: daily candles for {len(csvs)} products")
    elif wants:
        rep.add("WARN", "coinbase cache", f"none yet ({_short(cb)}): the first `{cmd} signals` fills it (the first "
                                          "universe scan downloads about 2 years per coin, at most 5 requests a "
                                          "second)")


def yfinance_needed(cfg: dict) -> list[str]:
    """What uses the yfinance feed: enabled assets, and the stock universe when it is on with feed yfinance."""
    out = [a["name"] for a in cfg.get("assets", []) if a.get("enabled") and (a.get("signal") or {}).get("feed") ==
           "yfinance" and (a.get("signal") or {}).get("source", "computed") == "computed"]
    u = equity_universe(cfg)
    if u["enabled"] and u["feed"] == "yfinance":
        out.append("universe.equity")
    return out


def check_stocks(rep: Report, cfg: dict, p: dict) -> None:
    """The yfinance package (FAIL when the yfinance feed is used without it) and the stock universe (README section
    13): on/off, an empty symbols list, a fixed allocation, the newest tradability capture."""
    py = cli_command().split(" -m ")[0]
    need = yfinance_needed(cfg)
    if importlib.util.find_spec("yfinance") is not None:
        try:
            from importlib.metadata import version
            ver = version("yfinance")
        except Exception:                          # noqa: BLE001 - installed without metadata
            ver = "importable"
        rep.add("PASS", "yfinance", ver + (f" (used by {', '.join(need)})" if need else ""))
    elif need:
        rep.add("FAIL", "yfinance", f"not installed, but {', '.join(need)} use the yfinance feed: "
                                    f"{py} -m pip install yfinance")
    u = equity_universe(cfg)
    if not u["enabled"]:
        rep.add("PASS", "stock universe", "off (universe.equity); a config from before it has no universe.equity "
                                          f"block: `{cli_command()} init --update` adds it")
        return
    rep.add("PASS", "stock universe", f"on: {len(u['symbols'])} symbols, feed {u['feed']}, at most {u['max_assets']} "
                                      f"with median volume >= ${u['min_dollar_volume_usd']:,.0f}/day{_fav_note(cfg)} "
                                      f"and >= {u['min_history_bars']} bars")
    if not u["symbols"]:
        rep.add("WARN", "stock universe", "universe.equity.symbols is empty: paste your tickers into the private "
                                          "config (`code private/agentic/config.json`)")
    if (cfg.get("allocation") or {}).get("method") != "slots":
        rep.add("WARN", "stock universe", "allocation.method is fixed: universe stocks get alloc_frac 0, so they are "
                                          "never bought; use allocation.method slots (README section 9)")
    try:
        from agentic import universe
        tr, _ = universe.etf_tradability(p["inbox"], cfg) if p["inbox"].is_dir() else ({}, [])
    except Exception as e:                         # noqa: BLE001 - pandas missing etc.: reported above
        rep.add("WARN", "stock universe", f"cannot read the inbox ({type(e).__name__})")
        return
    missing = [t for t in u["symbols"] if t not in tr]
    if missing:
        rep.add("WARN", "tradability", f"{len(missing)} of {len(u['symbols'])} tickers have no get_equity_tradability "
                                       "capture of the last 7 days: the next /moneyline checks them first")
    else:
        rep.add("PASS", "tradability", f"every ticker checked in the last 7 days "
                                       f"({sum(1 for t in u['symbols'] if tr[t]['ok'])} tradable)")


def _check_ignored(rep: Report, config_path: Path) -> None:
    """The private config and .claude/settings.local.json must be ignored by git (the repo is public)."""
    targets = [Path(".claude") / "settings.local.json"]
    try:
        targets.insert(0, Path(config_path).resolve().relative_to(REPO))
    except (ValueError, OSError):
        pass                                       # state dir outside the repo: nothing to commit by accident
    git = shutil.which("git")
    if not git:
        rep.add("WARN", "git ignore", "git not on PATH: cannot check that private files are ignored")
        return
    for t in targets:
        try:
            r = subprocess.run([git, "-C", str(REPO), "check-ignore", "-q", t.as_posix()],
                               capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            rep.add("WARN", "git ignore", f"cannot run git ({type(e).__name__})")
            return
        if r.returncode == 0:
            rep.add("PASS", "git ignore", f"{t.as_posix()} is ignored")
        elif r.returncode == 1:
            rep.add("FAIL", "git ignore", f"{t.as_posix()} is NOT ignored by git: the repo is public; add it to "
                                          ".gitignore")
        else:
            rep.add("WARN", "git ignore", f"git check-ignore failed for {t.as_posix()} (exit {r.returncode})")
            return
