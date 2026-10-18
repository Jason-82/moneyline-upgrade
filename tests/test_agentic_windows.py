"""Windows support: the built-in US Eastern time zone (no tz database), `doctor`, the Git Bash scheduling scripts in
agentic/windows/, and the CLI's command hints. Runs on Linux; Windows is simulated where it matters."""
import importlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zoneinfo
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import calendar as cal  # noqa: E402
from agentic import cli, config, doctor, ledger  # noqa: E402

UTC = timezone.utc
ACCT, RHS = "TESTACCT9Z", "778899001"           # fake account numbers
WIN = REPO / "agentic" / "windows"
BASH = doctor.find_git_bash()[0] if os.name == "nt" else shutil.which("bash")   # never WSL's bash.exe


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    d.mkdir()
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(d))
    for k in ("AGENTIC_PYTHON", "CLAUDE_CODE_GIT_BASH_PATH"):
        monkeypatch.delenv(k, raising=False)

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return d


def _zoneinfo_et():
    try:
        return zoneinfo.ZoneInfo("America/New_York")
    except zoneinfo.ZoneInfoNotFoundError:
        pytest.skip("no tz database to compare against")


# ------------------------------------------------------------------ US Eastern without a tz database

def _key(dt):
    return dt.replace(tzinfo=None), dt.fold, dt.utcoffset(), dt.dst(), dt.tzname()


def test_fallback_matches_zoneinfo_every_hour_2024_2030():
    z, f = _zoneinfo_et(), cal.USEastern()
    t = datetime(2024, 1, 1, tzinfo=UTC)
    n = 0
    while t < datetime(2031, 1, 1, tzinfo=UTC):                    # UTC -> local (fromutc), every hour
        assert _key(t.astimezone(f)) == _key(t.astimezone(z)), t
        assert t.astimezone(f).astimezone(UTC) == t
        t += timedelta(hours=1)
        n += 1
    assert n > 61000
    for year in range(2024, 2031):                                 # local -> UTC around both transitions
        start, end = cal.USEastern.transitions(year)
        for day in (start, end):
            w = day - timedelta(hours=3)
            while w < day + timedelta(hours=3):
                for fold in (0, 1):
                    a, b = w.replace(tzinfo=z, fold=fold), w.replace(tzinfo=f, fold=fold)
                    assert (a.utcoffset(), a.dst(), a.tzname()) == (b.utcoffset(), b.dst(), b.tzname()), (w, fold)
                    assert a.astimezone(UTC) == b.astimezone(UTC), (w, fold)
                w += timedelta(minutes=15)


def test_fallback_transition_details():
    f = cal.USEastern()
    assert cal.USEastern.transitions(2026) == (datetime(2026, 3, 8, 2), datetime(2026, 11, 1, 2))
    assert cal.USEastern.transitions(2030) == (datetime(2030, 3, 10, 2), datetime(2030, 11, 3, 2))
    # spring forward: 06:59 UTC is 01:59 EST, 07:00 UTC is 03:00 EDT
    assert datetime(2026, 3, 8, 6, 59, tzinfo=UTC).astimezone(f).strftime("%H:%M %Z") == "01:59 EST"
    assert datetime(2026, 3, 8, 7, 0, tzinfo=UTC).astimezone(f).strftime("%H:%M %Z") == "03:00 EDT"
    # fall back: 01:30 happens twice, fold 0 = EDT then fold 1 = EST
    first = datetime(2026, 11, 1, 5, 30, tzinfo=UTC).astimezone(f)
    second = datetime(2026, 11, 1, 6, 30, tzinfo=UTC).astimezone(f)
    assert first.replace(tzinfo=None) == second.replace(tzinfo=None) == datetime(2026, 11, 1, 1, 30)
    assert (first.fold, first.tzname(), second.fold, second.tzname()) == (0, "EDT", 1, "EST")
    assert f.utcoffset(None) is None and repr(f) == "USEastern()"
    with pytest.raises(ValueError):
        f.fromutc(datetime(2026, 1, 1, tzinfo=UTC))


def test_calendar_and_ledger_import_without_a_tz_database(monkeypatch):
    def missing(key):
        raise zoneinfo.ZoneInfoNotFoundError(f"No time zone found with key {key}")
    monkeypatch.setattr(zoneinfo, "ZoneInfo", missing)
    try:
        importlib.reload(cal)
        importlib.reload(ledger)
        assert cal.ET_SOURCE == "fallback" and isinstance(cal.ET, cal.USEastern) and ledger.ET is cal.ET
        # 2026-11-02 is a Monday after the fall-back: 16:00 EST = 21:00 UTC; in October it is 20:00 UTC
        assert cal.bar_close("equity", date(2026, 11, 2)) == datetime(2026, 11, 2, 21, 0, tzinfo=UTC)
        assert cal.bar_close("equity", date(2026, 10, 16)) == datetime(2026, 10, 16, 20, 0, tzinfo=UTC)
        assert cal.et_date(datetime(2026, 10, 17, 3, 59, tzinfo=UTC)) == date(2026, 10, 16)
        assert cal.et_date(datetime(2026, 10, 17, 4, 0, tzinfo=UTC)) == date(2026, 10, 17)
        assert cal.market_open(datetime(2026, 10, 19, 13, 30, tzinfo=UTC))
        assert not cal.market_open(datetime(2026, 12, 21, 14, 29, tzinfo=UTC))     # 09:29 EST
        assert cal.valid_until("equity", datetime(2026, 12, 21, 15, 0, tzinfo=UTC)) == \
            datetime(2026, 12, 21, 20, 45, tzinfo=UTC)
        assert ledger.day_key(datetime(2026, 10, 17, 3, 0, tzinfo=UTC)) == "2026-10-16"
    finally:
        monkeypatch.undo()
        importlib.reload(cal)
        importlib.reload(ledger)
    assert cal.ET_SOURCE == "zoneinfo" or importlib.util.find_spec("tzdata") is None


def test_hooks_and_cli_modules_load_without_a_tz_database(tmp_path, state):
    """A real interpreter with no tz database (as on Windows without the tzdata package): the hook guard still
    imports calendar/ledger and blocks or allows as usual."""
    if importlib.util.find_spec("tzdata") is not None:
        pytest.skip("the tzdata package is installed: zoneinfo cannot be made to fail this way")
    env = dict(os.environ, PYTHONTZPATH=str(tmp_path / "no-tz-database"), AGENTIC_STATE_DIR=str(state))
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import zoneinfo\n"
            "try:\n zoneinfo.ZoneInfo('America/New_York'); print('tz database found')\n"
            "except zoneinfo.ZoneInfoNotFoundError: pass\n"
            "from agentic import calendar, ledger, hooks, cli\n"
            "print(calendar.ET_SOURCE, ledger.day_key(calendar.as_utc(None)) is not None)")
    r = subprocess.run([sys.executable, "-I", "-c", code, str(REPO)], env=env, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.decode().split() == ["fallback", "True"]
    with tempfile.TemporaryDirectory() as td:
        doctor._fake_state(Path(td))
        env["AGENTIC_STATE_DIR"] = td
        for event, want in ((doctor.READ_EVENT, 0), (doctor.PLACE_EVENT, 2)):
            r = subprocess.run([sys.executable, "-I", str(doctor.PRE_HOOK)], input=event, env=env,
                               capture_output=True, timeout=60)
            assert r.returncode == want, r.stderr
        assert b"no plan order matches" in r.stderr


# ------------------------------------------------------------------ doctor

def _settings_dir(tmp_path, local=None, shared=None):
    d = tmp_path / "claude"
    d.mkdir(exist_ok=True)
    s = shared if shared is not None else json.loads((REPO / ".claude" / "settings.json").read_text())
    (d / "settings.json").write_text(json.dumps(s))
    if local is not None:
        (d / "settings.local.json").write_text(json.dumps(local))
    return d


def _config(state, **acct):
    raw = json.loads(config.EXAMPLE.read_text(encoding="utf-8"))
    raw["account"] = dict(raw.get("account") or {}, **acct)
    (state / "config.json").write_text(json.dumps(raw))


def _rows(out):
    return [ln for ln in out.splitlines() if ln[:4] in ("PASS", "WARN", "FAIL")]


def test_doctor_passes_on_a_good_install(state, tmp_path, capsys):
    _config(state, account_number=ACCT, rhs_account_number=RHS)
    d = _settings_dir(tmp_path, local={"env": {"AGENTIC_PYTHON": sys.executable}})
    assert doctor.run(settings_dir=d) == 0
    out = capsys.readouterr().out
    rows = _rows(out)
    assert not [r for r in rows if r.startswith("FAIL")], out
    for name in ("python", "interpreter", "AGENTIC_PYTHON", "pandas", "numpy", "time zone", "state dir", "config",
                 "accounts", "hooks", "pre hook", "hook command"):
        assert any(r[6:].startswith(name) for r in rows), name
    assert "settings.local.json" in out and "all checks passed" in out
    assert sum(1 for r in rows if "blocked (exit 2)" in r) == 2 and sum(1 for r in rows if "(exit 0)" in r) == 2
    assert ACCT not in out and RHS not in out and doctor.FAKE_ACCT not in out
    assert not (state / "hook.log").exists()                # the hook ran in a throwaway state dir


def test_doctor_reports_failures(state, tmp_path, capsys):
    bad = json.loads((REPO / ".claude" / "settings.json").read_text())
    bad["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = 'python3 "$CLAUDE_PROJECT_DIR/agentic/hooks/pre_tool_use.py"'
    del bad["hooks"]["PostToolUseFailure"]
    d = _settings_dir(tmp_path, shared=bad, local={"env": {"AGENTIC_PYTHON": "~/.venv/Scripts/python.exe"},
                                                   "disableAllHooks": True})
    assert doctor.run(settings_dir=d) == 1
    out = capsys.readouterr().out
    fails = [r for r in _rows(out) if r.startswith("FAIL")]
    text = "\n".join(fails)
    assert "copied literally" in text                      # ~ is not expanded in settings env
    assert "no config at" in text
    assert "PreToolUse does not run" in text and "PostToolUseFailure does not run" in text
    assert "disableAllHooks" in text and "fix AGENTIC_PYTHON first" in text
    assert "PostToolUse does not run" not in text.replace("PostToolUseFailure", "")


def test_doctor_missing_interpreter_and_unfilled_accounts(state, tmp_path, capsys):
    _config(state, account_number="FILL-IN", rhs_account_number="FILL-IN")
    d = _settings_dir(tmp_path, local={"env": {"AGENTIC_PYTHON": str(tmp_path / "nope" / "python.exe")}})
    assert doctor.run(settings_dir=d) == 1
    fails = "\n".join(r for r in _rows(capsys.readouterr().out) if r.startswith("FAIL"))
    assert "does not exist" in fails and "account.account_number not filled in" in fails
    assert "hook command" in fails                         # the real command cannot start that interpreter


def test_doctor_on_windows_without_git_bash_or_agentic_python(state, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "windows", lambda: True)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)       # no git.exe on PATH either
    monkeypatch.setattr(doctor, "GIT_BASH_PATHS", (str(tmp_path / "Git" / "bin" / "bash.exe"),))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    _config(state, account_number=ACCT, rhs_account_number=RHS)
    assert doctor.run(settings_dir=_settings_dir(tmp_path)) == 1
    fails = "\n".join(r for r in _rows(capsys.readouterr().out) if r.startswith("FAIL"))
    assert "Microsoft Store" in fails and "README section 1" in fails
    assert "Git Bash" in fails and "PowerShell" in fails


def test_doctor_on_windows_with_git_bash(state, tmp_path, monkeypatch, capsys):
    if BASH is None:
        pytest.skip("no bash")
    monkeypatch.setattr(doctor, "windows", lambda: True)
    monkeypatch.setenv("CLAUDE_CODE_GIT_BASH_PATH", BASH)
    _config(state, account_number=ACCT, rhs_account_number=RHS)
    venv_py = sys.executable
    d = _settings_dir(tmp_path, local={"env": {"AGENTIC_PYTHON": venv_py}})
    assert doctor.run(settings_dir=d) == 0, capsys.readouterr().out
    rows = _rows(capsys.readouterr().out)
    assert any(r.startswith("PASS  Git Bash") and "CLAUDE_CODE_GIT_BASH_PATH" in r for r in rows)
    assert sum(1 for r in rows if r.startswith("PASS  hook command")) == 2


def test_find_git_bash(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_GIT_BASH_PATH", str(tmp_path / "missing.exe"))
    path, how = doctor.find_git_bash()
    assert path is None and "missing" in how
    monkeypatch.delenv("CLAUDE_CODE_GIT_BASH_PATH")
    git = tmp_path / "Git" / "cmd" / "git.exe"
    git.parent.mkdir(parents=True)
    git.write_text("")
    (tmp_path / "Git" / "bin").mkdir()
    (tmp_path / "Git" / "bin" / "bash.exe").write_text("")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: str(git) if name == "git" else None)
    monkeypatch.setattr(doctor, "GIT_BASH_PATHS", ())
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert doctor.find_git_bash()[0] == (tmp_path / "Git" / "bin" / "bash.exe").as_posix()
    sys32 = tmp_path / "Windows" / "System32"                       # WSL's bash.exe is never Git Bash
    sys32.mkdir(parents=True)
    (sys32 / "bin").mkdir()
    (sys32 / "bin" / "bash.exe").write_text("")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: str(sys32 / "git.exe") if name == "git" else None)
    assert doctor.find_git_bash()[0] is None


def test_configured_python_precedence(monkeypatch):
    monkeypatch.setenv("AGENTIC_PYTHON", "/env/python")
    local, shared = {"env": {"AGENTIC_PYTHON": "C:/local/python.exe"}}, {"env": {"AGENTIC_PYTHON": "C:/s/python.exe"}}
    assert doctor.configured_python(local, shared) == ("C:/local/python.exe", ".claude/settings.local.json")
    assert doctor.configured_python(None, shared) == ("C:/s/python.exe", ".claude/settings.json")
    assert doctor.configured_python({}, {"hooks": {}}) == ("/env/python", "the environment")
    monkeypatch.delenv("AGENTIC_PYTHON")
    assert doctor.configured_python(None, None) == (None, "")
    monkeypatch.setattr(doctor, "windows", lambda: True)
    assert doctor._as_local_path("/c/Users/me/python.exe").as_posix() == "C:/Users/me/python.exe"


def test_doctor_constants_match_settings_json():
    s = json.loads((REPO / ".claude" / "settings.json").read_text())
    for event, cmd in doctor.HOOK_COMMANDS.items():
        assert s["hooks"][event][0]["hooks"][0]["command"] == cmd


def test_cli_doctor_command(monkeypatch):
    seen = []
    monkeypatch.setattr(doctor, "run", lambda: seen.append(1) or 0)
    assert cli.main(["doctor"]) == 0 and seen == [1]


# ------------------------------------------------------------------ CLI hints and output

def test_cli_command_names_the_repo_venv(monkeypatch):
    monkeypatch.setattr(sys, "executable", str(REPO / ".venv" / "Scripts" / "python.exe"))
    assert config.cli_command() == ".venv/Scripts/python.exe -m agentic"
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3.11")
    if os.name != "nt":
        assert config.cli_command() == "python3 -m agentic"


def test_cli_hints_use_the_running_interpreter(state, monkeypatch, capsys):
    monkeypatch.setattr(sys, "executable", str(REPO / ".venv" / "Scripts" / "python.exe"))
    assert cli.main(["init"]) == 0
    out = capsys.readouterr().out
    assert ".venv/Scripts/python.exe -m agentic doctor" in out and "python3" not in out
    assert cli.main(["status"]) == 0
    assert "`.venv/Scripts/python.exe -m agentic signals`" in capsys.readouterr().out


def test_utf8_output_on_windows(monkeypatch):
    import io

    class Stream(io.TextIOWrapper):
        pass
    out = Stream(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(cli, "os", type("FakeOs", (), {"name": "nt"}))      # not os.name itself: pathlib needs it
    cli._utf8_output()
    print("\u2192 \u00d7", file=out)
    out.flush()
    assert out.buffer.getvalue().decode("utf-8").strip() == "\u2192 \u00d7"


# ------------------------------------------------------------------ agentic/windows scripts

def _run(script, *args, env=None, cwd=None):
    return subprocess.run([BASH, str(WIN / script), *args], env=env, cwd=cwd, capture_output=True, text=True,
                          timeout=60)


@pytest.fixture
def fake_cygpath(tmp_path):
    """A cygpath stand-in: -w maps /x/y to C:\\fake\\x\\y; -m / is a fake Git root that has bin/bash.exe."""
    root = tmp_path / "Program Files" / "Git"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "bash.exe").write_text("")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "cygpath").write_text(
        "#!/usr/bin/env bash\n"
        'case "$1" in\n'
        f'  -m) [ "$2" = / ] && echo "{root.as_posix()}/" || echo "$2" ;;\n'
        '  -w) p="${2#/}"; printf \'C:\\\\fake\\\\%s\\n\' "${p//\\//\\\\}" ;;\n'
        "esac\n")
    (bindir / "cygpath").chmod(0o755)
    return bindir, root


@pytest.mark.skipif(BASH is None or os.name == "nt", reason="needs bash; uses a fake cygpath")
def test_schedule_install_dry_run_builds_the_schtasks_command(fake_cygpath):
    bindir, root = fake_cygpath
    env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
    r = _run("schedule_crypto_signals.sh", "install", "--dry-run", env=env)
    assert r.returncode == 0, r.stderr
    argv = shlex.split(r.stdout)
    win = lambda p: "C:\\fake\\" + str(p).lstrip("/").replace("/", "\\")          # noqa: E731
    assert argv[:11] == ["MSYS_NO_PATHCONV=1", "schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", "20:15", "/TN",
                         "moneyline-crypto-signals", "/TR"]
    assert argv[11] == f'"{win(root / "bin" / "bash.exe")}" -l "{win(WIN / "crypto_signals.sh")}"'
    assert len(argv) == 12


@pytest.mark.skipif(BASH is None or os.name == "nt", reason="needs bash without cygpath")
def test_schedule_without_cygpath_uses_the_configured_bash(tmp_path):
    env = dict(os.environ, CLAUDE_CODE_GIT_BASH_PATH="C:\\Program Files\\Git\\bin\\bash.exe")
    r = _run("schedule_crypto_signals.sh", "install", "--time", "21:05", "--name", "ml-test", "--dry-run", env=env)
    assert r.returncode == 0, r.stderr
    argv = shlex.split(r.stdout)
    assert argv[7] == "21:05" and argv[9] == "ml-test"
    assert argv[11] == f'"C:\\Program Files\\Git\\bin\\bash.exe" -l "{(WIN / "crypto_signals.sh").as_posix()}"'
    r = _run("schedule_crypto_signals.sh", "status", "--dry-run")
    assert shlex.split(r.stdout) == ["MSYS_NO_PATHCONV=1", "schtasks", "/Query", "/TN", "moneyline-crypto-signals",
                                     "/V", "/FO", "LIST"]
    r = _run("schedule_crypto_signals.sh", "remove", "--dry-run")
    assert shlex.split(r.stdout) == ["MSYS_NO_PATHCONV=1", "schtasks", "/Delete", "/TN", "moneyline-crypto-signals",
                                     "/F"]
    for bad in (["install", "--time", "24:00"], ["install", "--time", "8:15"], ["install", "--name", "a b"],
                ["bogus"], [], ["install", "--wat"]):
        r = _run("schedule_crypto_signals.sh", *bad, "--dry-run") if bad else _run("schedule_crypto_signals.sh")
        assert r.returncode == 2 and r.stderr, bad


@pytest.mark.skipif(BASH is None, reason="needs bash")
def test_schedule_refuses_without_schtasks(tmp_path):
    env = dict(os.environ, PATH=os.path.dirname(BASH) + os.pathsep + "/usr/bin" + os.pathsep + "/bin")
    if shutil.which("schtasks", path=env["PATH"]):
        pytest.skip("schtasks exists here")
    r = _run("schedule_crypto_signals.sh", "remove", env=env)
    assert r.returncode == 2 and "schtasks not found" in r.stderr


@pytest.mark.skipif(BASH is None or os.name == "nt", reason="needs bash; MSYS prints /c/... paths")
def test_crypto_signals_job_runs_from_the_repo_root_and_logs(tmp_path, state):
    fake = tmp_path / "fakepy"
    fake.write_text('#!/usr/bin/env bash\necho "cwd=$PWD args=$*"\nexit "${FAKE_RC:-0}"\n')
    fake.chmod(0o755)
    env = dict(os.environ, AGENTIC_PYTHON=str(fake), AGENTIC_STATE_DIR=str(state))
    r = _run("crypto_signals.sh", env=env, cwd=tmp_path)                 # any working directory
    assert r.returncode == 0 and r.stderr == ""
    r = _run("crypto_signals.sh", env=dict(env, FAKE_RC="1"), cwd=tmp_path)
    assert r.returncode == 1 and "moneyline signals failed (exit 1)" in r.stderr
    log = (state / "cron.log").read_text().splitlines()
    assert log[0].startswith("=== ") and log[0].endswith("signals --class crypto")
    assert log[1] == f"cwd={REPO} args=-m agentic signals --class crypto"
    assert log[2] == "=== exit 0" and log[-1] == "=== exit 1" and len(log) == 6


@pytest.mark.skipif(BASH is None, reason="needs bash")
def test_crypto_signals_job_needs_an_interpreter(tmp_path, state):
    repo = tmp_path / "repo"
    (repo / "agentic" / "windows").mkdir(parents=True)
    shutil.copy(WIN / "crypto_signals.sh", repo / "agentic" / "windows")
    r = subprocess.run([BASH, str(repo / "agentic" / "windows" / "crypto_signals.sh")], capture_output=True,
                       text=True, timeout=60, env=dict(os.environ, AGENTIC_STATE_DIR=str(state)))
    assert r.returncode == 2 and "no .venv" in r.stderr


def test_windows_scripts_are_git_bash_and_never_powershell():
    for f in WIN.glob("*.sh"):
        text = f.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash\n"), f
        assert "\r" not in text, f                                   # LF endings: bash rejects CRLF
        assert "powershell" not in text.lower() and "cmd /c" not in text.lower(), f
    sched = (WIN / "schedule_crypto_signals.sh").read_text(encoding="utf-8")
    assert "MSYS_NO_PATHCONV=1 schtasks" in sched


def test_gitignore_keeps_local_settings_and_venv_out():
    lines = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".claude/settings.local.json" in lines and ".venv/" in lines and "private/" in lines
    attrs = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "*.sh text eol=lf" in attrs                  # a Windows checkout (core.autocrlf) must not add CR


def test_slash_command_runs_the_configured_interpreter():
    text = (REPO / ".claude" / "commands" / "moneyline.md").read_text(encoding="utf-8")
    form = '"${AGENTIC_PYTHON:-python3}" -m agentic'
    assert text.count(form) >= 8 and "python3 -m agentic" not in text.replace(form, "")
    assert "agentic doctor" in text and "README.md` section 1" in text
    for word in ("powershell -", "cmd /c", ".\\"):
        assert word not in text.lower()


# ------------------------------------------------------------------ doctor: the CLI interpreter, BOMs; docs

def _venv(path, see_our_packages=False):
    """A new venv without pip. With see_our_packages, a .pth file adds this interpreter's site dirs, so it imports
    pandas from a different interpreter path (a system-site-packages venv would not when tests run in a venv)."""
    import venv
    venv.create(path, with_pip=False, symlinks=os.name != "nt")
    py = path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if see_our_packages:
        site = subprocess.run([str(py), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                              capture_output=True, text=True, check=True, timeout=60).stdout.strip()
        import numpy
        import pandas
        dirs = {p for p in sys.path if p.endswith(("site-packages", "dist-packages")) and os.path.isdir(p)}
        dirs |= {str(Path(m.__file__).resolve().parent.parent) for m in (pandas, numpy)}
        Path(site, "outer.pth").write_text("\n".join(sorted(dirs)) + "\n", encoding="utf-8")
    return py


def test_doctor_fails_when_agentic_python_cannot_import_pandas(state, tmp_path, capsys):
    """Regression: with AGENTIC_PYTHON set to a venv without pandas, every doctor line passed (the hooks need only
    the standard library), but /moneyline runs every CLI command with that interpreter and failed with
    ModuleNotFoundError."""
    pytest.importorskip("pandas")
    _config(state, account_number=ACCT, rhs_account_number=RHS)
    bare = _venv(tmp_path / "bare venv")
    d = _settings_dir(tmp_path, local={"env": {"AGENTIC_PYTHON": bare.as_posix()}})
    assert doctor.run(settings_dir=d) == 1
    out = capsys.readouterr().out
    fails = [r for r in _rows(out) if r.startswith("FAIL")]
    assert len(fails) == 1 and fails[0].startswith("FAIL  CLI python"), out
    assert bare.as_posix() in fails[0] and "cannot import pandas" in fails[0]
    assert f'"{bare.as_posix()}" -m pip install pandas numpy tzdata' in fails[0]        # quoted: the path has a space
    assert sum(1 for r in _rows(out) if "blocked (exit 2)" in r) == 2                  # the hooks themselves work
    good = _venv(tmp_path / "good", see_our_packages=True)                         # another path, with pandas
    d = _settings_dir(tmp_path, local={"env": {"AGENTIC_PYTHON": good.as_posix()}})
    assert doctor.run(settings_dir=d) == 0, capsys.readouterr().out
    rows = _rows(capsys.readouterr().out)
    assert any(r.startswith("PASS  CLI python") and "pandas" in r and "numpy" in r for r in rows)


def test_doctor_cli_python_check_names_the_problem(tmp_path, monkeypatch):
    rep = doctor.Report()
    doctor._check_cli_python(rep, str(tmp_path / "missing" / "python.exe"))
    assert rep.rows[-1][0] == "FAIL" and "cannot run" in rep.rows[-1][2]
    monkeypatch.setattr(doctor, "windows", lambda: True)
    doctor._check_cli_python(rep, sys.executable)
    assert rep.rows[-1][0] == "PASS" and "pandas" in rep.rows[-1][2]
    if os.name == "nt":
        return
    old = tmp_path / "old_python"
    old.write_text("#!/bin/sh\necho '{\"v\": [3, 9, 1], \"pandas\": \"2.0\", \"numpy\": \"1.0\"}'\n")
    stub = tmp_path / "stub_python"                    # like the Microsoft Store stub: no Python, no JSON
    stub.write_text("#!/bin/sh\necho 'Python was not found' >&2\nexit 9\n")
    for f in (old, stub):
        f.chmod(0o755)
    doctor._check_cli_python(rep, str(old))
    status, _, detail = rep.rows[-1]
    assert status == "FAIL" and "Python 3.9.1: the CLI needs 3.11" in detail
    assert ".venv/Scripts/python.exe" in detail and "pip install" not in detail
    doctor._check_cli_python(rep, str(stub))
    status, _, detail = rep.rows[-1]
    assert status == "FAIL" and "exit 9" in detail and "Python was not found" in detail


def test_doctor_reads_past_a_bom_in_config_and_flags_it_in_settings(state, tmp_path, capsys):
    """A config.json saved as "UTF-8 with BOM" is valid now. A settings file with a BOM still FAILs, with a clear
    message (Claude Code is not known to accept it), but its AGENTIC_PYTHON is read so the other checks run."""
    _config(state, account_number=ACCT, rhs_account_number=RHS)
    cfg = state / "config.json"
    cfg.write_bytes(b"\xef\xbb\xbf" + cfg.read_bytes())
    d = _settings_dir(tmp_path)
    (d / "settings.local.json").write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"env": {"AGENTIC_PYTHON": sys.executable}}).encode())
    assert doctor.run(settings_dir=d) == 1
    out = capsys.readouterr().out
    fails = [r for r in _rows(out) if r.startswith("FAIL")]
    assert len(fails) == 1 and "settings.local.json starts with a UTF-8 byte order mark" in fails[0], out
    assert any(r.startswith("PASS  config") for r in _rows(out))
    assert any(r.startswith("PASS  AGENTIC_PYTHON") and "settings.local.json" in r for r in _rows(out))


@pytest.mark.skipif(BASH is None, reason="no bash")
def test_readme_settings_local_one_liner_never_overwrites(tmp_path):
    """Regression: README section 1's one-liner replaced an existing .claude/settings.local.json, where Claude Code
    keeps the user's saved permission approvals. It must create the file once and refuse to overwrite it."""
    text = (REPO / "agentic" / "README.md").read_text(encoding="utf-8")
    (line,) = [ln.strip() for ln in text.splitlines() if "> .claude/settings.local.json" in ln]
    assert "set -C" in line and "pwd -W" in line and "\\" not in line.replace("\\n", "")
    (tmp_path / ".claude").mkdir()
    script = "pwd() { echo C:/Users/First Last/moneyline-upgrade; }\n" + line + "\n"   # Git Bash's pwd -W output

    def run():
        return subprocess.run([BASH, "-c", script], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    r = run()
    f = tmp_path / ".claude" / "settings.local.json"
    assert r.returncode == 0, r.stderr
    assert json.loads(f.read_text()) == {
        "env": {"AGENTIC_PYTHON": "C:/Users/First Last/moneyline-upgrade/.venv/Scripts/python.exe"}}
    saved = '{"permissions": {"allow": ["Bash(git status:*)"]}}\n'
    f.write_text(saved)
    r = run()
    assert r.returncode != 0 and "cannot overwrite existing file" in r.stderr
    assert f.read_text() == saved


def test_spec_matches_settings_json_and_git_bash():
    """SPEC section 11 shows the exact hook commands and Bash deny rules of .claude/settings.json; section 12 and the
    test command never use `python3 -m` (on Windows that is often the Microsoft Store stub)."""
    spec = (REPO / "agentic" / "SPEC.md").read_text(encoding="utf-8")
    s = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    sec11 = spec.split("## 11.", 1)[1].split("\n## 12.", 1)[0]
    pre = s["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert json.dumps(pre) in sec11
    post = s["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    assert post == s["hooks"]["PostToolUseFailure"][0]["hooks"][0]["command"]
    assert f"`{post}`" in sec11.replace("\n  ", " ")
    for rule in (d for d in s["permissions"]["deny"] if not d.startswith("mcp__")):
        assert f"`{rule}`" in sec11, rule
    for old in ("python3 -m agentic", "python3 -m pytest", "python3 -I", "agentic resume:*", "run --replan"):
        assert old not in spec, old
