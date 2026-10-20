"""Sticky STOP: the kill switch is the STOP file OR an unresolved STOP record in the append-only hook.log, so deleting
the file (by hand, a sync tool or an agent's shell command) no longer re-enables trading. Only `resume`, in the
user's own terminal, clears it, by appending a CLEAR record. The real PreToolUse / PostToolUse hooks run as
subprocesses; `resume` runs in process with a simulated terminal. Synthetic data only; state under tmp_path; no
network."""
import builtins
import io
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import cli, doctor, hooks, ledger, planner  # noqa: E402
from agentic.config import paths  # noqa: E402
from tests import test_agentic_hooks as th  # noqa: E402

UTC = timezone.utc
STICKY = "STOP is active per hook.log"
MISSING = "although the STOP file is missing; only resume in your own terminal clears it"
BYPASS = "an agent order went live without approval"


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    d = tmp_path / "state"
    d.mkdir()
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(d))

    def no_network(*a, **k):
        raise AssertionError("network access in a test")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return d


class Tty(io.StringIO):
    def isatty(self):
        return True


def resume(monkeypatch, typed="resume\n", *argv):
    monkeypatch.setattr(sys, "stdin", Tty(typed))
    return cli.main(["resume", *argv])


def log_lines(state):
    f = state / "hook.log"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def rec(ts, decision, hook="post", tool="mcp__robinhood-trading__place_equity_order", reason="r", **extra):
    return json.dumps({"ts": ts, "hook": hook, "tool": tool, "decision": decision, "reason": reason, "ref_id": None,
                       **extra})


def clear(ts, flags=("STOP",), reason=None):
    return rec(ts, "CLEAR", hook="cli", tool="resume", flags=list(flags),
               reason=reason or "cleared " + "; ".join(f"{n} (was: x)" for n in flags))


def write_log(state, *lines):
    (state / "hook.log").write_text("".join(x + "\n" for x in lines))


def iso(dt):
    return hooks.iso_z(dt)


def sell_plan(state):
    """A fresh plan order (its own ref_id) the guard allows once nothing else stands in the way."""
    sell = th.params(side="sell", ref_id=th.SELL_REF)
    th.write_plan(state, orders=[th.plan_order(sell, key="ETH|ETHA|sell|0")])
    return sell


def place(state, ti):
    return th.run(th.PRE, state, th.ev("place_equity_order", ti))


# ------------------------------------------------------------------ the hooks, end to end

def test_post_hook_stop_survives_deleting_the_file_until_resume(state, monkeypatch, capsys):
    th.ready(state, approvals=True)
    r = th.run(th.POST, state, th.ev("place_equity_order", th.params(), th.place_resp(order_id="ord-1")))
    assert r.returncode == 0 and b"AGENTIC STOP" in r.stderr
    stops = [e for e in log_lines(state) if e["decision"] == "STOP"]
    assert len(stops) == 1 and stops[0]["hook"] == "post" and "went live without approval" in stops[0]["reason"]
    (state / "STOP").unlink()                                          # by hand, a sync tool, an agent's `rm`
    sell = sell_plan(state)
    r = place(state, sell)
    err = r.stderr.decode()
    assert r.returncode == 2 and STICKY in err and MISSING in err and "cancels are still allowed" in err
    assert f"(written {hooks.scrub(stops[0]['ts'])}: an agent order went live without approval" in err
    assert log_lines(state)[-1]["decision"] == "block" and STICKY in log_lines(state)[-1]["reason"]
    # cancels still work under the sticky STOP (the kill switch must be able to pull orders)
    cancel = th.ev("cancel_equity_order", {"account_number": th.ACCT, "order_id": "ord-1"})
    assert th.run(th.PRE, state, cancel).returncode == 0
    # reads and previews too
    assert th.run(th.PRE, state, th.ev("get_equity_orders", {"account_number": th.ACCT})).returncode == 0
    assert th.run(th.PRE, state, th.ev("review_equity_order", sell)).returncode == 0
    # the flags, the status banner and the digest banner say so plainly
    fl = ledger.read_flags()
    assert set(fl) == {"STOP"} and fl["STOP"].startswith(STICKY) and ledger.read_flags(log=False) == {}
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(f"!!! {STICKY} (written ") and MISSING in lines[0]
    assert "The hook blocks every place call (cancels still work)" in lines[0]
    assert lines[1].startswith("!!! APPROVAL BYPASS")                  # the reason is still the bypass
    # Claude's shell has no terminal: resume refuses and nothing changes
    monkeypatch.setattr(sys, "stdin", io.StringIO("resume\n"))
    assert cli.main(["resume"]) == 2 and place(state, sell).returncode == 2
    # the user's terminal: resume offers STOP although the file is missing, and writes its CLEAR record
    capsys.readouterr()
    assert resume(monkeypatch) == 0
    out = capsys.readouterr().out
    assert f"STOP: {STICKY}" in out and "The STOP file is missing, but hook.log keeps STOP active" in out
    assert "cleared STOP" in out
    c = log_lines(state)[-1]
    assert (c["hook"], c["tool"], c["decision"], c["flags"]) == ("cli", "resume", "CLEAR", ["STOP"])
    assert c["reason"].startswith("cleared STOP (was: STOP is active per hook.log")
    assert hooks.sticky_stop(state / "hook.log") is None and ledger.read_flags() == {}
    r = place(state, sell)
    assert r.returncode == 0, r.stderr.decode()                       # trading is allowed again
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "!!!" not in out and "flags: none" in out and "last flag clear: " in out


def test_cli_stop_is_sticky(state, monkeypatch, capsys):
    th.ready(state)
    sell = sell_plan(state)
    assert place(state, sell).returncode == 0
    capsys.readouterr()
    assert cli.main(["stop", "manual", "kill"]) == 0
    assert "deleting the STOP file does not undo it" in capsys.readouterr().out
    s = [e for e in log_lines(state) if e["hook"] == "cli"]
    assert len(s) == 1 and (s[0]["tool"], s[0]["decision"], s[0]["reason"], s[0]["ref_id"]) == \
        ("stop", "STOP", "manual kill", None)
    assert "manual kill" in (state / "STOP").read_text()
    r = place(state, sell)
    assert r.returncode == 2 and b"STOP file present" in r.stderr
    (state / "STOP").unlink()
    r = place(state, sell)
    assert r.returncode == 2 and STICKY.encode() in r.stderr and b"manual kill" in r.stderr
    # a planner run sees it too: no orders at all
    assert "STOP" in planner._flags(None)
    assert resume(monkeypatch) == 0 and place(state, sell).returncode == 0
    # flatten records itself; it stays file-based (deleting FLATTEN lifts it, as before)
    assert cli.main(["flatten", "out"]) == 0
    f = log_lines(state)[-1]
    assert (f["hook"], f["tool"], f["decision"], f["reason"]) == ("cli", "flatten", "FLATTEN", "out")
    assert hooks.sticky_stop(state / "hook.log") is None and set(ledger.read_flags()) == {"FLATTEN"}


def test_a_new_stop_after_a_clear_blocks_again(state, monkeypatch):
    th.ready(state)
    sell = sell_plan(state)
    assert cli.main(["stop", "first"]) == 0
    assert resume(monkeypatch) == 0 and place(state, sell).returncode == 0
    # the PostToolUse hook stops again (a tool outside the allowlist ran); then the file goes away
    r = th.run(th.POST, state, th.ev("place_option_order", {"account_number": th.ACCT}, {"data": {}}))
    assert b"AGENTIC STOP" in r.stderr
    (state / "STOP").unlink()
    r = place(state, sell)
    assert r.returncode == 2 and STICKY.encode() in r.stderr and b"outside the allowlist" in r.stderr
    assert resume(monkeypatch) == 0 and place(state, sell).returncode == 0


def test_resume_of_another_flag_does_not_clear_a_sticky_stop(state, monkeypatch):
    th.ready(state)
    assert cli.main(["stop"]) == 0 and cli.main(["flatten"]) == 0
    (state / "STOP").unlink()
    assert set(ledger.read_flags()) == {"STOP", "FLATTEN"}
    assert resume(monkeypatch, "resume\n", "--flag", "FLATTEN") == 0
    assert log_lines(state)[-1]["flags"] == ["FLATTEN"]
    assert set(ledger.read_flags()) == {"STOP"}
    assert place(state, sell_plan(state)).returncode == 2
    assert resume(monkeypatch, "resume\n", "--flag", "STOP") == 0 and ledger.read_flags() == {}


def test_post_hook_logs_stop_even_when_the_stop_file_cannot_be_written(state):
    th.ready(state, approvals=True)
    (state / "STOP").mkdir()                                           # unwritable as a file
    r = th.run(th.POST, state, th.ev("place_equity_order", th.params(), th.place_resp()))
    assert b"could NOT be written" in r.stderr
    assert [e["decision"] for e in log_lines(state)].count("STOP") == 1
    (state / "STOP").rmdir()
    assert place(state, sell_plan(state)).returncode == 2


def test_cli_stop_when_the_file_or_the_record_cannot_be_written(state, monkeypatch, capsys):
    th.ready(state)
    real = ledger.set_flag

    def no_file(name, reason="", base=None):
        raise PermissionError(13, "denied")
    monkeypatch.setattr(ledger, "set_flag", no_file)
    capsys.readouterr()
    assert cli.main(["stop", "x"]) == 1                                # the record alone still holds STOP
    assert "hook.log records the STOP" in capsys.readouterr().err
    assert not (state / "STOP").exists() and place(state, sell_plan(state)).returncode == 2
    monkeypatch.setattr(ledger, "set_flag", real)
    assert resume(monkeypatch) == 0
    (state / "hook.log").rename(state / "hook.old")
    (state / "hook.log").mkdir()                                       # the record cannot be written
    capsys.readouterr()
    assert cli.main(["stop", "y"]) == 1
    assert "STOP is held by the STOP file alone" in capsys.readouterr().err and (state / "STOP").exists()


# ------------------------------------------------------------------ failing closed

def test_unreadable_hook_log_fails_closed(state, capsys):
    th.ready(state)
    th.write_plan(state, orders=[th.plan_order(th.params(side="sell", ref_id=th.SELL_REF), key="ETH|ETHA|sell|0")],
                  cancels=[{"tool": "cancel_equity_order", "params": {"account_number": th.ACCT, "order_id": "o-1"}}])
    (state / "hook.log").mkdir()                                       # exists, cannot be read as a file
    s = hooks.sticky_stop(state / "hook.log")
    assert s["why"] == "unreadable" and "cannot be read" in s["reason"]
    r = place(state, th.params(side="sell", ref_id=th.SELL_REF))
    err = r.stderr.decode()
    assert r.returncode == 2 and "STOP is treated as active" in err and "fail closed" in err
    cancel = th.ev("cancel_equity_order", {"account_number": th.ACCT, "order_id": "o-1"})
    assert th.run(th.PRE, state, cancel).returncode == 0                # cancels still work
    assert cli.main(["status"]) == 0
    assert capsys.readouterr().out.startswith("!!! STOP is treated as active: hook.log cannot be read")


def test_unreadable_hook_log_other_errors(state, monkeypatch):
    write_log(state, rec("2026-10-19T14:00:00Z", "allow"))
    real = builtins.open

    def broken(f, *a, **k):
        if str(f).endswith("hook.log"):
            raise PermissionError(13, "locked")
        return real(f, *a, **k)
    monkeypatch.setattr(builtins, "open", broken)
    assert hooks.sticky_stop(state / "hook.log")["why"] == "unreadable"
    monkeypatch.setattr(builtins, "open", real)
    assert hooks.sticky_stop(state / "hook.log") is None
    assert hooks.sticky_stop(state / "missing.log") is None             # no hook.log: the file check alone


def test_stop_and_clear_that_cannot_be_ordered_fail_closed(state):
    f = state / "hook.log"
    t = datetime(2026, 10, 19, 14, 0, tzinfo=UTC)
    write_log(state, rec(iso(t), "STOP"), clear(iso(t + timedelta(seconds=1))))
    assert hooks.sticky_stop(f) is None
    write_log(state, rec(iso(t), "STOP"), clear(iso(t)))                # the same instant: cleared
    assert hooks.sticky_stop(f) is None
    write_log(state, rec(iso(t), "STOP"), clear(iso(t - timedelta(hours=1))))   # the clear is dated earlier
    s = hooks.sticky_stop(f)
    assert s["why"] == "unordered" and "cannot be ordered" in hooks.sticky_stop_message(s)
    for bad in ("garbage", None, 12):                                  # a clear without a readable date
        write_log(state, rec(iso(t), "STOP"), clear(bad))
        assert hooks.sticky_stop(f)["why"] == "unordered", bad
    # a STOP without a readable date is still a STOP; a later, dated clear in the file clears it
    write_log(state, rec("garbage", "STOP"))
    assert hooks.sticky_stop(f)["why"] == "active"
    write_log(state, rec("garbage", "STOP"), clear(iso(t)))
    assert hooks.sticky_stop(f) is None
    # file order decides which is newer: a STOP after the clear is active whatever its date
    write_log(state, clear(iso(t)), rec(iso(t - timedelta(days=1)), "STOP"))
    assert hooks.sticky_stop(f)["why"] == "active"


def test_resume_says_when_stop_stays_active(state, monkeypatch, capsys):
    write_log(state, rec(iso(datetime.now(UTC)), "STOP", reason="kept"))

    def no_record(*a, **k):
        raise PermissionError(13, "locked")
    monkeypatch.setattr(cli, "log_flag_clear", no_record)              # the CLEAR record cannot be written
    capsys.readouterr()
    assert resume(monkeypatch) == 1
    err = capsys.readouterr().err
    assert "could not record this in hook.log" in err and "WARNING: STOP is still active" in err
    assert "STOP" in ledger.read_flags() and not any(e["decision"] == "CLEAR" for e in log_lines(state))


def test_resume_refuses_when_a_new_stop_arrives_while_confirming(state, monkeypatch, capsys):
    assert cli.main(["stop", "first"]) == 0

    def confirm_late(prompt=""):                                        # the hook stops again meanwhile
        hooks.write_stop(paths(), "an agent order went live without approval", datetime.now(UTC))
        hooks.log("post", "mcp__robinhood-trading__place_equity_order", "STOP", BYPASS)
        return "resume"
    monkeypatch.setattr(builtins, "input", confirm_late)
    monkeypatch.setattr(sys, "stdin", Tty(""))
    capsys.readouterr()
    assert cli.main(["resume"]) == 1
    assert "flags changed while you were confirming" in capsys.readouterr().err
    assert (state / "STOP").exists() and not any(e["decision"] == "CLEAR" for e in log_lines(state))


# ------------------------------------------------------------------ reading hook.log

def test_records_that_count(state):
    f = state / "hook.log"
    t = "2026-10-19T14:00:00.000000Z"
    later = "2026-10-19T15:00:00.000000Z"
    write_log(state, rec(t, "block", hook="pre", reason="STOP file present: no new orders"))     # not a STOP record
    assert hooks.sticky_stop(f) is None
    write_log(state, rec(t, "STOP", hook="cli", tool="stop", reason="by hand"))
    assert hooks.sticky_stop(f)["reason"] == "by hand" and hooks.sticky_stop(f)["ts"] == t
    write_log(state, rec(t, "STOP"), clear(later, flags=["FLATTEN", "BLOCK_BUYS"]))           # STOP not cleared
    assert hooks.sticky_stop(f)["why"] == "active"
    write_log(state, rec(t, "STOP"), rec(later, "RESOLVE", hook="cli", tool="resume", reason="cleared STOP (x)"))
    assert hooks.sticky_stop(f)["why"] == "active"                     # only a CLEAR clears
    write_log(state, rec(t, "STOP"), rec(later, "CLEAR", hook="pre", tool="resume", flags=["STOP"]))
    assert hooks.sticky_stop(f)["why"] == "active"                     # only resume's own (hook "cli") record
    # a CLEAR written before records had "flags": its reason names STOP first
    write_log(state, rec(t, "STOP"), rec(later, "CLEAR", hook="cli", tool="resume", reason="cleared STOP (was: x)"))
    assert hooks.sticky_stop(f) is None
    write_log(state, rec(t, "STOP"), rec(later, "CLEAR", hook="cli", tool="resume",
                                         reason="cleared FLATTEN (was: STOP soon); BLOCK_BUYS (was: y)"))
    assert hooks.sticky_stop(f)["why"] == "active"
    # several STOPs and clears: the newest of each decides
    write_log(state, rec(t, "STOP", reason="a"), clear(later), rec("2026-10-19T16:00:00Z", "STOP", reason="b"),
              clear("2026-10-19T17:00:00Z"), rec("2026-10-19T18:00:00Z", "STOP", reason="c"))
    s = hooks.sticky_stop(f)
    assert s["reason"] == "c" and s["ts"] == "2026-10-19T18:00:00Z"
    with open(f, "a") as fh:
        fh.write(clear("2026-10-19T19:00:00Z") + "\n")
    assert hooks.sticky_stop(f) is None


def test_malformed_lines_are_ignored(state):
    f = state / "hook.log"
    t = "2026-10-19T14:00:00Z"
    junk = ["not json at all", "[1, 2, 3]", "{}", '"STOP"', "null", '{"ts": "x", "decision": "ST', "", "   ",
            "STOP STOP", '{"decision": "CLEAR", "flags": ["STOP"]'] 
    write_log(state, *junk)
    assert hooks.sticky_stop(f) is None
    write_log(state, rec(t, "STOP"), *junk, clear("2026-10-19T15:00:00Z"), *junk)
    assert hooks.sticky_stop(f) is None
    with open(f, "ab") as fh:                                           # bytes that are not UTF-8
        fh.write(b"\xff\xfe\x00garbage\n")
    assert hooks.sticky_stop(f) is None
    # a damaged line that still reads "decision": "STOP" (two appends interleaved) counts as a STOP: fail closed
    with open(f, "a") as fh:
        fh.write('{"ts": "2026-10-19T16:00:00Z", "hook": "post", "tool": "x", "decision": "STOP", "reas{"ts": 1}\n')
    s = hooks.sticky_stop(f)
    assert s["why"] == "active" and s["ts"] is None and "damaged" in s["reason"]
    assert "at an unknown time" in hooks.sticky_stop_message(s)
    with open(f, "a") as fh:
        fh.write(clear("2026-10-19T17:00:00Z") + "\n")
    assert hooks.sticky_stop(f) is None
    # an escaped quote inside a reason is not a STOP record
    write_log(state, '{"ts": "t", "hook": "pre", "decision": "block", "reason": "\\"decision\\": \\"STOP\\"" broken')
    assert hooks.sticky_stop(f) is None


def test_large_hook_log_is_read_from_its_tail(state, monkeypatch):
    f = state / "hook.log"
    filler = rec("2026-10-19T13:00:00.000000Z", "captured", reason="saved to the inbox " + "x" * 150) + "\n"
    n = hooks.STOP_LOG_TAIL // len(filler) + 2000                       # well past the 2 MB tail
    t = "2026-10-19T14:00:00.000000Z"
    with open(f, "w") as fh:
        fh.write(rec(t, "STOP", reason="too old to see") + "\n")         # outside the tail: not read
        fh.write(filler * n)
    assert f.stat().st_size > hooks.STOP_LOG_TAIL + 100_000
    assert hooks.sticky_stop(f) is None
    with open(f, "a") as fh:
        fh.write(rec(t, "STOP", reason="recent") + "\n" + filler * 50)
    assert hooks.sticky_stop(f)["reason"] == "recent"
    with open(f, "a") as fh:
        fh.write(clear("2026-10-19T15:00:00.000000Z") + "\n" + filler * 50)
    assert hooks.sticky_stop(f) is None
    # only the tail is read: count the bytes the check reads
    read = []
    real = builtins.open

    class Counting:
        def __init__(self, fh):
            self.fh = fh

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.fh.close()

        def seek(self, *a):
            return self.fh.seek(*a)

        def read(self, *a):
            data = self.fh.read(*a)
            read.append(len(data))
            return data

    def counting_open(p, mode="r", *a, **k):
        fh = real(p, mode, *a, **k)
        return Counting(fh) if str(p).endswith("hook.log") else fh
    monkeypatch.setattr(builtins, "open", counting_open)
    assert hooks.sticky_stop(f) is None and sum(read) == hooks.STOP_LOG_TAIL
    monkeypatch.setattr(builtins, "open", real)
    # the cut's first, partial line is dropped, never parsed: the oldest bytes of the window
    line = json.dumps({"ts": t, "hook": "post", "reason": "z" * 200, "decision": "STOP"})
    f.write_text(line + "\n" + filler * 30)
    assert hooks.sticky_stop(f)["why"] == "active"                      # read whole: a STOP
    assert hooks.sticky_stop(f, tail=len(filler) * 30 + 40) is None     # cut inside it: its rest is dropped
    assert hooks.sticky_stop(f, tail=len(filler) * 30 + len(line) + 2)["why"] == "active"


def test_an_active_stop_is_carried_forward_before_it_leaves_the_tail(state):
    f = state / "hook.log"
    filler = rec("2026-10-19T13:00:00.000000Z", "captured", reason="saved to the inbox " + "x" * 150) + "\n"
    write_log(state, rec("2026-10-19T14:00:00.000000Z", "STOP", reason="kept"))
    assert not hooks.carry_stop_forward(f)                             # a small hook.log is not even read
    with open(f, "a") as fh:
        fh.write(filler * (hooks.STOP_LOG_TAIL // 2 // len(filler) + 50))   # the STOP is now over 1 MB back
    assert hooks.sticky_stop(f)["behind"] > hooks.STOP_LOG_TAIL // 2
    # the PostToolUse hook carries it forward after any Robinhood call, e.g. a read under STOP
    th.write_config(state)
    r = th.run(th.POST, state, th.ev("get_portfolio", {"account_number": th.ACCT}, {"data": {}}))
    assert r.returncode == 0
    last = log_lines(state)[-1]
    assert (last["hook"], last["decision"]) == ("post", "STOP")
    assert last["reason"].startswith("carried forward from 2026")
    assert last["reason"].endswith(": kept")
    assert last["origin"]["ts"] == "2026-10-19T14:00:00.000000Z" and last["origin"]["reason"] == "kept"
    s = hooks.sticky_stop(f)                                           # it reports the first STOP, not the carry
    assert s["why"] == "active" and s["behind"] < 1000 and s["reason"] == "kept"
    assert s["ts"] == "2026-10-19T14:00:00.000000Z" and s["id"] == last["origin"]["id"]
    assert not hooks.carry_stop_forward(f)                             # fresh again: nothing more to write
    # it survives far more log than the tail holds
    for _ in range(3):
        with open(f, "a") as fh:
            fh.write(filler * (hooks.STOP_LOG_TAIL // 2 // len(filler) + 50))
        assert hooks.carry_stop_forward(f)
    assert f.stat().st_size > 2 * hooks.STOP_LOG_TAIL and hooks.sticky_stop(f)["why"] == "active"
    # a cleared STOP is never carried forward
    with open(f, "a") as fh:
        fh.write(clear(iso(datetime.now(UTC))) + "\n" + filler * (hooks.STOP_LOG_TAIL // 2 // len(filler) + 50))
    assert not hooks.carry_stop_forward(f) and hooks.sticky_stop(f) is None


# ------------------------------------------------------------------ review 8: carries, clock, races, damaged lines

def post_stop(state):
    """A real PostToolUse STOP (an agent order went live while approvals are required), then the file goes away."""
    th.ready(state, approvals=True)
    r = th.run(th.POST, state, th.ev("place_equity_order", th.params(), th.place_resp(order_id="ord-1")))
    assert r.returncode == 0 and b"AGENTIC STOP" in r.stderr
    (state / "STOP").unlink()
    return sell_plan(state)


def filler(n_bytes):
    """Ordinary read lines (no STOP in them) totalling at least n_bytes."""
    line = rec(iso(datetime.now(UTC)), "allow", hook="pre", tool="mcp__robinhood-trading__get_equity_quotes",
               reason="read") + "\n"
    return line * (n_bytes // len(line) + 1)


def append(state, text):
    with open(state / "hook.log", "a") as fh:
        fh.write(text)


def test_an_unordered_stop_is_carried_forward_and_one_resume_clears_it(state, monkeypatch):
    th.ready(state)
    sell = sell_plan(state)
    now = datetime.now(UTC)
    write_log(state, rec(iso(now), "STOP", reason=BYPASS), clear(iso(now - timedelta(hours=1))))   # clock jumped back
    assert hooks.sticky_stop(state / "hook.log")["why"] == "unordered" and place(state, sell).returncode == 2
    append(state, filler(int(1.2 * (1 << 20))))                         # later runs' reads
    r = th.run(th.POST, state, th.ev("get_equity_quotes", {"symbols": ["ETHA"]}, {"data": {"results": []}}))
    assert r.returncode == 0
    last = log_lines(state)[-1]
    assert (last["decision"], last["origin"]["reason"]) == ("STOP", BYPASS)    # carried, after the clear
    s = hooks.sticky_stop(state / "hook.log")
    assert s["why"] == "active" and s["reason"] == BYPASS and s["ts"] == iso(now)
    append(state, filler(int(0.9 * (1 << 20))))                         # the first STOP is now out of the window
    assert hooks.sticky_stop(state / "hook.log")["reason"] == BYPASS and place(state, sell).returncode == 2
    assert resume(monkeypatch) == 0 and place(state, sell).returncode == 0     # one resume clears it


def test_blocked_place_calls_carry_the_stop_forward(state):
    sell = post_stop(state)
    assert place(state, sell).returncode == 2
    block = (state / "hook.log").read_text().splitlines()[-1]
    assert json.loads(block)["decision"] == "block"
    append(state, (block + "\n") * (int(1.2 * (1 << 20)) // (len(block) + 1)))   # blocked attempts: no PostToolUse
    r = place(state, sell)                                              # the real PreToolUse hook blocks, then carries
    assert r.returncode == 2
    last = log_lines(state)[-1]
    assert (last["hook"], last["decision"]) == ("pre", "STOP") and BYPASS in last["origin"]["reason"]
    append(state, (block + "\n") * (int(1.5 * (1 << 20)) // (len(block) + 1)))   # past the first STOP's window
    s = hooks.sticky_stop(state / "hook.log")
    assert s["why"] == "active" and BYPASS in s["reason"] and place(state, sell).returncode == 2
    # a blocked call with a small hook.log, or with no STOP in force, writes nothing more
    n = len(log_lines(state))
    assert th.run(th.PRE, state, th.ev("place_option_order", {"account_number": th.ACCT})).returncode == 2
    assert [e["decision"] for e in log_lines(state)[n:]] == ["block"]


def test_post_hook_carries_even_when_handling_fails(state, monkeypatch):
    from agentic.hooks import post_tool_use
    monkeypatch.setattr(post_tool_use, "H", hooks)
    th.write_config(state)
    write_log(state, rec(iso(datetime.now(UTC)), "STOP", reason="kept"))
    append(state, filler(int(1.2 * (1 << 20))))

    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(post_tool_use, "_readback", boom)
    with pytest.raises(RuntimeError):
        post_tool_use.handle(th.ev("get_equity_orders", {"account_number": th.ACCT}, {"data": {"results": []}}))
    assert log_lines(state)[-1]["origin"]["reason"] == "kept"


def test_resume_clears_a_stop_dated_in_the_future(state, monkeypatch, capsys):
    th.ready(state)
    sell = sell_plan(state)
    future = iso(datetime.now(UTC) + timedelta(days=2))                 # the clock was 2 days ahead when written
    write_log(state, rec(future, "STOP", reason="clock ahead"))
    s = hooks.sticky_stop(state / "hook.log")
    assert place(state, sell).returncode == 2
    capsys.readouterr()
    assert resume(monkeypatch) == 0
    out = capsys.readouterr()
    assert f"dated {future}, in the future" in out.out and "cleared STOP" in out.out and not out.err
    c = log_lines(state)[-1]
    assert (c["decision"], c["through"], c["through_ts"]) == ("CLEAR", s["id"], future)
    assert hooks.sticky_stop(state / "hook.log") is None and place(state, sell).returncode == 0
    # a copy of that CLEAR line appended after a new STOP (a replay) does not clear the new STOP
    old_clear = (state / "hook.log").read_text().splitlines()[-1]
    assert cli.main(["stop", "second"]) == 0
    (state / "STOP").unlink()
    append(state, old_clear + "\n")
    s2 = hooks.sticky_stop(state / "hook.log")
    assert s2["why"] == "active" and s2["reason"] == "second" and place(state, sell).returncode == 2
    assert resume(monkeypatch) == 0 and place(state, sell).returncode == 0


def test_a_clear_names_the_stop_it_clears(state):
    f = state / "hook.log"
    t = "2026-10-19T14:00:00.000000Z"
    write_log(state, rec(t, "STOP", reason="a"))
    sid = hooks.stop_state(f)[1]["id"]
    write_log(state, rec(t, "STOP", reason="a"),
              clear("2026-10-19T13:00:00Z").replace('"flags"', f'"through": "{sid}", "flags"'))
    assert hooks.sticky_stop(f) is None                                 # named: cleared, though dated earlier
    for through in ("0" * 16, None, 12):                                # another STOP, none seen, junk
        write_log(state, rec(t, "STOP", reason="a"), clear("2026-10-19T15:00:00Z").replace(
            '"flags"', f'"through": {json.dumps(through)}, "flags"'))
        s = hooks.sticky_stop(f)
        assert s["why"] == "active" and s["reason"] == "a", through     # a STOP recorded after the prompt
    # the newest STOP record is reported whether or not it is cleared
    write_log(state, rec(t, "STOP", reason="a"), clear("2026-10-19T15:00:00Z"))
    assert hooks.stop_state(f) == (None, {"id": sid, "ts": t, "reason": "a"})
    assert hooks.stop_state(state / "missing.log") == (None, None)


def test_a_stop_recorded_while_resume_clears_stays_active(state, monkeypatch, capsys):
    sell = post_stop(state)
    first = hooks.sticky_stop(state / "hook.log")
    real_clear = ledger.clear_flag

    def clear_then_hook_stops(name, *a, **k):                           # after the re-check, before the CLEAR record
        real_clear(name, *a, **k)
        th.run(th.POST, state, th.ev("place_equity_order", th.params(), th.place_resp(order_id="ord-2")))
    monkeypatch.setattr(ledger, "clear_flag", clear_then_hook_stops)
    capsys.readouterr()
    assert resume(monkeypatch) == 1
    assert "a new STOP was recorded while resume was clearing" in capsys.readouterr().err
    c = [e for e in log_lines(state) if e["decision"] == "CLEAR"]
    assert len(c) == 1 and c[0]["through"] == first["id"]
    s = hooks.sticky_stop(state / "hook.log")
    assert s["why"] == "active" and s["id"] != first["id"]
    (state / "STOP").unlink()
    assert place(state, sell).returncode == 2                           # the new STOP is sticky
    monkeypatch.setattr(ledger, "clear_flag", real_clear)
    assert resume(monkeypatch) == 0 and place(state, sell).returncode == 0


def test_resume_says_when_a_new_stop_file_appears_while_clearing(state, monkeypatch, capsys):
    assert cli.main(["stop", "first"]) == 0
    real_clear = ledger.clear_flag

    def clear_then_file(name, *a, **k):                                 # a STOP file whose hook.log record failed
        real_clear(name, *a, **k)
        hooks.write_stop(paths(), "second", datetime.now(UTC))
    monkeypatch.setattr(ledger, "clear_flag", clear_then_file)
    capsys.readouterr()
    assert resume(monkeypatch) == 1
    assert "a new STOP file appeared while resume was clearing" in capsys.readouterr().err
    assert "STOP" in ledger.read_flags()


def test_resume_refuses_when_only_hook_log_records_a_new_stop_while_confirming(state, monkeypatch, capsys):
    assert cli.main(["stop", "first"]) == 0                             # the file text stays the same below

    def confirm_late(prompt=""):
        hooks.log("post", "mcp__robinhood-trading__place_equity_order", "STOP", BYPASS)
        return "resume"
    monkeypatch.setattr(builtins, "input", confirm_late)
    monkeypatch.setattr(sys, "stdin", Tty(""))
    capsys.readouterr()
    assert cli.main(["resume"]) == 1
    assert "flags changed while you were confirming" in capsys.readouterr().err
    assert (state / "STOP").exists() and not any(e["decision"] == "CLEAR" for e in log_lines(state))


def test_carries_keep_the_first_stop(state):
    th.ready(state, approvals=True)
    f = state / "hook.log"
    t = datetime.now(UTC).replace(microsecond=123456)
    write_log(state, rec(iso(t), "STOP", reason=BYPASS + " (placed_agent=agentic, state=queued)"))
    for _ in range(8):                                                  # about 8.5 MB of log under one STOP
        append(state, filler(int(1.05 * (1 << 20))))
        assert hooks.carry_stop_forward(f)
    carried = [e for e in log_lines(state) if e["decision"] == "STOP"][1:]
    assert len(carried) == 8
    want = f"carried forward from {t:%Y-%m-%dT%H:%M:%S}Z: {BYPASS} (placed_agent=agentic, state=queued)"
    assert all(e["reason"] == want for e in carried)                    # never nested, no masked digits
    assert {e["origin"]["ts"] for e in carried} == {iso(t)}
    s = hooks.sticky_stop(f)
    assert s["ts"] == iso(t) and s["reason"].startswith(BYPASS)
    banner = ledger.flag_banner()                                       # the STOP file is missing
    assert banner[0].startswith(f"!!! {STICKY} (written {iso(t)}: {BYPASS}")
    assert banner[1].startswith("!!! APPROVAL BYPASS")
    # a carry written before records had "origin": its nested prefixes are dropped
    write_log(state, rec(iso(t), "STOP", reason="carried forward from 2026-10-19T14:00:00.***Z: carried forward "
                                                "from an unknown time: the real reason"))
    s = hooks.sticky_stop(f)
    assert (s["ts"], s["reason"]) == (None, "the real reason")


def test_a_deeply_nested_damaged_line_never_crashes(state, monkeypatch, capsys):
    from agentic import universe
    nested = "[" * 100_000
    write_log(state, nested + "STOP")                                   # no STOP record in it
    assert hooks.sticky_stop(state / "hook.log") is None
    capsys.readouterr()
    assert cli.main(["status"]) == 0 and resume(monkeypatch) == 0
    assert "no flags set" in capsys.readouterr().out
    assert universe.recent_attempts(paths()["inbox"], "get_crypto_quotes") == ([], False)
    write_log(state, nested + '"decision": "STOP"')                     # a damaged STOP record: fail closed
    s = hooks.sticky_stop(state / "hook.log")
    assert s["why"] == "active" and s["ts"] is None and "damaged" in s["reason"]
    write_log(state, rec(iso(datetime.now(UTC)), "STOP", reason="real"), nested + "STOP")
    assert hooks.sticky_stop(state / "hook.log")["reason"] == "real"
    capsys.readouterr()
    assert cli.main(["status"]) == 0 and capsys.readouterr().out.startswith(f"!!! {STICKY}")
    assert resume(monkeypatch) == 0 and hooks.sticky_stop(state / "hook.log") is None
    # the journal readers skip such a line too (strict: an error the pre hook fails closed on)
    (state / "journal.jsonl").write_text(nested + "\n" + json.dumps({"event": "x"}) + "\n")
    assert ledger.read_journal() == [{"event": "x"}]
    assert hooks.read_journal(state / "journal.jsonl", strict=False) == [{"event": "x"}]
    with pytest.raises(ValueError):
        hooks.read_journal(state / "journal.jsonl")


def test_removing_hook_log_lifts_a_sticky_stop_as_documented(state):
    """Known limit (README section 6): hook.log missing means the STOP file check alone, so deleting, emptying,
    rotating or trimming hook.log lifts a sticky STOP. The docs must say so (test_docs_describe_the_sticky_stop)."""
    sell = post_stop(state)
    assert place(state, sell).returncode == 2
    (state / "hook.log").unlink()
    assert place(state, sell).returncode == 0


# ------------------------------------------------------------------ banners and docs

def test_doctor_and_digest_show_the_sticky_stop(state, monkeypatch, capsys):
    from agentic import signals as sg
    assert cli.main(["init"]) == 0
    write_log(state, rec("2026-10-19T14:00:00.000000Z", "STOP", reason=BYPASS))
    rep = doctor.Report()
    doctor._check_flags(rep)
    rows = [r for r in rep.rows if r[1] == "flags"]
    assert rows[0][0] == "WARN" and rows[0][2].startswith(STICKY) and MISSING in rows[0][2]
    assert rows[1][2].startswith("APPROVAL BYPASS") and not any(r[0] == "FAIL" for r in rep.rows)
    written = []
    monkeypatch.setattr(sg, "compute_signals", lambda *a, **k: {"assets": []})
    monkeypatch.setattr(sg, "format_digest", lambda sig, full=False: "MONEYLINE DIGEST synthetic")
    monkeypatch.setattr(sg, "write_signals", lambda sig: paths()["base"] / "signals" / "s.json")
    monkeypatch.setattr(sg, "write_digest", lambda sig, text: written.append(text) or paths()["base"] / "d.txt")
    cli._signals(cli.build_parser().parse_args(["signals"]), {}, datetime.now(UTC))
    assert written[-1].splitlines()[0].startswith(f"!!! {STICKY}")
    assert resume(monkeypatch) == 0
    rep = doctor.Report()
    doctor._check_flags(rep)
    assert [r[0] for r in rep.rows] == ["PASS"]
    cli._signals(cli.build_parser().parse_args(["signals"]), {}, datetime.now(UTC))
    assert written[-1] == "MONEYLINE DIGEST synthetic"


def test_docs_describe_the_sticky_stop():
    readme = (REPO / "agentic" / "README.md").read_text(encoding="utf-8")
    spec = (REPO / "agentic" / "SPEC.md").read_text(encoding="utf-8")
    kill = readme.split("## 6. Kill switch and flags", 1)[1].split("\n## ", 1)[0]
    assert "sticky" in kill.lower() and "only `resume`" in kill and "every clear is logged" in kill.lower()
    assert "FLATTEN" in kill and "file-based" in kill
    assert "sticky_stop" in spec and "STOP_LOG_TAIL" in spec and "fail closed" in spec.lower()
    # the known limit: deleting, emptying, trimming, rotating or replacing hook.log lifts a sticky STOP
    handoff = (REPO / "HANDOFF.md").read_text(encoding="utf-8")
    files = readme.split("## 14. Files", 1)[1]
    for text in (kill, spec, handoff, files):
        flat = " ".join(text.split()).lower()
        assert all(w in flat for w in ("deleting, emptying", "trimming", "hook.log")), text[:80]
    assert "Leave hook.log alone while STOP may be set" in kill and "older copy" in kill
    assert "never trim, rotate or delete `hook.log`" in " ".join(kill.split())
    item1 = " ".join(spec.split("1. no STOP", 1)[1].split("2. config `live`", 1)[0].split())
    assert "lifts a sticky STOP without a `resume`" in item1 and "\"through\"" in item1
    assert "PreToolUse hook after every call it blocks" in item1 and "unordered" in item1
