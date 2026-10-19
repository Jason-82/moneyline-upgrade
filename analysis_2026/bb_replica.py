"""
Runner of the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md; its Addendum's code layout:
"bb_replica.py is the runner"; "Controls (run before primary results are read)": "A failed control stops the study
until it is fixed"; the Sensitivity grid's F: "the engine writes the nine counts to results_bb/ before any return is
read"; "H11b ... Run only after every primary result has been written to results_bb/"). Contract: the scratchpad's
bb_engine_spec.md, "Integration layer" ("bb_fit.py F frequency-matched counts (written before any return)").

    python3 -m analysis_2026.bb_replica controls [--out DIR] [--jobs 4] [--only a,b]
    python3 -m analysis_2026.bb_replica fit      [--out DIR] [--jobs 4] --only fcount     # F's counts, before any return
    python3 -m analysis_2026.bb_replica primary  [--out DIR] [--jobs 4] [--only H1,H6]
    python3 -m analysis_2026.bb_replica report   [--out DIR]
    python3 -m analysis_2026.bb_replica desc     [--out DIR] [--jobs 4] [--only ...]
    python3 -m analysis_2026.bb_replica fit      [--out DIR] [--jobs 4] [--only ...]
    python3 -m analysis_2026.bb_replica report   [--out DIR]
    python3 -m analysis_2026.bb_replica all      [--out DIR] [--jobs 4]          # every line above, in that order
    python3 -m analysis_2026.bb_replica status   [--out DIR]       # which stages have run (no result is printed)
    python3 -m analysis_2026.bb_replica selftest

DIR defaults to analysis_2026/results_bb (layout: controls/, primary/, rows/, headline/, routes/, tv/, scorecard/,
explore/, fcount/, h11/, h11b/, h12/, luck/, verdicts.csv, verdicts.txt).

Stages
  controls  bb_controls.run(out_dir, which, jobs) -> controls/summary.json (all_passed), summary.txt, inference.json
            (level95, level_noedge). Exit 2 if not every control passed.
  primary   REFUSES (exit 2) unless controls/summary.json has "all_passed": true and controls/inference.json gives a
            level_noedge, and unless F's counts are written (fcount/F.json naming F's cell and fcount/counts.csv, from
            a full bb_fit run); then bb_tests.run(out_dir, which, jobs, level_noedge, level95) -> primary/.
  desc      bb_desc.run(out_dir, which=None, jobs=4): descriptive rows. Refuses on the same two gates.
  fit       bb_fit.run(out_dir, which=None, jobs=4): F counts, H11, H11b, H12, luck. Refuses on the controls gate.
            `--only fcount` (F's counts, PRE_PRIMARY_FIT) is the one part that runs before primary; any other part,
            and fit without --only, refuses unless every primary result is written (primary/tests.json holds all 12
            tests and none errored: primary_status, the report's check). A part list without fcount also needs F's
            counts on disk.
  report    Refuses on the controls gate; bb_tests.report(out_dir, level_noedge, level95) with the controls' levels
            (it refuses unless every test's bounds are at those levels): Holm across the 12, gates, halves, verdicts,
            answer map -> verdicts.csv / .txt.
  all       controls -> (stop unless every control passed) -> fit --only fcount -> primary -> report -> desc -> fit
            (bb_fit's other parts) -> report. Any refusal stops it.

Coding choices (also in the build report)
1. The controls gate is strict: summary.json must parse, its all_passed must be the JSON value true, and it must not be
   a quick or partial run (bb_controls' quick / partial / valid_gate fields); inference.json must give level_noedge as
   a number in (0.95, 1) (the pre-registration's 1 - 0.05/12 = 0.99583, or the controls'
   widened level); level95 defaults to 0.95 if absent. Anything else refuses, naming the reason.
2. desc, fit and report are gated on the controls too (the pre-registration stops the whole study on a failed
   control; report's NO EDGE bounds must be at the controls' level).
3. Modules written by other agents are called through _call_run, which passes the results directory, the subset and
   the worker count by name under the names their run() uses: bb_controls.run(quick=False, out=results_bb/controls,
   workers, only); bb_desc / bb_fit as run(out_dir=results_bb, which, jobs) per the integration contract (an `out`
   parameter gets results_bb). A run() without a recognisable results-directory parameter, or a missing module,
   stops with its name.
4. Nothing here prints a result: each stage prints where it wrote; verdicts are read from verdicts.txt.
5. Ordering. F's counts come before any return: primary and desc refuse until fcount/F.json (a non-quick bb_fit run
   naming F's cell) and fcount/counts.csv exist, and `all` runs `fit --only fcount` right after the controls. Every
   other bb_fit part (luck, H12, H11b, H11) runs only after every primary result is written. The pre-registration
   orders only H11b so; the rest follow it because H11 reads H11b's decoys and the luck benchmark, and the study's
   stage order is controls -> F -> primary -> descriptive.
6. `all` runs report twice: right after primary, because bb_desc's rule scorecard takes the Holm-family verdicts
   from verdicts.csv (bb_desc choice 10), and at the end, because the answer map's "You can trade it" reads routes/
   (bb_desc's routes part). Both passes read the same tests.json, so the verdicts are the same; the first pass's
   answer map says "routes not run".
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import inspect
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RES = ROOT / "analysis_2026" / "results_bb"
STAGES = ("controls", "primary", "desc", "fit", "report", "all", "status", "selftest")
PRE_PRIMARY_FIT = ("fcount",)                  # the bb_fit part that runs before any return (choice 5)
FCOUNT_FILES = ("F.json", "counts.csv")       # bb_fit's fcount/ outputs
RULE_CONTROLS = ("The pre-registration stops the study until every control passes (results_bb/controls/summary.json "
                 "all_passed true).")
RULE_FCOUNT = ("The pre-registration (F): 'the engine writes the nine counts to results_bb/ before any return is "
               "read'. Run `bb_replica fit --only fcount` first.")
RULE_PRIMARY = ("The pre-registration (H11b): 'Run only after every primary result has been written to results_bb/'. "
                "Only `fit --only fcount` runs before primary.")


# ============================================================================ the gates
def controls_status(out_dir=RES) -> dict:
    """{"ok": bool, "why": str, "level_noedge": float | None, "level95": float | None} from controls/summary.json and
    controls/inference.json (coding choice 1)."""
    d = Path(out_dir) / "controls"
    res = {"ok": False, "why": "", "level_noedge": None, "level95": None}
    sj = d / "summary.json"
    if not sj.exists():
        res["why"] = f"{sj} not found: run the controls first"
        return res
    try:
        S = json.loads(sj.read_text())
    except (ValueError, OSError) as e:
        res["why"] = f"{sj} unreadable: {e}"
        return res
    if not isinstance(S, dict) or S.get("all_passed") is not True:
        failed = [k for k, v in S.items() if isinstance(v, dict) and v.get("passed") is False] \
            if isinstance(S, dict) else None
        res["why"] = f"{sj}: all_passed is {S.get('all_passed') if isinstance(S, dict) else S!r}, not true" + \
            (f" (failed: {failed})" if failed else "")
        return res
    if S.get("quick") is True or S.get("partial") is True or S.get("valid_gate") is False:
        res["why"] = (f"{sj}: a quick or partial controls run (quick {S.get('quick')}, partial {S.get('partial')}, "
                      f"valid_gate {S.get('valid_gate')}) cannot open the gate; run the full controls")
        return res
    ij = d / "inference.json"
    if not ij.exists():
        res["why"] = f"{ij} not found: the NO EDGE level (level_noedge) is required"
        return res
    try:
        I = json.loads(ij.read_text())
    except (ValueError, OSError) as e:
        res["why"] = f"{ij} unreadable: {e}"
        return res
    lv = I.get("level_noedge") if isinstance(I, dict) else None
    if isinstance(lv, bool) or not isinstance(lv, (int, float)) or not (0.95 < float(lv) < 1.0) or math.isnan(lv):
        res["why"] = f"{ij}: level_noedge {lv!r} is not a number in (0.95, 1)"
        return res
    l95 = I.get("level95", 0.95)
    if isinstance(l95, bool) or not isinstance(l95, (int, float)) or not (0.95 <= float(l95) < 1.0):
        res["why"] = f"{ij}: level95 {l95!r} is not a number in [0.95, 1)"
        return res
    res.update(ok=True, why="every control passed", level_noedge=float(lv), level95=float(l95))
    return res


def fcount_status(out_dir=RES) -> dict:
    """{"ok", "why"}: F's nine W16 tranche counts are on disk (choice 5): fcount/F.json parses, names F's cell under
    "F" and is not a quick (self-test sized) run, and fcount/counts.csv exists."""
    d = Path(out_dir) / "fcount"
    miss = [n for n in FCOUNT_FILES if not (d / n).exists()]
    if miss:
        return {"ok": False, "why": f"{d}: {', '.join(miss)} not found: F's nine W16 tranche counts are not written"}
    try:
        J = json.loads((d / "F.json").read_text())
    except (ValueError, OSError) as e:
        return {"ok": False, "why": f"{d / 'F.json'} unreadable: {e}"}
    if not isinstance(J, dict) or not isinstance(J.get("F"), dict):
        return {"ok": False, "why": f"{d / 'F.json'} names no F cell (no 'F' object)"}
    if J.get("quick") is True:
        return {"ok": False, "why": f"{d / 'F.json'} comes from a quick (self-test sized) bb_fit run"}
    return {"ok": True, "why": "F's counts written"}


def primary_status(out_dir=RES) -> dict:
    """{"ok", "why", "missing", "errored"}: every primary result is written (choice 5): primary/tests.json holds all
    12 bb_tests.TESTS and none carries an error (the report's own check)."""
    from analysis_2026.bb_tests import TESTS
    tj = Path(out_dir) / "primary" / "tests.json"
    res = {"ok": False, "why": "", "missing": list(TESTS), "errored": []}
    if not tj.exists():
        res["why"] = f"{tj} not found: no primary result is written"
        return res
    try:
        J = json.loads(tj.read_text())
    except (ValueError, OSError) as e:
        res["why"] = f"{tj} unreadable: {e}"
        return res
    T = J.get("tests") if isinstance(J, dict) else None
    T = T if isinstance(T, dict) else {}
    missing = [t for t in TESTS if not isinstance(T.get(t), dict)]
    errored = [t for t in TESTS if isinstance(T.get(t), dict) and "error" in T[t]]
    res.update(missing=missing, errored=errored)
    if missing or errored:
        res["why"] = f"{tj}: not every primary result is written (missing {missing}, errored {errored})"
        return res
    res.update(ok=True, why=f"all {len(TESTS)} primary results written")
    return res


def _refuse(stage: str, why: str, rule: str, say=print) -> int:
    say(f"bb_replica {stage}: REFUSED - {why}. {rule}")
    return 2


# ============================================================================ stages
OUT_SUB = {"bb_controls": "controls"}          # modules whose `out` argument is their own subdirectory
ALIASES = {"which": ("which", "only"), "jobs": ("jobs", "workers", "n_jobs")}
OUT_NAMES = ("out_dir", "out", "outdir", "root", "results_dir")


def _call_run(modname: str, out_dir, which=None, jobs: int = 4):
    """module.run(...) with the results directory, the subset and the worker count passed BY NAME under the names
    run() uses (choice 3): out_dir / out / root (bb_controls' `out` is results_bb/controls), which / only, jobs /
    workers / n_jobs, and quick=False where run() has a quick switch. A run() whose results-directory parameter
    cannot be identified stops instead of receiving the path in some other positional parameter."""
    try:
        mod = importlib.import_module(f"analysis_2026.{modname}")
    except ModuleNotFoundError as e:
        if e.name in (f"analysis_2026.{modname}", modname):
            raise SystemExit(f"bb_replica: analysis_2026/{modname}.py is not available ({e})")
        raise
    fn = getattr(mod, "run", None)
    if fn is None:
        raise SystemExit(f"bb_replica: analysis_2026/{modname}.py has no run()")
    P = inspect.signature(fn).parameters
    kw = {}
    oname = next((n for n in OUT_NAMES if n in P), None)
    if oname is None:
        raise SystemExit(f"bb_replica: {modname}.run{inspect.signature(fn)} has no results-directory parameter "
                         f"({', '.join(OUT_NAMES)})")
    kw[oname] = str(Path(out_dir) / OUT_SUB[modname]) if (oname == "out" and modname in OUT_SUB) else str(out_dir)
    for val, names in ((which, ALIASES["which"]), (jobs, ALIASES["jobs"])):
        n = next((x for x in names if x in P), None)
        if n is not None:
            kw[n] = val
    if "quick" in P:
        kw["quick"] = False
    return fn(**kw)


def cmd_controls(out_dir=RES, jobs: int = 4, only=None, say=print) -> int:
    t0 = time.time()
    _call_run("bb_controls", out_dir, which=only, jobs=jobs)
    st = controls_status(out_dir)
    say(f"bb_replica controls: done in {time.time() - t0:.0f} s; {'every control passed' if st['ok'] else st['why']}")
    return 0 if st["ok"] else 2


def cmd_primary(out_dir=RES, jobs: int = 4, only=None, say=print) -> int:
    st = controls_status(out_dir)
    if not st["ok"]:
        return _refuse("primary", st["why"], RULE_CONTROLS, say)
    fc = fcount_status(out_dir)
    if not fc["ok"]:
        return _refuse("primary", fc["why"], RULE_FCOUNT, say)
    from analysis_2026 import bb_tests
    bb_tests.run(out_dir, which=only, jobs=jobs, level_noedge=st["level_noedge"], level95=st["level95"], say=say)
    return 0


def cmd_desc(out_dir=RES, jobs: int = 4, only=None, say=print) -> int:
    st = controls_status(out_dir)
    if not st["ok"]:
        return _refuse("desc", st["why"], RULE_CONTROLS, say)
    fc = fcount_status(out_dir)
    if not fc["ok"]:
        return _refuse("desc", fc["why"], RULE_FCOUNT, say)
    t0 = time.time()
    _call_run("bb_desc", out_dir, which=only, jobs=jobs)
    say(f"bb_replica desc: done in {time.time() - t0:.0f} s")
    return 0


def cmd_fit(out_dir=RES, jobs: int = 4, only=None, say=print) -> int:
    st = controls_status(out_dir)
    if not st["ok"]:
        return _refuse("fit", st["why"], RULE_CONTROLS, say)
    parts = None if only is None else [str(p).strip().lower() for p in only if str(p).strip()]
    if parts is None or not set(parts) <= set(PRE_PRIMARY_FIT):
        ps = primary_status(out_dir)
        if not ps["ok"]:
            return _refuse("fit", ps["why"], RULE_PRIMARY, say)
        if parts is not None and not set(PRE_PRIMARY_FIT) & set(parts):
            fc = fcount_status(out_dir)
            if not fc["ok"]:
                return _refuse("fit", fc["why"], RULE_FCOUNT, say)
    t0 = time.time()
    _call_run("bb_fit", out_dir, which=parts, jobs=jobs)
    say(f"bb_replica fit: done in {time.time() - t0:.0f} s")
    return 0


def cmd_report(out_dir=RES, say=print) -> int:
    st = controls_status(out_dir)
    if not st["ok"]:
        return _refuse("report", st["why"], RULE_CONTROLS, say)
    from analysis_2026 import bb_tests
    bb_tests.report(out_dir, say=say, level_noedge=st["level_noedge"], level95=st["level95"])
    return 0


def _fit_rest() -> list | None:
    """bb_fit's parts other than F's counts, in bb_fit's order (None: bb_fit without PARTS runs every part)."""
    try:
        from analysis_2026 import bb_fit
        P = list(bb_fit.PARTS)
    except (ImportError, AttributeError):
        return None
    return [p for p in P if p not in PRE_PRIMARY_FIT]


def cmd_all(out_dir=RES, jobs: int = 4, say=print) -> int:
    rc = cmd_controls(out_dir, jobs, say=say)
    if rc:
        say("bb_replica all: stopped after the controls (not every control passed)")
        return rc
    steps = (("fit --only fcount (F's counts, before any return)",
              lambda: cmd_fit(out_dir, jobs, list(PRE_PRIMARY_FIT), say=say)),
             ("primary", lambda: cmd_primary(out_dir, jobs, say=say)),
             ("report (first pass: bb_desc's scorecard reads the Holm verdicts)", lambda: cmd_report(out_dir, say=say)),
             ("desc", lambda: cmd_desc(out_dir, jobs, say=say)),
             ("fit (H11, H11b, H12, luck)", lambda: cmd_fit(out_dir, jobs, _fit_rest(), say=say)),
             ("report", lambda: cmd_report(out_dir, say=say)))
    for name, fn in steps:
        rc = fn()
        if rc:
            say(f"bb_replica all: stopped at {name} (exit {rc})")
            return rc
    return 0


def cmd_status(out_dir=RES, say=print) -> int:
    out = Path(out_dir)
    st = controls_status(out)
    say(f"controls: {'passed' if st['ok'] else 'NOT passed - ' + st['why']}"
        + (f" (level_noedge {st['level_noedge']}, level95 {st['level95']})" if st["ok"] else ""))
    fc = fcount_status(out)
    say(f"F's counts: {'written' if fc['ok'] else 'NOT written - ' + fc['why']}")
    tj = out / "primary" / "tests.json"
    if tj.exists():
        ps = primary_status(out)
        try:
            J = json.loads(tj.read_text())
            done = sorted(J.get("tests", {}))
        except (ValueError, OSError, AttributeError):
            done = []
        say(f"primary: {len(done)} tests written ({', '.join(done)}); "
            f"{'complete' if ps['ok'] else 'NOT complete - ' + ps['why']}")
    else:
        say("primary: not run")
    for d in ("rows", "headline", "routes", "tv", "scorecard", "explore", "fcount", "h11", "h11b", "h12", "luck"):
        p = out / d
        say(f"{d}: {len(list(p.glob('*'))) if p.exists() else 0} files")
    say(f"report: {'written' if (out / 'verdicts.txt').exists() else 'not written'}")
    return 0


# ============================================================================ self-test
def _write(tmp: Path, all_passed, level_noedge, level95) -> None:
    d = tmp / "controls"
    d.mkdir(parents=True, exist_ok=True)
    S = {"all_passed": True, "quick": True, "valid_gate": False} if all_passed == "quick" else {"all_passed": all_passed}
    (d / "summary.json").write_text(json.dumps(S))
    inf = {}
    if level_noedge is not None:
        inf["level_noedge"] = level_noedge
    if level95 is not None:
        inf["level95"] = level95
    (d / "inference.json").write_text(json.dumps(inf))


def _write_fcount(tmp: Path, quick: bool = False) -> None:
    """F's counts as bb_fit.run_fcount writes them (F.json with the F cell; counts.csv with is_F)."""
    d = tmp / "fcount"
    d.mkdir(parents=True, exist_ok=True)
    (d / "F.json").write_text(json.dumps({"F": {"bars": "4h", "row": "S8", "universe": "S12 top 6"},
                                          "written_before_returns": True, "quick": quick}))
    (d / "counts.csv").write_text("cell,bars,row,universe,n_tranches,is_F\n0,1d,R0,BTC/ETH/SOL,40,False\n"
                                  "4,4h,S8,S12 top 6,900,True\n")


def _write_tests(tmp: Path, tests: dict | None) -> None:
    (tmp / "primary").mkdir(parents=True, exist_ok=True)
    (tmp / "primary" / "tests.json").write_text("{}" if tests is None else json.dumps({"meta": {}, "tests": tests}))


def check_gate(say=print) -> None:
    """Known answers of the gates and the stage order (review fixes included):
    - primary / desc / fit / report refuse (exit 2, stage not called) without a passed summary.json or a usable
      inference.json; with both, bb_tests.run and bb_tests.report get the controls' levels;
    - primary and desc refuse until F's counts are written (fcount/F.json naming F, not quick; counts.csv);
    - fit runs `--only fcount` before primary, and anything else only when primary/tests.json holds all 12 tests and
      none errored (a partial `primary --only H1`, errored tests, '{}' or an unreadable file refuse, whatever --only);
    - all: stops after failed controls; otherwise controls -> fit[fcount] -> primary -> report -> desc -> fit[the
      rest] -> report, with F's cell readable by bb_desc and the Holm verdicts written before desc runs."""
    import shutil
    import tempfile
    from analysis_2026 import bb_tests
    tmp = Path(tempfile.mkdtemp(prefix="bb_replica_gate_"))
    calls = []
    seen = {}
    real_run, real_report, real_call = bb_tests.run, bb_tests.report, globals()["_call_run"]
    ALL = {t: {"test_id": t} for t in bb_tests.TESTS}

    def fake_run(out_dir, which=None, jobs=4, level_noedge=None, level95=None, say=None, **k):
        calls.append(("primary", level_noedge, level95))
        seen["fcount_at_primary"] = fcount_status(out_dir)["ok"]
        _write_tests(Path(out_dir), ALL)

    def fake_report(out_dir, say=None, level_noedge=None, level95=None, **k):
        calls.append(("report", level_noedge, level95))
        (Path(out_dir) / "verdicts.csv").write_text("test_id,verdict,label\n")

    def fake_call(modname, out_dir, which=None, jobs=4, **k):
        calls.append((modname, None if which is None else list(which)))
        out = Path(out_dir)
        if modname == "bb_controls" and getattr(fake_call, "pass_controls", False):
            _write(out, True, 0.997, 0.96)
        if modname == "bb_fit" and (which is None or "fcount" in which):
            _write_fcount(out)
        if modname == "bb_desc":
            seen["verdicts_at_desc"] = (out / "verdicts.csv").exists()
            if importlib.util.find_spec("analysis_2026.bb_desc") is not None:
                from analysis_2026.bb_desc import read_f_cell
                seen["f_cell_at_desc"] = read_f_cell(out)[0]
    quiet = lambda s: None                                       # noqa: E731
    run_ = lambda *a: main([*a[:1], "--out", str(tmp), *a[1:]], say=quiet)      # noqa: E731
    bb_tests.run, bb_tests.report = fake_run, fake_report
    globals()["_call_run"] = fake_call
    try:
        # 1. the controls gate
        cases = [("no summary", None, None, None, False),
                 ("all_passed false", False, 0.997, 0.95, False),
                 ("all_passed string", "true", 0.997, 0.95, False),
                 ("no level_noedge", True, None, 0.95, False),
                 ("level_noedge out of range", True, 0.9, 0.95, False),
                 ("quick run", "quick", 0.997, 0.95, False),
                 ("passed", True, 0.99625, 0.955, True)]
        for name, ap, lv, l95, ok in cases:
            shutil.rmtree(tmp / "controls", ignore_errors=True)
            if ap is not None:
                _write(tmp, ap, lv, l95)
            st = controls_status(tmp)
            assert st["ok"] is ok, (name, st)
            calls.clear()
            if not ok:
                for stage in ("primary", "desc", "fit", "report"):
                    assert run_(stage) == 2 and calls == [], (name, stage, calls)
                assert run_("fit", "--only", "fcount") == 2 and calls == [], (name, calls)
        # 2. F's counts before any return: primary and desc refuse without them (or with a quick / F-less F.json)
        for bad in (None, "quick", "no F"):
            shutil.rmtree(tmp / "fcount", ignore_errors=True)
            if bad == "quick":
                _write_fcount(tmp, quick=True)
            elif bad == "no F":
                _write_fcount(tmp)
                (tmp / "fcount" / "F.json").write_text(json.dumps({"cells": 9}))
            assert not fcount_status(tmp)["ok"], bad
            calls.clear()
            assert run_("primary") == 2 and run_("desc") == 2 and calls == [], (bad, calls)
        shutil.rmtree(tmp / "fcount", ignore_errors=True)
        calls.clear()
        assert run_("fit") == 2 and run_("fit", "--only", "luck") == 2 and calls == []
        assert run_("fit", "--only", "fcount") == 0 and calls == [("bb_fit", ["fcount"])], calls
        assert fcount_status(tmp)["ok"]
        calls.clear()
        assert run_("primary") == 0 and calls == [("primary", 0.99625, 0.955)], calls
        assert run_("report") == 0 and calls[-1] == ("report", 0.99625, 0.955), calls
        calls.clear()
        assert run_("desc") == 0 and calls == [("bb_desc", None)], calls
        # 3. fit's H11b gate: every primary result written (all 12, none errored), whatever --only says
        partial = {"H1": {"test_id": "H1"}}
        errored = {t: ({"test_id": t, "error": "Traceback ..."} if t != "H1" else {"test_id": t}) for t in ALL}
        for name, J in (("only H1", partial), ("11 errored", errored), ("'{}'", None), ("unreadable", "x")):
            if J == "x":
                (tmp / "primary").mkdir(exist_ok=True)
                (tmp / "primary" / "tests.json").write_text("not json")
            else:
                _write_tests(tmp, J)
            assert not primary_status(tmp)["ok"], name
            calls.clear()
            for args in (("fit",), ("fit", "--only", "h11b"), ("fit", "--only", "luck,h12"), ("fit", "--only", "h11")):
                assert run_(*args) == 2 and calls == [], (name, args, calls)
            assert run_("fit", "--only", "fcount") == 0 and calls == [("bb_fit", ["fcount"])], (name, calls)
        _write_tests(tmp, ALL)
        assert primary_status(tmp)["ok"]
        calls.clear()
        assert run_("fit") == 0 and run_("fit", "--only", "h11b") == 0
        assert calls == [("bb_fit", None), ("bb_fit", ["h11b"])], calls
        shutil.rmtree(tmp / "fcount", ignore_errors=True)             # complete primary but no F counts on disk
        calls.clear()
        assert run_("fit", "--only", "luck") == 2 and calls == []
        assert run_("fit", "--only", "fcount,luck") == 0 and calls == [("bb_fit", ["fcount", "luck"])], calls
        # 4. all: failed controls stop everything; passed controls run F's counts first, report before desc
        for d in ("controls", "fcount", "primary"):
            shutil.rmtree(tmp / d, ignore_errors=True)
        (tmp / "verdicts.csv").unlink(missing_ok=True)
        calls.clear()
        fake_call.pass_controls = False
        assert run_("all") == 2 and calls == [("bb_controls", None)], calls
        calls.clear()
        fake_call.pass_controls = True
        rest = _fit_rest()
        assert rest and "fcount" not in rest and "h11b" in rest, rest
        assert run_("all") == 0
        want = [("bb_controls", None), ("bb_fit", ["fcount"]), ("primary", 0.997, 0.96), ("report", 0.997, 0.96),
                ("bb_desc", None), ("bb_fit", rest), ("report", 0.997, 0.96)]
        assert calls == want, calls
        assert seen["fcount_at_primary"] is True and seen["verdicts_at_desc"] is True
        if "f_cell_at_desc" in seen:
            assert seen["f_cell_at_desc"] is not None, seen
    finally:
        bb_tests.run, bb_tests.report = real_run, real_report
        globals()["_call_run"] = real_call
        shutil.rmtree(tmp, ignore_errors=True)
    # other agents' run() signatures: arguments by name; bb_controls' convention (quick, out = the controls dir,
    # workers, only); a run() without a results-directory parameter stops
    import types
    got = []
    fakes = {"_bb_replica_fake1": lambda out_dir, jobs=1: got.append(("f1", out_dir, jobs)),
             "_bb_replica_fake2": lambda quick=True, out=None, workers=1, only=None, tmp=None:
             got.append(("f2", quick, out, workers, only, tmp)),
             "_bb_replica_fake3": lambda quick=True, n=1: got.append(("f3",))}
    for nm, f in fakes.items():
        m = types.ModuleType(f"analysis_2026.{nm}")
        m.run = f
        sys.modules[f"analysis_2026.{nm}"] = m
    OUT_SUB["_bb_replica_fake2"] = "controls"
    try:
        _call_run("_bb_replica_fake1", "X", which=["a"], jobs=3)
        _call_run("_bb_replica_fake2", "X", which=["a"], jobs=3)
        assert got == [("f1", "X", 3), ("f2", False, str(Path("X") / "controls"), 3, ["a"], None)], got
        for bad in ("_bb_replica_fake3", "_bb_replica_missing_module"):
            try:
                _call_run(bad, "X")
                raise AssertionError(f"{bad} did not stop")
            except SystemExit:
                pass
    finally:
        OUT_SUB.pop("_bb_replica_fake2", None)
        for nm in fakes:
            del sys.modules[f"analysis_2026.{nm}"]
    # the real bb_controls, when present, is called with quick=False and out=<results>/controls; the real bb_fit's
    # F-count part is named as PRE_PRIMARY_FIT says
    if importlib.util.find_spec("analysis_2026.bb_controls") is not None:
        P = inspect.signature(importlib.import_module("analysis_2026.bb_controls").run).parameters
        assert next(n for n in OUT_NAMES if n in P) in ("out", "out_dir"), list(P)
    if importlib.util.find_spec("analysis_2026.bb_fit") is not None:
        assert set(PRE_PRIMARY_FIT) <= set(importlib.import_module("analysis_2026.bb_fit").PARTS)
    say("  bb_replica: primary / desc / fit / report refuse (exit 2, stage not called) without a passed summary.json or "
        "a usable level_noedge, and get the controls' levels; primary and desc refuse until F's counts are written; "
        "fit beyond F's counts refuses unless all 12 primary results are written (partial, errored, empty or "
        "unreadable tests.json refuse, whatever --only); all stops after failed controls, else runs controls -> "
        "fit[fcount] -> primary -> report -> desc (F readable, verdicts written) -> fit[rest] -> report")


def selftest() -> None:
    check_gate(print)
    print("bb_replica selftest: all passed")


# ============================================================================ CLI
def main(argv=None, say=print) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m analysis_2026.bb_replica", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=STAGES)
    ap.add_argument("--out", default=str(RES), help="results directory (default analysis_2026/results_bb)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", default=None, help="comma-separated subset passed as which= (e.g. H1,H6)")
    a = ap.parse_args(argv)
    only = [x.strip() for x in a.only.split(",") if x.strip()] if a.only else None
    out = Path(a.out)
    if a.stage == "selftest":
        selftest()
        return 0
    if a.stage == "controls":
        return cmd_controls(out, a.jobs, only, say=say)
    if a.stage == "primary":
        return cmd_primary(out, a.jobs, only, say=say)
    if a.stage == "desc":
        return cmd_desc(out, a.jobs, only, say=say)
    if a.stage == "fit":
        return cmd_fit(out, a.jobs, only, say=say)
    if a.stage == "report":
        return cmd_report(out, say=say)
    if a.stage == "status":
        return cmd_status(out, say=say)
    return cmd_all(out, a.jobs, say=say)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
