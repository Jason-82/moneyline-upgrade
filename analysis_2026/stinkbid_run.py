"""
Runner of the stink-bid study (analysis_2026/STINKBID_PREREG.md, FROZEN 2026-11-18, commit 72ac2a4): the run order of
§14 ("Each stage refuses to run until the one before it is complete"), §10.5 ("a failed control stops the study"),
§10.3 (H1 FLIP, H2R RESTING, H4 LEVELS with every gate; Holm; verdicts), §11 (the answer: verdicts first, the
recommendation table in order, the fixed sentences with their numbers, the descriptive sentences, the further rules)
and §12 (reporting rules). Descriptive estimands, sensitivity rows and exploratory splits (§10.4) are computed by
stinkbid_desc.py. Contract: research_notes/Stink bids/build_spec.md, "stinkbid_run.py and stinkbid_desc.py". Engine,
statistics, levels and data modules (stinkbid_engine, stinkbid_stats, stinkbid_levels, stinkbid_data) are used, never
edited; the controls (stinkbid_controls) and the sheet (stinkbid_sheet) are other agents' modules this runner calls.

    python3 -m analysis_2026.stinkbid_run status                      # which stages are complete (no result shown)
    python3 -m analysis_2026.stinkbid_run data      [--jobs 4]        # 1. data: base files, levels, prefetch
    python3 -m analysis_2026.stinkbid_run controls  [--jobs 4]        # 2. K1-K8 (stinkbid_controls) -> gate
    python3 -m analysis_2026.stinkbid_run fcount    [--jobs 4]        # 3. every program's fill counts, no outcome
    python3 -m analysis_2026.stinkbid_run primary   [--jobs 4]        # 4. H1, H2R, H4 with every gate
    python3 -m analysis_2026.stinkbid_run report                      # 5. Holm, verdicts, the answer (§11)
    python3 -m analysis_2026.stinkbid_run desc      [--jobs 4]        # 6. descriptive estimands, sensitivity rows
    python3 -m analysis_2026.stinkbid_run explore   [--jobs 4]        # 7. exploratory splits (BH within tables)
    python3 -m analysis_2026.stinkbid_run sheet     -- <sheet args>   # 8. the level sheet (stinkbid_sheet)
    python3 -m analysis_2026.stinkbid_run selftest                    # gating, answer map, synthetic end to end
  options: --out DIR      results (default analysis_2026/results_stinkbid; small tables only)
           --cache DIR    engine run cache (default data/stinkbid/runs; gitignored, large)
           --jobs N       engine processes (real data; default 4)
           --rerun        run a stage that is already complete: it and every later stage are invalidated, and the
                          rerun is logged in <out>/stages/deviations.jsonl (§12 "Deviations"); --reason TEXT says why
           --B N          bootstrap draws (default 9,999, §10.2; the selftest uses fewer)
           --ub-f3        also compute F3 (s = 1%) rows on U-B (coding choice 13: about 36 GB of 1m index history)

Stages, their gates and their outputs (OUT = --out, CACHE = --cache; markers in OUT/stages/<stage>.json)
  data      real: the base files (universes, 1m spot for U-Q1 u U-Q1-12 u U-A u U-C, M7 inputs, USDT/USD proxy,
            T-bill, 1d index) are checked and fetched where missing (stinkbid_data, resumable, checksum-verified);
            then, "once levels exist", every non-U-B program is run in counts-only mode on F1 (bids = levels; P1 on
            U-Q1 streams aggTrades for its fill windows into stinkbid_data's capacity cache, every other program uses
            C1: coding choice 15), V4's fetch rule
            (stinkbid_data.index_fetch_days) gives the candidate days, and the 1m index and perpetual months the fill
            stage reads for them are prefetched (fill_stage_months: every coin of the bid coin's chain, inside its own
            spot segments; stinkbid_data.fut_prefetch), plus HYPE's index months (§5) and the index months the
            outcome runs' F3 / F4 rows read (index_history_months: U-Q1, U-Q1-12, U-Q1-xm, U-A and U-C coins with a
            contract, their member months and the 12 after each, prereg Addendum 1 A1.6; a warning when the estimate
            exceeds the free disk less 4 GB). The fill and outcome stages refuse while a planned month is not cached
            (fut_months_missing), so they never download. U-B coins are streamed by the engine itself in later
            stages. Writes OUT/data/{coverage.json, candidate_days.csv, prefetch_index.csv, prefetch_perp.csv}.
            Injected data: the world is validated.
  controls  refuses until data is complete. Runs stinkbid_controls (a module-level run() given the controls
            directory, else its documented CLI `python3 -m analysis_2026.stinkbid_controls run --jobs N`) unless
            OUT/controls/summary.json exists, then validates it: all_passed must be a JSON boolean. Reads
            k3_calibration.json (the K3 rule), k1.json / summary.json (K1c's Delta90 for D-H2) and d11_null.parquet
            (D11, when the calibration lacks H1's null totals). The controls module writes to the default results
            directory; with another --out, place its outputs in OUT/controls. The stage completes either way; a
            false all_passed stops the study (every later stage refuses). The marker records all_passed, the gate
            and the sha256 of every file in OUT/controls; a later stage refuses when any of them changed (only
            `controls --rerun --reason ...`, logged as a deviation, opens the gate again).
  fcount    refuses until controls is complete with all_passed true, and while any outcome run exists in CACHE
            (fill counts are written before any outcome, §14). Every program of the plan (FCOUNT_RUNS) runs in
            counts-only mode under every fill rule (F1-F5; capacity; the K5 fill audit, whose violations stop the
            run). Writes OUT/fcount/{counts.csv, by_month.csv, p1_episodes.csv, status.csv, summary.json, fcount.txt}.
  primary   refuses until fcount is complete and covers every program, and unless the controls gate is open (coding
            choice 1: the controls marker's all_passed, its file hashes, and OUT/controls/summary.json with
            all_passed true and the K3 calibration: stinkbid_stats.inference_calibration's output, "tests" for H1,
            H2R and H4 and "null" draws for any test that needs calibration). Runs the outcome programs of
            ANSWER_RUNS (P1 on U-Q1 with every exit, rule and cost; P1 on U-B, the gate; H4 on U-Q1 with its
            placebos; P1 on U-C, the hindsight row beside every headline) and computes H1, H2R and H4 with every gate
            (§10.3), the rows reported beside them (F3d, F3 at s = 3%, U-B, U-C), the bot-latency version of H1, the
            F3-kept subsets ("a Binance-only result") and concentration / single events; K3's rule is applied
            (stinkbid_stats.apply_calibration). Writes OUT/primary/{primary.json, gates.csv, h4_methods.csv,
            samples_H1.csv, samples_H2R.csv}.
  report    refuses until primary is complete. Holm over the three p-values whatever the gates
            (stinkbid_stats.family_verdicts), the verdicts, and the answer of §11. Writes OUT/verdicts.txt (the
            answer as printed, then the details), OUT/verdicts.csv (one row per test, H2R, H1, H4) and
            OUT/answer.json (verdicts, recommendation keys and texts, sentences, numbers, flags for the sheet).
  desc      refuses until report is complete. Runs DESC_RUNS and writes every §10.4 descriptive estimand, table and
            sensitivity row (stinkbid_desc.compute_desc) to OUT/desc/ (CSV per table, desc.json, desc.txt).
  explore   refuses until desc is complete. Runs EXPLORE_RUNS (and, on real data, HYPE on its perpetual's index) and
            writes the exploratory splits (BH within each table) to OUT/explore/, then OUT/sheet_inputs.json (what
            the sheet needs to decide what is shown, §13).
  sheet     refuses until explore is complete and stinkbid_sheet exists; runs it with the given arguments and checks
            that it wrote OUT/sheet/sheet_YYYY-MM-DD.csv.
  status    prints each stage's state and the controls gate; never a result.

Programs (stinkbid_engine.PROGRAMS) and plans
  ANSWER_RUNS  P1/U_Q1 "full" (every rule, the default exit plan plus TH72 on F3_1 (coding choice 18), +-30-day /
               pooled twins, leave-out drift);
               P1/U_B "gate" (F1 with X-FLIP, X-FLIP-bot, X-HOLD-90; streamed; F3_1 X-FLIP only with --ub-f3);
               H4/U_Q1 "h4" (F1 and F3_1, X-FLIP); P1/U_C "sens"
  DESC_RUNS    P1 on U_Q1_12, U_Q1_xm, U_A; P1-1, P1-30, P1-90, P1-lazy, P1-G, P1-1330, P1-k5-12, M1, M2a, M3 on U-Q1
               ("sens": F1 with X-FLIP and X-HOLD-90, F3_1 with X-FLIP); H4-all/U_Q1 "h4all" (F1, F3_1, F4; X-FLIP)
  EXPLORE_RUNS M8/U_Q1 "sens"; HYPE on its index (real data)
  FCOUNT_RUNS  all of them, counts only, every rule

Coding choices the pre-registration leaves open (most literal reading; listed in the build report)
 1. Gating is by completion markers (OUT/stages/<stage>.json with the mode, real or injected:<label>); a stage
    refuses when the previous one is not complete in the same mode. Every stage after controls also checks the
    controls gate (controls_gate): the controls marker must record all_passed true and an open gate, every file of
    OUT/controls must still have the sha256 the controls stage recorded (summary.json, the K3 calibration, k1.json,
    d11_null.parquet, ...: a summary replaced after a failed or passed run, e.g. by the controls module's own CLI,
    does not reopen or change the gate), and OUT/controls/summary.json is re-validated: all_passed must be the JSON
    value true (and the run not quick / partial / valid_gate false, the BB runner's rule), because §10.5 stops the
    whole study on a failed control. A complete stage runs again only with --rerun, which invalidates it and every
    later stage (markers moved to OUT/stages/stale/; a fcount rerun also moves the outcome cache aside) and logs a
    deviation with --reason (§12).
 2. "fcount writes every program's fill counts before any outcome exists": fcount refuses while an outcome run
    exists in the cache, and primary refuses until fcount's counts cover every program of FCOUNT_RUNS.
 3. H1 sample: F1 fills with an X-FLIP (rule M) outcome at C-RH whose 72-hour horizon is observed; H2R: F1 fills
    with a finite a_f (alert_M: the alert buyer's open at M(fill) on spot, over L, minus 1; C-RH on both sides
    cancels); clusters = month-blocks of the sample's own fill times; E = 3.75%, 2%, 1% (stinkbid_stats.E).
    H1's gates: mean r_f > 0; mean Delta > 0 in each half, without the worst month-block (the one whose removal
    lowers it most), without the biggest episode (most fills), on U-B (P1 on U-B, the same statistic) and under F3
    (s = 1%: the F3_1 rows at the route's cost, RH). H2R's: the same without the r_f gate, with a_f. H4's: the
    argmax method's b > 0 in each half and without the worst month-block (on test_h4's partition) and under F3
    (h4_frames on F3_1, b of the argmax method on the F3 sample's own partition). A gate that cannot be evaluated
    (no fills) is not met.
 4. K3 (§10.5): a test whose calibration says needs_calibration gets the simulation-calibrated p and the widened
    bound (stinkbid_stats.apply_calibration), also for the bot-latency and F3-kept rows of the same test.
 5. "If it passes only at bot latency" (§11, H1 row): H1 under X-FLIP-bot (the same sample rules, gates and K3
    rule, U-B and F3 gates on their bot rows) with its p put in H1's place in the three-test Holm family; it
    "passes" when its verdict under the rule of every verdict is PASS (stinkbid_stats.verdict: Holm-adjusted
    p < 0.05, every bot gate holds, and its 98.33% upper bound is not below E; a bot version whose bound is below E
    is NO EDGE, prereg Addendum 1 A1.8). Then the H1 row of the rule-M verdict is printed with the bot sentence and
    no flip target.
 6. "A PASS that relies on events F3 removes is reported as 'a Binance-only result'": the test re-run on the F1
    fills that F3 (s = 1%) also fills (H4: the stacked fills whose own bid also filled under F3) has a p_decide not
    below the Holm level at which the test was rejected.
 7. "You could run it on Robinhood" (§11): H1 or H2R PASSes, the D7 flip account on F3 (s = 1%, r_res = 0) beats
    B-MIX (CAGR difference, 12-month block bootstrap, 95% interval above zero), and a passing test's statistic is
    > 0 on the U-C row (P1 run on U-C, hindsight) under F3.
 8. V4 (adopted): if H1's mean Delta under F3 and under F3d (s = 1%) differ in sign, H1's sentence adds "only on
    brief index dips".
 9. S16: when the three largest episodes give more than half of a headline's total, its verdict line names them
    (the PASS sentence of S9; a neutral sentence otherwise).
10. Fixed sentences are printed verbatim with their computed numbers: the worst day's share S of live P1 bids that
    filled (U-Q1, F1), A and B the 365-day knife shares of fills and their twins, the MoneyLine split (the share
    red at placement printed beside the fixed sentence), the size cap per rung (Q_max = 0.25 x the 10th percentile
    of past seller dollars below the level). The descriptive sentences (D-H2, D-H3, D-H5, D8) come from
    stinkbid_desc with their estimates; their fixed "about 20-40%" / "6-10%" ranges stay and the computed MDE is
    printed beside them.
11. The sheet's chart-level rule (§13): a method is listed as earned only when H4 PASSed and its Romano-Wolf
    adjusted p is below the Holm level at which H4 was rejected (or it passes D10's family, written by desc).
12. Large engine outputs (bids, fills, outcomes, benchmarks, capacity curves) are cached as parquet under CACHE
    (gitignored), keyed by a signature of (program, universe, plan, mode, engine / levels / data source hashes);
    OUT holds only tables. Injected worlds run single-process (the engine would pickle the whole world).
13. U-B's outcome run is F1-only by default. Its pre-registered uses (the H1 / H2R gate "Delta > 0 / a > 0 on U-B",
    D-H5's population, T1's U-B row, the U-B sensitivity row) are F1 statistics; an F3 row would make the engine read
    the 1m index of every U-B coin with a fill (an estimate made when it read whole histories: about 20,600
    coin-months or 36 GB, against about 18 GB free on this machine). §12's "every Binance number beside its F3
    number" is therefore not met for the U-B rows unless --ub-f3 is passed; those F3 rows are labelled "F3 not
    computed for this run" (prereg Addendum 1, A1.7). The fill and outcome stages read only months the data stage
    prefetched (fut_months_missing; stinkbid_engine coding choices 14 and 27).
14. D12 is printed in verdicts.txt's details before the verdict table (§10.4: "Reported before H1's table"); the
    answer itself (verdicts and sentences) comes first, before any table (§11).
15. aggTrades capacity (§4 "aggTrades, streamed for every U-Q1 coin-day with a fill (for capacity)"; §7 "The 1-minute
    approximation C1 is used where aggTrades are not streamed"): every pre-registered capacity number is P1's on
    U-Q1 (D4, D7 and D7-OWN sizing, the Q / theta size rows, the bad-print filter, the size cap of §11 and the
    sheet's column 5), so only P1 on U-Q1 runs with capacity 'auto' (aggTrades on real U-Q1, one zip per coin-day
    of its fill windows, cached by window); every other program and universe runs with capacity 'c1' (their
    per-fill returns do not use capacity, §6.3). stinkbid_data.agg_capacity caches by (L, start, end), so a
    program with its own levels would download the same crash days again. K6's aggTrades sample is the controls
    module's.
16. H1's E sensitivity (§10.3: "2.26% (r_res = 3.35%) is a sensitivity"): H1's verdict re-mapped with E =
    stinkbid_stats.E_SENS["H1_gold"] (the same Holm p, gates and 98.33% bound; NO EDGE precedes PASS, Addendum 1
    A1.8), printed in verdicts.txt and written to verdicts.csv (e_sens, verdict_e_sens) and answer.json
    ("sensitivity"). It never changes the primary verdict.
17. HYPE (§5, §6.1 "futures-based inputs (..., HYPE's index) use data through Saturday (d0 - 1)"): the HYPE world
    trades on the 1m index, but its level inputs (P0, sigma30, ATR14) read daily index bars lagged one day, so a
    Monday 03:30 placement sees the index only through Saturday's close (V6: Sunday's index file is published after
    the placement).
18. The "full" plan of P1 on U-Q1 adds TH72 to F3_1's exits (the engine's default plan has it on F1 only), so D6's
    theta_k and mu*_k and D8's part 2 have their Robinhood-route proxy numbers beside the Binance ones (§12; §7 "The
    sheet's numbers come from F3": the sheet's trade-off column shows theta_k and mu*_k). The twins' seeds do not
    depend on the exits a run evaluates (stinkbid_engine coding choice 16), so no other number changes.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import importlib.util
import inspect
import io
import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import stinkbid_stats as sbs  # noqa: E402
from analysis_2026 import stinkbid_desc as sbdesc  # noqa: E402

RES = ROOT / "analysis_2026" / "results_stinkbid"
CACHE = ROOT / "data" / "stinkbid" / "runs"
SCRATCH = Path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/sb_runner")
STAGES = ("data", "controls", "fcount", "primary", "report", "desc", "explore", "sheet")
PREV = {s: STAGES[i - 1] for i, s in enumerate(STAGES) if i}
FAMILY = sbs.FAMILY                                  # ("H1", "H2R", "H4")
ORDER = sbs.REPORT_ORDER                             # ("H2R", "H1", "H4"), §11
E = sbs.E                                            # {"H1": 0.0375, "H2R": 0.02, "H4": 0.01}
NAN = float("nan")

ANSWER_RUNS = (("P1", "U_Q1", "full"), ("P1", "U_B", "gate"), ("H4", "U_Q1", "h4"), ("P1", "U_C", "sens"))
DESC_RUNS = (("P1", "U_Q1_12", "sens"), ("P1", "U_Q1_xm", "sens"), ("P1", "U_A", "sens"),
             ("P1-1", "U_Q1", "sens"), ("P1-30", "U_Q1", "sens"), ("P1-90", "U_Q1", "sens"),
             ("P1-lazy", "U_Q1", "sens"), ("P1-G", "U_Q1", "sens"), ("P1-1330", "U_Q1", "sens"),
             ("P1-k5-12", "U_Q1", "sens"), ("M1", "U_Q1", "sens"), ("M2a", "U_Q1", "sens"), ("M3", "U_Q1", "sens"),
             ("H4-all", "U_Q1", "h4all"))
EXPLORE_RUNS = (("M8", "U_Q1", "sens"),)
FCOUNT_RUNS = ANSWER_RUNS + DESC_RUNS + EXPLORE_RUNS
AGG_RUNS = (("P1", "U_Q1"),)          # the runs whose capacity is reported; aggTrades only for these (choice 15)
SOURCES = ("stinkbid_engine.py", "stinkbid_levels.py", "stinkbid_data.py")


# ============================================================================ context, markers, logs
class StageRefused(RuntimeError):
    """A stage's gate is not met (§14, §10.5): nothing was run."""


@dataclass
class Ctx:
    out: Path = RES
    cache: Path = CACHE
    data: dict | None = None                       # None: real data; else an injected world (stinkbid_engine.World)
    label: str = ""
    n_jobs: int = 4
    B: int = sbs.B_BOOT
    verbose: bool = True
    rerun: bool = False
    reason: str = ""
    sheet_args: list = field(default_factory=list)
    controls_fn: object = None                     # injected controls runner (selftest); None: stinkbid_controls
    ub_f3: bool = False                            # F3 rows on U-B (whole index histories of ~430 coins; choice 13)

    @property
    def injected(self) -> bool:
        return self.data is not None

    @property
    def mode(self) -> str:
        return f"injected:{self.label or 'synthetic'}" if self.injected else "real"

    def log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)


def _now() -> str:
    return pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M:%S UTC")


def _jdump(path: Path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(sbdesc._jsonable(obj), indent=1, default=str))
    os.replace(tmp, path)


def _jload(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def _append_log(ctx: Ctx, name: str, rec: dict):
    f = ctx.out / "stages" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as fh:
        fh.write(json.dumps(sbdesc._jsonable(dict(time=_now(), mode=ctx.mode, **rec)), default=str) + "\n")


def marker_path(ctx: Ctx, stage: str) -> Path:
    return ctx.out / "stages" / f"{stage}.json"


def read_marker(ctx: Ctx, stage: str) -> dict | None:
    return _jload(marker_path(ctx, stage))


def stage_complete(ctx: Ctx, stage: str) -> bool:
    m = read_marker(ctx, stage)
    return bool(isinstance(m, dict) and m.get("complete") is True and m.get("mode") == ctx.mode)


def write_marker(ctx: Ctx, stage: str, t0: float, info: dict):
    _jdump(marker_path(ctx, stage), dict(stage=stage, complete=True, mode=ctx.mode, started=info.pop("started", ""),
                                         finished=_now(), seconds=round(time.time() - t0, 1), **info))
    _append_log(ctx, "log.jsonl", dict(event="complete", stage=stage))


def invalidate(ctx: Ctx, stages: list, reason: str):
    """Move the markers of `stages` to OUT/stages/stale/ and log the deviation (§12)."""
    stale = ctx.out / "stages" / "stale"
    stale.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
    moved = []
    for s in stages:
        f = marker_path(ctx, s)
        if f.exists():
            os.replace(f, stale / f"{s}.{stamp}.json")
            moved.append(s)
    _append_log(ctx, "deviations.jsonl", dict(event="rerun", stages=moved, reason=reason or "(no reason given)"))
    return moved


def deviations(ctx: Ctx) -> list:
    f = ctx.out / "stages" / "deviations.jsonl"
    if not f.exists():
        return []
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()]


# ============================================================================ the controls gate
def _find_calibration(S: dict, cdir: Path):
    """The K3 calibration (stinkbid_stats.inference_calibration's output: a dict with "tests" and, for calibrated
    tests, "null") from summary.json (K3 / k3 / calibration keys) or a k3*.json / *calib*.json file in the
    controls directory."""
    def ok(x):
        return isinstance(x, dict) and isinstance(x.get("tests"), dict)
    cands = []
    for k in ("K3", "k3"):
        v = S.get(k)
        if isinstance(v, dict):
            cands += [v.get("calibration"), v.get("calib"), v]
    cands += [S.get("calibration"), S.get("k3_calibration"), S.get("K3_calibration")]
    for c in cands:
        if ok(c):
            return c
    for pat in ("k3_calibration.json", "K3_calibration.json", "k3.json", "K3.json", "calibration.json", "*k3*.json",
                "*K3*.json", "*calib*.json"):
        for f in sorted(cdir.glob(pat)):
            v = _jload(f)
            if ok(v):
                return v
            if isinstance(v, dict):
                for k in ("calibration", "calib", "K3", "k3"):
                    if ok(v.get(k)):
                        return v[k]
    return None


def controls_status(ctx: Ctx) -> dict:
    """{"ok", "why", "summary", "calib"} from OUT/controls/summary.json (coding choice 1)."""
    out = dict(ok=False, why="", summary=None, calib=None)
    f = ctx.out / "controls" / "summary.json"
    if not f.exists():
        out["why"] = f"{f} not found: run the controls stage first (§10.5: controls run before any outcome)"
        return out
    S = _jload(f)
    if not isinstance(S, dict):
        out["why"] = f"{f} is unreadable"
        return out
    out["summary"] = S
    if S.get("all_passed") is not True:
        failed = [k for k, v in S.items() if isinstance(v, dict) and v.get("passed") is False]
        out["why"] = (f"{f}: all_passed is {S.get('all_passed')!r}, not true: a failed control stops the study (§10.5)"
                      + (f"; failed: {failed}" if failed else ""))
        return out
    if S.get("quick") is True or S.get("partial") is True or S.get("valid_gate") is False:
        out["why"] = f"{f}: a quick or partial controls run cannot open the gate"
        return out
    C = _find_calibration(S, f.parent)
    if C is None:
        out["why"] = (f"{f}: the K3 calibration (inference_calibration output with 'tests') was not found in "
                      "summary.json or controls/k3*.json")
        return out
    miss = [t for t in FAMILY if t not in C["tests"]]
    if miss:
        out["why"] = f"K3 calibration has no result for {miss} (§10.5: K3 reports H1, H2R and H4)"
        return out
    need = [t for t in FAMILY if C["tests"][t].get("needs_calibration")]
    lack = [t for t in need if not (C.get("null", {}).get(t))]
    if lack:
        out["why"] = f"K3 says {lack} need the simulation-calibrated rule but the calibration has no null draws"
        return out
    out.update(ok=True, why="every control passed", calib=C, calibrated_tests=need)
    return out


def controls_manifest(ctx: Ctx) -> dict:
    """{relative path: sha256} of every file under OUT/controls (temporary *.tmp files left out)."""
    d = ctx.out / "controls"
    out = {}
    if not d.exists():
        return out
    for p in sorted(d.rglob("*")):
        if p.is_file() and not p.name.endswith(".tmp"):
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            out[str(p.relative_to(d))] = h.hexdigest()
    return out


RERUN_CONTROLS = ("run 'python3 -m analysis_2026.stinkbid_run controls --rerun --reason TEXT' (logged as a deviation, "
                  "§12)")


def controls_gate(ctx: Ctx) -> dict:
    """The §10.5 gate of every stage after controls (coding choice 1): the controls marker records all_passed true
    and an open gate, every file of OUT/controls still has the sha256 the controls stage recorded, and the current
    summary.json still passes controls_status. {"ok", "why"} (plus controls_status's keys when ok)."""
    m = read_marker(ctx, "controls")
    if not (isinstance(m, dict) and m.get("complete") is True and m.get("mode") == ctx.mode):
        return dict(ok=False, why="the controls stage is not complete")
    if m.get("all_passed") is not True:
        return dict(ok=False, why=f"the controls stage recorded all_passed = {m.get('all_passed')!r}: a failed "
                                  f"control stops the study (§10.5); after a fix, {RERUN_CONTROLS}")
    if m.get("gate_ok") is not True:
        return dict(ok=False, why=f"the controls stage recorded a closed gate ({m.get('why')}); after a fix, "
                                  f"{RERUN_CONTROLS}")
    man = m.get("manifest")
    if not isinstance(man, dict) or not man:
        return dict(ok=False, why=f"the controls marker records no file hashes; {RERUN_CONTROLS}")
    cur = controls_manifest(ctx)
    changed = sorted(k for k in set(man) | set(cur) if man.get(k) != cur.get(k))
    if changed:
        return dict(ok=False, why=f"the controls outputs changed after the controls stage validated them ({changed[:6]}"
                                  f"{' ...' if len(changed) > 6 else ''}); the gate stays as recorded until you "
                                  f"{RERUN_CONTROLS}")
    cs = controls_status(ctx)
    if not cs["ok"]:
        return dict(ok=False, why=cs["why"])
    return dict(cs, ok=True, why="every control passed; the controls outputs are unchanged since the controls stage")


# ============================================================================ engine runs and their cache
def _engine():
    from analysis_2026 import stinkbid_engine as sbe
    return sbe


def _src_hash() -> str:
    h = hashlib.sha256()
    for f in SOURCES:
        p = ROOT / "analysis_2026" / f
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def capacity_mode(prog: str | None, universe: str) -> str:
    """The engine's capacity mode for a run (coding choice 15): 'auto' (aggTrades on real U-Q1, C1 on injected
    worlds) only for the runs whose capacity is reported (AGG_RUNS: P1 on U-Q1), 'c1' for every other run."""
    return "auto" if (prog, universe) in AGG_RUNS else "c1"


def plan_cfg(plan: str, universe: str, ctx: Ctx, counts_only: bool = False, rules=None,
             prog: str | None = None) -> dict:
    """The engine cfg of a plan (see the module docstring); prog decides the capacity mode (coding choice 15)."""
    sbe = _engine()
    if counts_only:
        cfg = dict(counts_only=True, rules=tuple(rules or sbe.RULES_ALL))
    elif plan == "full":
        ex = dict(sbe.default_exits(sbe.DEFAULT_CFG["rules"]))
        if sbe.THETA not in ex["F3_1"]:
            ex["F3_1"] = tuple(ex["F3_1"]) + (sbe.THETA,)       # D6 / D8 on the Robinhood-route proxy (choice 18)
        cfg = dict(exits=ex)
    elif plan == "gate":
        ex = {"F1": (sbe.FLIP, sbe.FLIP_BOT, sbe.EXIT_SPECS["HOLD90"])}
        if ctx.ub_f3:
            ex["F3_1"] = (sbe.FLIP,)
        cfg = dict(rules=tuple(ex), exits=ex, twin_sens=False, drift=False)
    elif plan == "h4":
        cfg = dict(rules=("F1", "F3_1"), exits={"F1": (sbe.FLIP,), "F3_1": (sbe.FLIP,)}, twin_sens=False,
                   drift=False)
    elif plan == "h4all":
        cfg = dict(rules=("F1", "F3_1", "F4"), exits={"F1": (sbe.FLIP,), "F3_1": (sbe.FLIP,), "F4": (sbe.FLIP,)},
                   twin_sens=False, drift=False)
    elif plan == "sens":
        cfg = dict(rules=("F1", "F3_1"), exits={"F1": (sbe.FLIP, sbe.EXIT_SPECS["HOLD90"]), "F3_1": (sbe.FLIP,)},
                   twin_sens=False, drift=False)
    else:
        raise ValueError(f"unknown plan {plan!r}")
    cfg["capacity"] = capacity_mode(prog, universe)
    cfg["stream"] = bool(universe == "U_B" and not ctx.injected)
    cfg["n_jobs"] = 1 if ctx.injected else int(ctx.n_jobs)
    cfg["verbose"] = bool(ctx.verbose)
    return cfg


def _cfg_key(cfg: dict) -> dict:
    """The parts of an engine cfg that change its results (for the run cache's signature)."""
    ex = cfg.get("exits")
    return dict(rules=list(cfg.get("rules") or []), capacity=cfg.get("capacity"), stream=cfg.get("stream"),
                twin_sens=cfg.get("twin_sens"), drift=cfg.get("drift"),
                exits={r: [e.name for e in v] for r, v in sorted(ex.items())} if isinstance(ex, dict) else None)


def _sig(prog, univ, plan, counts_only, ctx: Ctx, rules=None, cfg: dict | None = None) -> str:
    return json.dumps(dict(program=prog, universe=univ, plan=plan, counts_only=counts_only, mode=ctx.mode,
                           rules=list(rules) if rules else None, src=_src_hash(),
                           ub_f3=bool(ctx.ub_f3 and plan == "gate"), cfg=_cfg_key(cfg) if cfg else None),
                      sort_keys=True)


def run_dir(ctx: Ctx, prog: str, univ: str, counts_only: bool, tag: str = "") -> Path:
    return ctx.cache / ("fcount" if counts_only else "outcomes") / f"{prog}__{univ}{tag}"


def _parquet_safe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            vals = df[c].dropna()
            if len(vals) and all(isinstance(v, (bool, np.bool_)) for v in vals):
                df[c] = df[c].astype(float)
            elif len(vals) and all(isinstance(v, (int, float, np.integer, np.floating)) for v in vals):
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = df[c].map(lambda v: v if (v is None or isinstance(v, str)) else str(v))
    return df


def save_run(path: Path, res: dict, sig: str):
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    for k, v in res.items():
        if isinstance(v, pd.DataFrame):
            _parquet_safe(v).to_parquet(path / f"{k}.parquet", compression="zstd")
    meta = dict(res.get("meta") or {})
    meta.pop("cfg", None)
    _jdump(path / "meta.json", dict(program=res.get("program"), universe=res.get("universe"), meta=meta))
    _jdump(path / "done.json", dict(sig=sig, saved=_now()))


def load_run(path: Path) -> dict:
    path = Path(path)
    res = {}
    for f in path.glob("*.parquet"):
        res[f.stem] = pd.read_parquet(f)
    m = _jload(path / "meta.json", {})
    res.update(program=m.get("program"), universe=m.get("universe"), meta=m.get("meta", {}))
    for k in ("bids", "fills", "outcomes", "bench", "audit", "bid_status", "cap_curve"):
        res.setdefault(k, pd.DataFrame())
    return res


def _members(ctx: Ctx) -> dict:
    """{universe column: {coin: set(month ints since 1970-01)}} from the universes table."""
    sbe = _engine()
    if not hasattr(ctx, "_members_cache"):
        u = sbe.World(ctx.data).universe()
        cols = [c for c in u.columns if c.startswith("U_")]
        mi = u["month"].astype(str).str[:7].map(lambda m: (int(m[:4]) - 1970) * 12 + int(m[5:7]) - 1).to_numpy()
        out = {}
        for c in cols:
            sel = u[c].astype(bool).to_numpy()
            d = {}
            for coin, m in zip(u["coin"].to_numpy()[sel], mi[sel]):
                d.setdefault(coin, set()).add(int(m))
            out[c] = d
        ctx._members_cache = out
    return ctx._members_cache


def add_membership(ctx: Ctx, res: dict) -> dict:
    """Flags in_<universe> on the fills (placement month), for D-H5 (U-Q1-12), D3/D4 (U-C) and the rows."""
    F = res.get("fills")
    if F is None or not len(F) or "month" not in F:
        return res
    for U, d in _members(ctx).items():
        col = f"in_{U}"
        if col in F and U == "U_Q1":
            continue
        F[col] = [int(m) in d.get(c, ()) for c, m in zip(F["coin"].to_numpy(), F["month"].to_numpy())]
    return res


def universe_available(ctx: Ctx, univ: str) -> bool:
    return univ in _members(ctx)


def run_engine(ctx: Ctx, prog: str, univ: str, plan: str, counts_only: bool = False, rules=None,
               reuse: bool = True) -> dict | None:
    """Run (or reload from the cache) one engine program; None when the universe is not in the universes table."""
    if not universe_available(ctx, univ):
        ctx.log(f"  {prog}/{univ}: universe column {univ} not available; skipped")
        return None
    path = run_dir(ctx, prog, univ, counts_only, "_" + "-".join(rules) if rules else "")
    cfg = plan_cfg(plan, univ, ctx, counts_only, rules, prog=prog)
    sig = _sig(prog, univ, plan, counts_only, ctx, rules, cfg)
    done = _jload(path / "done.json")
    if reuse and isinstance(done, dict) and done.get("sig") == sig:
        ctx.log(f"  {prog}/{univ} ({'counts' if counts_only else plan}): reloaded from {path}")
        return load_run(path)
    sbe = _engine()
    t = time.time()
    ctx.log(f"  {prog}/{univ} ({'counts only' if counts_only else plan}) ...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        res = sbe.run_program(prog, univ, data=ctx.data, cfg=cfg)
    add_membership(ctx, res)
    save_run(path, res, sig)
    ctx.log(f"  {prog}/{univ}: done in {time.time() - t:.0f}s -> {path}")
    return res


def outcome_runs_exist(ctx: Ctx) -> list:
    d = ctx.cache / "outcomes"
    return sorted(p.name for p in d.glob("*") if (p / "done.json").exists()) if d.exists() else []


def runs_for(ctx: Ctx, plans) -> dict:
    out = {}
    for prog, univ, plan in plans:
        out[f"{prog}/{univ}"] = run_engine(ctx, prog, univ, plan)
    return out


def tbill_at_fn(ctx: Ctx):
    """T-bill yield (a fraction a year) at given minutes: stinkbid_data.tbill_daily on real data (through the
    engine's World), the injected world's value otherwise."""
    sbe = _engine()
    w = sbe.World(ctx.data)

    def f(minutes):
        m = np.asarray(minutes, np.int64)
        if not len(m):
            return np.zeros(0)
        days = pd.DatetimeIndex(sbdesc.ts_min((m // 1440) * 1440)).tz_localize(None)
        return np.asarray(w.tbill(days), float) / 100.0
    return f


# ============================================================================ stage plumbing
def _begin(ctx: Ctx, stage: str) -> float:
    """The §14 gate of a stage (coding choice 1). Returns the start time."""
    prev = PREV.get(stage)
    if prev and not stage_complete(ctx, prev):
        m = read_marker(ctx, prev)
        why = "has not run" if m is None else (f"ran in mode {m.get('mode')!r}, not {ctx.mode!r}"
                                               if m.get("mode") != ctx.mode else "is not complete")
        raise StageRefused(f"{stage} refuses: the previous stage '{prev}' {why} (§14: each stage refuses to run "
                           "until the one before it is complete)")
    if stage not in ("data", "controls"):
        cg = controls_gate(ctx)
        if not cg["ok"]:
            raise StageRefused(f"{stage} refuses: {cg['why']}")
    if stage in ("fcount", "primary", "desc", "explore") and not ctx.injected:
        mf = fut_months_missing(ctx)                      # the engine stages never download (coding choice 13)
        n = sum(len(v) for v in mf.values())
        if n:
            ex = "; ".join(f"{k}: {v[:3]}" for k, v in mf.items() if v)
            raise StageRefused(f"{stage} refuses: {n} futures months the data stage planned are not cached ({ex} "
                               "...); run the data stage again (--rerun) so that no later stage downloads")
    i = STAGES.index(stage)
    later = [s for s in STAGES[i + 1:] if read_marker(ctx, s) is not None]
    this = read_marker(ctx, stage) is not None
    if this or later:
        if not ctx.rerun:
            also = " and so have " + ", ".join(later) if later else ""
            raise StageRefused(f"{stage} refuses: it has already run{also}"
                               "; pass --rerun (logged as a deviation, with --reason) to run it again")
        moved = invalidate(ctx, [stage] + later, ctx.reason)
        ctx.log(f"  --rerun: invalidated {moved} (logged in {ctx.out / 'stages' / 'deviations.jsonl'})")
        if stage == "fcount" and outcome_runs_exist(ctx):
            stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
            os.replace(ctx.cache / "outcomes", ctx.cache / f"outcomes_stale_{stamp}")
    if stage == "fcount":
        ex = outcome_runs_exist(ctx)
        if ex:
            raise StageRefused(f"fcount refuses: outcome runs already exist in {ctx.cache / 'outcomes'} ({ex[:4]}...); "
                               "§14 writes the fill counts before any outcome")
    if stage == "primary":
        fs = fcount_status(ctx)
        if not fs["ok"]:
            raise StageRefused(f"primary refuses: {fs['why']}")
    _append_log(ctx, "log.jsonl", dict(event="start", stage=stage))
    return time.time()


def fcount_status(ctx: Ctx) -> dict:
    f = ctx.out / "fcount" / "counts.csv"
    if not stage_complete(ctx, "fcount") or not f.exists():
        return dict(ok=False, why=f"{f} is missing: fill counts come before any outcome (§14)")
    c = pd.read_csv(f)
    have = set(zip(c["program"], c["universe"]))
    need = [(p, u) for p, u, _ in FCOUNT_RUNS if universe_available(ctx, u)]
    miss = [x for x in need if x not in have]
    if miss:
        return dict(ok=False, why=f"fill counts are missing for {miss}")
    return dict(ok=True, why="")


# ============================================================================ 1. data
def stage_data(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "data")
    started = _now()
    d = ctx.out / "data"
    d.mkdir(parents=True, exist_ok=True)
    info = dict(started=started)
    if ctx.injected:
        W = ctx.data
        u = W.get("universe")
        if u is None or "U_Q1" not in u or "U_B" not in u:
            raise StageRefused("data refuses: the injected world needs a universe table with U_Q1 and U_B")
        coins = W.get("coins", {})
        cov = dict(mode=ctx.mode, coins=len(coins) if not callable(coins) else None,
                   universe_columns=[c for c in u.columns if c.startswith("U_")], months=int(u["month"].nunique()),
                   end=W.get("end"))
        _jdump(d / "coverage.json", cov)
        info.update(outputs=[str(d / "coverage.json")], coverage=cov)
        write_marker(ctx, "data", t0, info)
        ctx.log(f"data (injected): world validated -> {d}")
        return info
    from analysis_2026 import stinkbid_data as sbd
    sbe = _engine()
    steps = []
    if not (sbd.OUT / "ref" / "universes.parquet").exists():
        sbd.build_universes()
        steps.append("universes")
    coins = sbd._m1_coins()
    miss = [c for c in coins if not (sbd.OUT / "m1_spot" / f"{sbd.coin_sym(c)[0]}.parquet").exists()]
    if miss:
        sbd.m1_bulk(miss, False, max(1, ctx.n_jobs))
        steps.append(f"m1 ({len(miss)} coins)")
    for what, sub in (("metrics", "metrics"), ("mark", "mark1h"), ("perp1h", "perp1h")):
        if not any((sbd.OUT / sub).glob("*.parquet")):
            sbd.m7_bulk(what)
            steps.append(what)
    sbd.usd_fetch(False)
    sbd.tbill_fetch(False)
    sbd.index1d_bulk(None)
    steps += ["usd", "tbill", "index1d"]
    # levels -> bids (counts only, F1; P1 on U-Q1 streams aggTrades for its fill windows, every other program uses
    # C1: coding choice 15), V4's candidate days
    bids = []
    for prog, univ, plan in FCOUNT_RUNS:
        if univ == "U_B":
            continue
        cfg = plan_cfg(plan, univ, ctx, counts_only=True, rules=("F1",), prog=prog)
        res = sbe.run_program(prog, univ, cfg=cfg)
        b = res["bids"]
        if len(b):
            bids.append(pd.DataFrame({"coin": b.coin, "L": b.L, "live_from": sbdesc.ts_min(b.live_from),
                                      "live_to": sbdesc.ts_min(b.life_end - 1)}))
        ctx.log(f"  data: {prog}/{univ} levels for {len(b):,} bids")
    allb = pd.concat(bids, ignore_index=True).drop_duplicates() if bids else pd.DataFrame(
        columns=["coin", "L", "live_from", "live_to"])
    # the outcome runs' F3 / F4 rows read each coin's 1m index for its member months and the 12 after each
    # (stinkbid_engine coding choice 27, prereg Addendum 1 A1.6): prefetch exactly those months, after a disk estimate
    hist = index_history_months(ctx)
    est_gb = len(hist) * 1.8 / 1024
    free_gb = shutil.disk_usage(sbd.OUT).free / 1e9
    if est_gb > free_gb - 4:
        ctx.log(f"  WARNING: the index history the outcome runs read is estimated at up to {est_gb:.1f} GB "
                f"({len(hist):,} coin-months, an upper bound) against {free_gb:.1f} GB free")
    ph_full = sbd.fut_prefetch("index", hist)
    cand = sbd.index_fetch_days(allb) if len(allb) else pd.DataFrame(columns=["coin", "day"])
    cand.to_csv(d / "candidate_days.csv", index=False)
    cd = fill_stage_months(cand)
    pi = sbd.fut_prefetch("index", cd)
    pp = sbd.fut_prefetch("perp", cd)
    hype = [("HYPE", m) for m in pd.period_range("2025-05", sbd.END[:7], freq="M").strftime("%Y-%m")]
    ph = sbd.fut_prefetch("index", hype)
    pd.concat([pi, ph, ph_full], ignore_index=True).to_csv(d / "prefetch_index.csv", index=False)
    pp.to_csv(d / "prefetch_perp.csv", index=False)
    agg_days = sum(1 for _ in (sbd.OUT / "agg_cap").rglob("*.json")) if (sbd.OUT / "agg_cap").exists() else 0
    cov = dict(mode=ctx.mode, steps=steps, m1_coins=len(coins), bids=int(len(allb)), candidate_days=int(len(cand)),
               index_months=int(len(pi)), perp_months=int(len(pp)), hype_index_months=int(len(ph)),
               index_history_months=int(len(hist)), index_history_estimate_gb=round(est_gb, 1),
               free_disk_gb_before=round(free_gb, 1), agg_coin_days_cached=agg_days, ub_f3=bool(ctx.ub_f3),
               aggtrades_runs=[f"{p}/{u}" for p, u in AGG_RUNS])
    _jdump(d / "coverage.json", cov)
    info.update(outputs=[str(d / f) for f in ("coverage.json", "candidate_days.csv", "prefetch_index.csv",
                                              "prefetch_perp.csv")], coverage=cov)
    write_marker(ctx, "data", t0, info)
    ctx.log(f"data: base files checked, {len(cand):,} candidate index days prefetched -> {d}")
    return info


def _chain(coin: str) -> list:
    """The coin and its successors, in order: the spot chain a position follows (stinkbid_engine.build_spot)."""
    from analysis_2026 import stinkbid_data as sbd
    lin, x = [coin], coin
    while sbd.successor(x):
        x = sbd.successor(x)[0]
        if x in lin:
            break
        lin.append(x)
    return lin


def _span_months(seg: pd.DataFrame, coin: str) -> set:
    """'YYYY-MM' months of a coin's own spot segments (first day of its first segment, from the 1m cache's start, to
    the last day of its last): the months stinkbid_engine.build_index reads a chain coin for (coding choice 27)."""
    from analysis_2026 import stinkbid_data as sbd
    sg = seg[seg["coin"] == coin]
    if not len(sg):
        return set()
    a, b = pd.Timestamp(sg["first_day"].min()), pd.Timestamp(sg["last_day"].max())
    a = max(a, pd.Timestamp(sbd.M1_FROM + "-01"))                         # the engine's spot series is the 1m cache
    if a > b:
        return set()
    return set(pd.period_range(a, b, freq="M").strftime("%Y-%m"))


def _chain_months(seg: pd.DataFrame, coin: str, months, spans: dict) -> set:
    """(chain coin, month) the engine requests when it builds a coin's index or perpetual series for `months`: every
    coin of the chain with a USD-M contract, for the months inside its own spot segments, up to END's month. Months
    before a contract's first index day are included: the engine asks for them, and the data stage records them as
    empty months, so no later stage downloads."""
    from analysis_2026 import stinkbid_data as sbd
    out = set()
    end_m = sbd.END[:7]
    for x in _chain(coin):
        if sbd.um_contract(x) is None:
            continue
        if x not in spans:
            spans[x] = _span_months(seg, x)
        for m in months:
            if m in spans[x] and m <= end_m:
                out.add((x, m))
    return out


def fill_stage_months(cand: pd.DataFrame) -> list:
    """(coin, 'YYYY-MM') the fill stage (pass 1, counts and outcome runs alike) reads: the months of V4's candidate
    days (stinkbid_data.index_fetch_days, for the bid's coin) for every coin of the bid coin's chain, inside each
    chain coin's own spot segments (_chain_months)."""
    from analysis_2026 import stinkbid_data as sbd
    if not len(cand):
        return []
    seg = pd.read_csv(sbd.OUT / "ref" / "segments.csv")
    by = pd.DataFrame({"coin": cand["coin"].astype(str),
                       "m": pd.to_datetime(cand["day"]).dt.strftime("%Y-%m")}).drop_duplicates()
    out, spans = set(), {}
    for c, g in by.groupby("coin"):
        out |= _chain_months(seg, c, set(g["m"]), spans)
    return sorted(out)


def index_history_months(ctx: Ctx) -> list:
    """(coin, 'YYYY-MM') of every month the engine's outcome runs read on the index route: for each coin of the
    universes whose outcome plans have F3 / F4 rows (U-Q1, U-Q1-12, U-Q1-xm, U-A, U-C; U-B only with --ub-f3), the
    months stinkbid_engine.index_months_for gives (its member months in any of those universes or U-Q1, and the 12
    months after each; engine coding choice 27), for every coin of its chain with a USD-M contract, inside that
    coin's own spot segments (_chain_months: what build_index requests). A superset of each run's requests (a run's
    members are a subset of the union), so the outcome stages never download; months before a contract's first
    index day are empty months."""
    from analysis_2026 import stinkbid_data as sbd
    sbe = _engine()
    cols = ["U_Q1", "U_Q1_12", "U_Q1_xm", "U_A", "U_C"] + (["U_B"] if ctx.ub_f3 else [])
    mem = _members(ctx)
    coins = set()
    for c in cols:
        coins |= set(mem.get(c, {}))
    seg = pd.read_csv(sbd.OUT / "ref" / "segments.csv")
    out, spans = set(), {}
    for c in sorted(coins):
        ms = set()
        for col in cols:
            ms |= set(mem.get(col, {}).get(c, set()))
        # _members counts months as (year - 1970) * 12 + month - 1, the engine's numpy month ints
        want = set(sbe.index_months_for(np.array(sorted(ms), np.int64),
                                        np.array(sorted(mem.get("U_Q1", {}).get(c, set())), np.int64)))
        out |= _chain_months(seg, c, want, spans)
    return sorted(out)


def fut_months_missing(ctx: Ctx) -> dict:
    """Months the data stage planned (OUT/data/prefetch_index.csv, prefetch_perp.csv) that are not in stinkbid_data's
    month cache: {kind: [(coin, month)]}. The fill and outcome stages refuse while any is missing, so they never
    download (a download inside a run could fail mid-run or change what a run reads)."""
    from analysis_2026 import stinkbid_data as sbd
    out = {}
    for kind, f in (("index", "prefetch_index.csv"), ("perp", "prefetch_perp.csv")):
        p = ctx.out / "data" / f
        if not p.exists():
            out[kind] = [("*", f"{f} missing")]
            continue
        t = pd.read_csv(p, dtype={"coin": str, "month": str})
        miss = [(c, m) for c, m in zip(t["coin"], t["month"])
                if not sbd._fut_path(kind, c, m).exists() or not sbd._fut_path(kind, c, m).with_suffix(".json").exists()]
        bad = t[t.get("error", pd.Series("", index=t.index)).fillna("").astype(str) != ""]
        out[kind] = miss + [(c, f"{m}: {e}") for c, m, e in zip(bad["coin"], bad["month"], bad["error"])]
    return out


# ============================================================================ 2. controls
def _call_controls(ctx: Ctx):
    """Run the controls (coding choice 1 of the module docstring)."""
    if ctx.controls_fn is not None:
        return ctx.controls_fn(ctx)
    if importlib.util.find_spec("analysis_2026.stinkbid_controls") is None:
        raise StageRefused("controls refuses: analysis_2026/stinkbid_controls.py does not exist yet (the controls "
                           "agent's module); run it, or place its summary.json in "
                           f"{ctx.out / 'controls'}")
    mod = importlib.import_module("analysis_2026.stinkbid_controls")
    cdir = ctx.out / "controls"
    fn = getattr(mod, "run", None)
    if callable(fn):
        sig = inspect.signature(fn).parameters
        kw = {}
        for k in ("out", "out_dir", "outdir"):
            if k in sig:
                kw[k] = cdir
        for k in ("jobs", "n_jobs", "workers"):
            if k in sig:
                kw[k] = ctx.n_jobs
        if "quick" in sig:
            kw["quick"] = False
        if any(k in kw for k in ("out", "out_dir", "outdir")) or ctx.out == RES:
            return fn(**kw)
    # the controls module's documented CLI: python3 -m analysis_2026.stinkbid_controls run [--jobs N]
    cmd = [sys.executable, "-m", "analysis_2026.stinkbid_controls", "run", "--jobs", str(ctx.n_jobs)]
    r = subprocess.run(cmd, cwd=str(ROOT))
    if r.returncode not in (0, 2):
        raise RuntimeError(f"{' '.join(cmd)} exited with {r.returncode}")
    return None


def k1c_delta90(ctx: Ctx, summary: dict | None):
    """K1c's Delta under X-HOLD-90 ("what regime timing alone produces", printed with D-H2): the controls' K1 ->
    K1c -> HOLD90 -> engine_delta_RH (else engine_delta), from summary.json or controls/k1.json; a flat
    K1c.delta90 is accepted too."""
    cands = []
    for S in (summary or {}, _jload(ctx.out / "controls" / "k1.json", {}) or {}):
        if isinstance(S, dict):
            cands += [S.get("K1c"), (S.get("K1") or {}).get("K1c") if isinstance(S.get("K1"), dict) else None]
    for c in cands:
        if not isinstance(c, dict):
            continue
        if "delta90" in c:
            return sbdesc._f(c["delta90"])
        h = c.get("HOLD90")
        if isinstance(h, dict):
            for k in ("engine_delta_RH", "engine_delta"):
                if k in h:
                    return sbdesc._f(h[k])
    return None


def stage_controls(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "controls")
    started = _now()
    f = ctx.out / "controls" / "summary.json"
    if not f.exists():
        _call_controls(ctx)
    S = _jload(f)
    if not isinstance(S, dict) or not isinstance(S.get("all_passed"), bool):
        raise StageRefused(f"controls refuses to complete: {f} is missing or has no boolean all_passed")
    cs = controls_status(ctx)
    man = controls_manifest(ctx)
    info = dict(started=started, all_passed=bool(S["all_passed"]), gate_ok=cs["ok"], why=cs["why"],
                calibrated_tests=cs.get("calibrated_tests", []), outputs=[str(f)], manifest=man)
    write_marker(ctx, "controls", t0, info)
    ctx.log(f"controls: all_passed = {S['all_passed']}; gate {'open' if cs['ok'] else 'closed: ' + cs['why']}")
    return info


# ============================================================================ 3. fcount
def fill_counts(res: dict, prog: str, univ: str) -> tuple:
    """Counts only (§14 stage 3): per variant (real / placebo for H4 programs) and rule, bids, fills, fill rate, coins
    and months with fills, the effective number of months, G* of the month-blocks, fill days, episodes, halves,
    market-wide share, speed classes, gap-through fills and F3-unverifiable fills; and fills per month."""
    B, F = res.get("bids", pd.DataFrame()), res.get("fills", pd.DataFrame())
    rows, months = [], []
    if B is None or not len(B):
        return [dict(program=prog, universe=univ, variant="(none)", real=True, rule="F1", bids=0, fills=0)], []
    rules = [c[2:] for c in F.columns if c.startswith("t_F") and not c.startswith("t_F3usd")] if len(F) else ["F1"]
    keys = [("all", None)] + [(v, r) for v, r in B.groupby(["variant", "real"]).size().index]
    for var, real in keys:
        if var == "all":
            bm = np.ones(len(B), bool)
            fm = np.ones(len(F), bool) if len(F) else np.zeros(0, bool)
            real_v = "all"
        else:
            bm = (B["variant"].to_numpy() == var) & (B["real"].astype(bool).to_numpy() == bool(real))
            fm = ((F["variant"].to_numpy() == var) & (F["real"].astype(bool).to_numpy() == bool(real))) if len(F) \
                else np.zeros(0, bool)
            real_v = bool(real)
        nb = int(bm.sum())
        for rule in rules:
            tcol = "t_" + rule
            g = F[fm & (F[tcol].to_numpy() >= 0)] if len(F) and tcol in F else F.iloc[:0]
            row = dict(program=prog, universe=univ, variant=var, real=real_v, rule=rule, bids=nb, fills=int(len(g)),
                       fill_rate=float(len(g) / nb) if nb else NAN, coins=0, months=0, eff_months=NAN,
                       month_blocks=0, gstar=NAN, fill_days=0, episodes=0, half0=0, half1=0)
            if len(g):
                t = sbdesc.ts_min(g[tcol].to_numpy(np.int64))
                mo = sbs.month_key(t)
                _, cnt = np.unique(mo, return_counts=True)
                mb, _ = sbs.month_blocks(t)
                hf = sbs.half_key(t)
                row.update(coins=int(g["coin"].nunique()), months=int(len(cnt)), eff_months=sbs.eff_clusters(cnt),
                           month_blocks=int(len(np.unique(mb))), gstar=sbs.gstar(np.bincount(mb)),
                           fill_days=int(len(np.unique(sbs.fill_days(t)))),
                           episodes=int(len(np.unique(sbs.episodes(t)[0]))), half0=int((hf == 0).sum()),
                           half1=int((hf == 1).sum()))
                if rule == "F1":
                    if "mw" in g:
                        mw = pd.to_numeric(g["mw"], errors="coerce").to_numpy(float)
                        row["mw_share"] = float(np.nanmean(mw)) if np.isfinite(mw).any() else NAN
                    if "s24" in g:
                        cls = sbdesc._speed_class(g["s24"].to_numpy(float))
                        for c in ("fast", "middle", "slow"):
                            row[f"{c}_share"] = float((cls == c).mean())
                    for c in ("gap_through", "idx_missing"):
                        if c in g:
                            row[c] = int(g[c].fillna(False).astype(bool).sum())
                if var != "all" or prog in ("P1",):
                    for m_, n_ in zip(*np.unique(mo, return_counts=True)):
                        months.append(dict(program=prog, universe=univ, variant=var, real=real_v, rule=rule,
                                           month=int(m_), fills=int(n_)))
            rows.append(row)
    return rows, months


def _int0(x) -> int:
    """An integer count from a table cell; NaN / None / missing -> 0 (a program with bids but no fill)."""
    v = sbdesc._f(x)
    return int(v) if np.isfinite(v) else 0


def fcount_text(C: pd.DataFrame, mode: str) -> str:
    """fcount.txt: one line per program (all variants, F1)."""
    lines = ["Fill counts per program (counts only; no outcome was computed), STINKBID_PREREG.md §14 stage 3",
             f"mode: {mode}; written {_now()}", ""]
    if len(C):
        for (p, u), g in C.groupby(["program", "universe"], sort=False):
            a = g[(g["variant"] == "all") & (g["rule"] == "F1")]
            if len(a):
                a = a.iloc[0]
                lines.append(f"{p:9s} {u:8s} bids {_int0(a.get('bids')):>8,}  F1 fills {_int0(a.get('fills')):>6,}  "
                             f"months {_int0(a.get('months')):>3}  G* {sbdesc._f(a.get('gstar')):5.1f}  episodes "
                             f"{_int0(a.get('episodes')):>3}")
            else:
                lines.append(f"{p:9s} {u:8s} bids {0:>8,}  (no bid placed)")
    return "\n".join(lines) + "\n"


def stage_fcount(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "fcount")
    started = _now()
    d = ctx.out / "fcount"
    d.mkdir(parents=True, exist_ok=True)
    rows, months, status, audit = [], [], [], []
    p1_eps = None
    for prog, univ, plan in FCOUNT_RUNS:
        res = run_engine(ctx, prog, univ, plan, counts_only=True)
        if res is None:
            continue
        r, m = fill_counts(res, prog, univ)
        rows += r
        months += m
        bs = res.get("bid_status", pd.DataFrame())
        if len(bs):
            for k, v in bs["status"].value_counts().items():
                status.append(dict(program=prog, universe=univ, status=k, placements=int(v)))
        A = res.get("audit", pd.DataFrame())
        audit.append(dict(program=prog, universe=univ,
                          violations=int((A["type"] == "violation").sum()) if len(A) and "type" in A else 0,
                          gap_listings=int((A["type"] == "gap").sum()) if len(A) and "type" in A else 0))
        if prog == "P1" and univ == "U_Q1" and len(res["fills"]):
            F = res["fills"]
            f1 = F[F["t_F1"] >= 0]
            if len(f1):
                t = sbdesc.ts_min(f1["t_F1"].to_numpy(np.int64))
                ids, tab = sbs.episodes(t)
                cn = f1["coin"].astype(str).to_numpy()
                tab["coins"] = [len(np.unique(cn[ids == e])) for e in tab["episode"]]
                p1_eps = tab
    C = pd.DataFrame(rows)
    C.to_csv(d / "counts.csv", index=False)
    pd.DataFrame(months).to_csv(d / "by_month.csv", index=False)
    pd.DataFrame(status).to_csv(d / "status.csv", index=False)
    pd.DataFrame(audit).to_csv(d / "audit.csv", index=False)
    if p1_eps is not None:
        p1_eps.to_csv(d / "p1_episodes.csv", index=False)
    (d / "fcount.txt").write_text(fcount_text(C, ctx.mode))
    summ = dict(programs=int(C[["program", "universe"]].drop_duplicates().shape[0]),
                violations=int(sum(a["violations"] for a in audit)))
    _jdump(d / "summary.json", summ)
    info = dict(started=started, outputs=[str(d / f) for f in ("counts.csv", "by_month.csv", "status.csv",
                                                                  "audit.csv", "p1_episodes.csv", "fcount.txt",
                                                                  "summary.json")], **summ)
    write_marker(ctx, "fcount", t0, info)
    ctx.log(f"fcount: counts for {summ['programs']} programs -> {d}")
    return info


# ============================================================================ 4. primary (§10.3)
def _mean_pos(y) -> bool:
    y = np.asarray(y, float)
    y = y[np.isfinite(y)]
    return bool(len(y) and y.mean() > 0)


def _mean(y) -> float:
    y = np.asarray(y, float)
    y = y[np.isfinite(y)]
    return float(y.mean()) if len(y) else NAN


def _calibrate(row: dict, test: str, calib: dict | None) -> dict:
    if calib is None:
        return row
    r = sbs.apply_calibration(row, test, calib)
    r["rule"] = "simulation-calibrated" if r.get("calibrated") else "nominal"
    return r


def _clean_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k in ("tstar", "tstar_restricted", "tstar_unrestricted", "clusters"):
            continue
        out[k] = v
    return out


def _mean_test(d: pd.DataFrame, test: str, ctx: Ctx, calib) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = sbs.test_mean(d["y"].to_numpy(float), d["mb"].to_numpy(), E_=E[test], B=ctx.B, unit="month-block")
    return _calibrate(r, test, calib)


def _mean_gates(d: pd.DataFrame, ub_rows: pd.DataFrame, f3_rows: pd.DataFrame, r_pos=None) -> dict:
    """The gates of H1 / H2R (coding choice 3): halves, without the worst month-block, without the biggest episode,
    U-B and F3 (and mean r_f > 0 for H1)."""
    y = d["y"].to_numpy(float)
    g = {}
    if r_pos is not None:
        g["mean_r_pos"] = bool(r_pos)
    for h in (0, 1):
        g[f"half{h + 1}_pos"] = _mean_pos(y[d["hf"].to_numpy() == h]) if len(d) else False
    if len(d):
        wb = sbs.drop_worst_group_mean(y, d["mb"].to_numpy())[0]
        be = sbs.drop_biggest_group_mean(y, d["ep"].to_numpy())[0]
    else:
        wb = be = NAN
    g["no_worst_block_pos"] = bool(np.isfinite(wb) and wb > 0)
    g["no_biggest_episode_pos"] = bool(np.isfinite(be) and be > 0)
    g["u_b_pos"] = _mean_pos(ub_rows["y"]) if len(ub_rows) else False
    g["f3_pos"] = _mean_pos(f3_rows["y"]) if len(f3_rows) else False
    return g


def _h4_frames(res: dict, rule: str, fill_ids=None) -> dict:
    sbe = _engine()
    if res is None:
        return {}
    try:
        fr = sbe.h4_frames(res, rule, "FLIP")
    except Exception:
        return {}
    out = {}
    for m in sbs.H4_METHODS:
        if m in fr:
            f = fr[m]
            if fill_ids is not None:
                f = f[np.isin(f["fill_id"].to_numpy(), fill_ids)].reset_index(drop=True)
            out[m] = f
    return out


def _h4_test(methods: dict, ctx: Ctx, calib) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = sbs.test_h4(methods, B=ctx.B, E_=E["H4"]) if methods else dict(
            methods=pd.DataFrame(), T=NAN, argmax=None, estimate=NAN, p_decide=NAN, ub=NAN, clusters={}, n=0, G=0,
            gstar=NAN, mde=NAN, ci95=(NAN, NAN), n_bonf=4)
    if calib is not None and isinstance(r.get("methods"), pd.DataFrame) and len(r["methods"]):
        r = _calibrate(r, "H4", calib)
    return r


def _h4_gates(row: dict, methods: dict, f3: dict) -> tuple:
    """H4's gates (coding choice 3): (gates {name: bool}, the argmax method's fit under F3 as a beside row). methods:
    the F1 stacked frames test_h4 ran on (row = its result); f3: the stacked frames on F3 (s = 1%, h4_frames(res,
    'F3_1'))."""
    am = row.get("argmax")
    g = dict(half1_pos=False, half2_pos=False, no_worst_block_pos=False, f3_pos=False)
    b3 = dict(estimate=NAN, ci_lo=NAN, ci_hi=NAN, n=0, G=0, gstar=NAN, unit="month-block", method=am,
              label=sbdesc.LABEL_RH)
    if am is None or am not in methods:
        return g, b3
    fr = methods[am]
    part = row["clusters"][am]
    hf = sbs.half_key(fr["time"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for h in (0, 1):
            b = sbs.h4_fit(fr, mask=hf == h, clusters=part)["b"]
            g[f"half{h + 1}_pos"] = bool(np.isfinite(b) and b > 0)
        b, _ = sbs.h4_drop_worst_block(fr, clusters=part)
        g["no_worst_block_pos"] = bool(np.isfinite(b) and b > 0)
        f3 = f3 or {}
        if am in f3 and len(f3[am]):
            cl3 = sbs.h4_clusters(f3)[am]
            fit3 = sbs.h4_fit(f3[am], clusters=cl3)
            g["f3_pos"] = bool(np.isfinite(fit3["b"]) and fit3["b"] > 0)
            q = sbs._tppf(0.975, fit3["gstar"] - 1) if np.isfinite(fit3["gstar"]) else NAN
            b3.update(estimate=fit3["b"], ci_lo=fit3["b"] - q * fit3["se"], ci_hi=fit3["b"] + q * fit3["se"],
                      n=int(fit3["n"]), G=int(fit3["G"]), gstar=fit3["gstar"], se=fit3["se"])
    return g, b3


def _beside(res: dict, stat: str, rule: str, exit: str = "FLIP", B: int = sbs.B_BOOT) -> dict:
    d = sbdesc.per_fill(res, rule, exit) if stat == "delta" else sbdesc.per_bench(res, rule, "alert_M")
    r = sbdesc.mean_row(d, B=B)
    r["label"] = sbdesc.rule_label(rule)
    return r


def primary_compute(runs: dict, calib: dict | None, ctx: Ctx) -> dict:
    """H1, H2R and H4 with every gate (§10.3; coding choices 3-6), the rows beside them and the robustness checks."""
    P, UB, H4, UC = (runs.get(k) for k in ("P1/U_Q1", "P1/U_B", "H4/U_Q1", "P1/U_C"))
    out = dict(rows={}, gates={}, beside={}, robust={}, bot={}, f3kept={}, samples={}, warnings=[])
    B = ctx.B
    # ---- H1 FLIP
    d1 = sbdesc.per_fill(P, "F1", "FLIP", "C-RH", "delta")
    ub1 = sbdesc.per_fill(UB, "F1", "FLIP", "C-RH", "delta") if UB is not None else sbdesc.per_fill({}, "F1")
    f31 = sbdesc.per_fill(P, "F3_1", "FLIP", "RH", "delta")
    out["rows"]["H1"] = _mean_test(d1, "H1", ctx, calib)
    out["gates"]["H1"] = _mean_gates(d1, ub1, f31, r_pos=_mean_pos(d1["r"]) if len(d1) else False)
    out["robust"]["H1"] = sbdesc.robust(d1)
    out["beside"]["H1"] = {"mean_r": _mean(d1["r"]) if len(d1) else NAN,
                           "F3_1": _beside(P, "delta", "F3_1", B=B), "F3d_1": _beside(P, "delta", "F3d_1", B=B),
                           "F3_3": _beside(P, "delta", "F3_3", B=B),
                           "U_B": sbdesc.mean_row(ub1, B=B),
                           "U_C": _beside(UC, "delta", "F1", B=B) if UC is not None else {},
                           "U_C_F3": _beside(UC, "delta", "F3_1", B=B) if UC is not None else {}}
    # bot latency (coding choice 5)
    db = sbdesc.per_fill(P, "F1", "FLIP_bot", "C-RH", "delta")
    ubb = sbdesc.per_fill(UB, "F1", "FLIP_bot", "C-RH", "delta") if UB is not None else sbdesc.per_fill({}, "F1")
    f3b = sbdesc.per_fill(P, "F3_1", "FLIP_bot", "RH", "delta")
    out["bot"] = dict(row=_mean_test(db, "H1", ctx, calib),
                      gates=_mean_gates(db, ubb, f3b, r_pos=_mean_pos(db["r"]) if len(db) else False))
    # F3-kept subset (coding choice 6)
    keep = d1["t_F3_1"].to_numpy() >= 0 if "t_F3_1" in d1 else np.zeros(len(d1), bool)
    k1 = sbdesc.add_clusters(d1[keep].drop(columns=["mb", "ep", "qb", "hf", "wk", "mo", "qu", "yr", "day"]))
    out["f3kept"]["H1"] = _mean_test(k1, "H1", ctx, calib) if len(k1) else dict(p_decide=NAN, n=0)
    # ---- H2R RESTING
    d2 = sbdesc.per_bench(P, "F1", "alert_M")
    ub2 = sbdesc.per_bench(UB, "F1", "alert_M") if UB is not None else sbdesc.per_bench({}, "F1")
    f32 = sbdesc.per_bench(P, "F3_1", "alert_M")
    out["rows"]["H2R"] = _mean_test(d2, "H2R", ctx, calib)
    out["gates"]["H2R"] = _mean_gates(d2, ub2, f32)
    out["robust"]["H2R"] = sbdesc.robust(d2)
    out["beside"]["H2R"] = {"F3_1": _beside(P, "alert", "F3_1", B=B), "F3d_1": _beside(P, "alert", "F3d_1", B=B),
                            "F3_3": _beside(P, "alert", "F3_3", B=B), "U_B": sbdesc.mean_row(ub2, B=B),
                            "U_C": _beside(UC, "alert", "F1", B=B) if UC is not None else {},
                            "U_C_F3": _beside(UC, "alert", "F3_1", B=B) if UC is not None else {}}
    keep = d2["t_F3_1"].to_numpy() >= 0 if "t_F3_1" in d2 else np.zeros(len(d2), bool)
    k2 = sbdesc.add_clusters(d2[keep].drop(columns=["mb", "ep", "qb", "hf", "wk", "mo", "qu", "yr", "day"]))
    out["f3kept"]["H2R"] = _mean_test(k2, "H2R", ctx, calib) if len(k2) else dict(p_decide=NAN, n=0)
    # ---- H4 LEVELS
    methods = _h4_frames(H4, "F1")
    missing = [m for m in sbs.H4_METHODS if m not in methods]
    if missing:
        out["warnings"].append(f"H4: no stacked fills for {missing} (NO EDGE needs a bound for all four methods)")
    r4 = _h4_test(methods, ctx, calib)
    f3m = _h4_frames(H4, "F3_1")
    out["gates"]["H4"], b3 = _h4_gates(r4, methods, f3m)
    am = r4.get("argmax")
    if am is not None and am in methods:
        fr = methods[am]
        part = r4["clusters"][am]
        dd = sbdesc.add_clusters(pd.DataFrame({"time": pd.to_datetime(fr["time"], utc=True)}))

        def fit(mask, fr=fr, part=part):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return sbs.h4_fit(fr, mask=mask, clusters=part)["b"]
        out["robust"]["H4"] = sbdesc.robust_fit(dd, fit)
    else:
        out["robust"]["H4"] = sbdesc.robust_fit(pd.DataFrame(), None)
    F = H4["fills"] if H4 is not None else pd.DataFrame()
    kept_ids = F.loc[F["t_F3_1"] >= 0, "fill_id"].to_numpy() if len(F) and "t_F3_1" in F else np.zeros(0)
    mk = _h4_frames(H4, "F1", kept_ids)
    out["f3kept"]["H4"] = _clean_row(_h4_test(mk, ctx, calib)) if mk else dict(p_decide=NAN, n=0)
    r43 = _clean_row(_h4_test(f3m, ctx, None)) if f3m else {}
    out["beside"]["H4"] = {"F3_1": b3, "F3_1_omnibus": dict(T=r43.get("T"), argmax=r43.get("argmax"),
                                                            p_decide=r43.get("p_decide"), note="H4 re-run on F3 fills")}
    out["rows"]["H4"] = r4
    out["samples"] = {"H1": d1, "H2R": d2}
    return out


def stage_primary(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "primary")
    started = _now()
    cs = controls_status(ctx)
    runs = runs_for(ctx, ANSWER_RUNS)
    if runs.get("P1/U_Q1") is None:
        raise StageRefused("primary: P1 on U-Q1 could not be run")
    Pc = primary_compute(runs, cs["calib"], ctx)
    d = ctx.out / "primary"
    d.mkdir(parents=True, exist_ok=True)
    meth = Pc["rows"]["H4"].get("methods")
    if isinstance(meth, pd.DataFrame):
        meth.to_csv(d / "h4_methods.csv", index=False)
    for t, s in Pc["samples"].items():
        cols = [c for c in ("fill_id", "coin", "time", "rung", "y", "r", "mb", "ep", "hf", "t_F3_1") if c in s]
        s[cols].to_csv(d / f"samples_{t}.csv", index=False)
    rows = {t: _clean_row(r) for t, r in Pc["rows"].items()}
    js = dict(rows=rows, gates=Pc["gates"], beside=Pc["beside"], robust=Pc["robust"],
              bot=dict(row=_clean_row(Pc["bot"]["row"]), gates=Pc["bot"]["gates"]),
              f3kept={t: _clean_row(r) for t, r in Pc["f3kept"].items()}, warnings=Pc["warnings"],
              calibration={t: ("simulation-calibrated" if Pc["rows"][t].get("calibrated") else "nominal")
                           for t in FAMILY}, mode=ctx.mode, B=ctx.B, runs=[f"{p}/{u}" for p, u, _ in ANSWER_RUNS])
    _jdump(d / "primary.json", js)
    g = pd.DataFrame([dict(test=t, gate=k, held=v) for t, gg in Pc["gates"].items() for k, v in gg.items()
                      if isinstance(v, (bool, np.bool_))])
    g.to_csv(d / "gates.csv", index=False)
    info = dict(started=started, outputs=[str(d / f) for f in ("primary.json", "gates.csv", "h4_methods.csv",
                                                                  "samples_H1.csv", "samples_H2R.csv")])
    write_marker(ctx, "primary", t0, info)
    ctx.log(f"primary: H1, H2R and H4 with their gates -> {d} (read the verdicts after the report stage)")
    return info


# ============================================================================ 5. report (§10.3 verdicts, §11 answer)
NAMES = {"H2R": "Rest vs alert (H2R RESTING)", "H1": "Flip (H1 FLIP)", "H4": "Levels (H4 LEVELS)"}
E_TXT = {"H2R": "2% per fill", "H1": "3.75% per fill", "H4": "1% per fill"}
CLAIM = {"H2R": "resting bids bought more coin per dollar than an alert at the same level followed by a manual buy",
         "H1": "stink-bid fills sold into the rebound by hand beat random buys of the same coin with the same exit",
         "H4": "a chart method's levels beat plain volatility-scaled levels at the same depth, in the same wick"}

DISCOUNT = ("A bid's discount is not a gain by itself. If prices are unpredictable, a bid 30% below the price buys the "
            "same expected value as buying now, minus what the coin earns while you wait; in a crash that gaps "
            "through your price, it buys less. Only a quick rebound after the wick can pay for the wait.")
TAIL_NEWS = ("Coin-specific collapses (LUNA, FTT, OM) look like ordinary wicks on the first day; a resting order "
             "cannot read the news. Cancel a coin's bids on news about the coin itself (a hack, exploit, depeg, "
             "delisting or regulatory action).")
MONEYLINE = ("Most past fills came when the coin's MoneyLine was already red; a fill buys against your own trend "
             "signal. Decide before the fill which rule governs the position.")
MONEYLINE_NOTE = "The sheet uses the replicated pre-October-2026 MoneyLine."
RH_PROXY = ("Robinhood fidelity: no Robinhood crypto history exists here, so every Robinhood-route number (F3, F4) is "
            "a proxy and says so.")


def _pct(x, nd=1, sign=False):
    return sbdesc.fmt_pct(x, nd, sign)


def _ci(lo, hi):
    return sbdesc.fmt_ci(lo, hi)


def recommendation(v: dict) -> list:
    """The §11 recommendation table, applied in order (H2R, then H1, then H4). v: verdicts {"H2R", "H1", "H4"} each
    PASS | NO EDGE | NO EDGE (HARMS) | INCONCLUSIVE; h1_bot_only (bool); numbers per test (X, lo, hi, N, G, gstar,
    M = MDE; H1 also R = mean r_f; H4 also j = the method); mu_star {rung: value}. Returns [(key, text)]."""
    n = v.get("numbers", {})
    out = []
    a = n.get("H2R", {})
    h2r = v["H2R"]
    if h2r.startswith("NO EDGE"):
        out.append(("H2R_NOEDGE", "Don't leave stink bids resting. If you want to buy after crashes, set price alerts "
                                  "at the sheet's levels and buy by hand after checking the news."))
        if h2r == "NO EDGE (HARMS)":
            out.append(("H2R_HARMS_ADD", "Resting bids bought into falls that kept going: buying a few hours later "
                                         "was cheaper."))
    elif h2r == "INCONCLUSIVE":
        out.append(("H2R_INCONCLUSIVE", f"Resting bids and alerts can't be told apart (an edge under about "
                                        f"{_pct(a.get('M'))} wouldn't show). Prefer alerts: your cash stays free and "
                                        "earning."))
    else:
        mu = v.get("mu_star") or {}
        mus = "; ".join(f"k = {k:g}: {_pct(x)} a year" for k, x in sorted(mu.items())) or "n/a"
        out.append(("H2R_PASS", f"Resting bids bought {_pct(a.get('X'))} more coin per dollar than buying by hand a "
                                f"few hours later ({_ci(a.get('lo'), a.get('hi'))}), over {a.get('N')} fills in "
                                f"{a.get('G')} months (about {sbdesc._f(a.get('gstar')):.0f} independent months). Use "
                                "them only with cash you would otherwise hold in T-bills. Whether waiting beats buying "
                                "now depends on your expectation: at rung k, waiting pays only if you expect the coin "
                                f"to beat cash by less than mu*_k a year (D6): {mus}."))
    b = n.get("H1", {})
    h1 = v["H1"]
    if h1 == "PASS":
        out.append(("H1_PASS", f"Selling stink-bid fills into the rebound by hand beat random buys of the same coin by "
                               f"{_pct(b.get('X'))} per fill ({_ci(b.get('lo'), b.get('hi'))}). After Robinhood costs, "
                               f"a flip made {_pct(b.get('R'), sign=True)} on average. It held in both halves, without "
                               "the biggest month and crash, and on Robinhood-like prices. The sheet shows the flip "
                               "target."))
    elif h1.startswith("NO EDGE"):
        out.append(("H1_NOEDGE", "Flipping stink-bid fills doesn't beat random buys by the 3.75% per fill it would "
                                 "take to cover the round trip and the cash the bids tie up. Don't run the flip "
                                 "version."))
        if h1 == "NO EDGE (HARMS)":
            out.append(("H1_HARMS_ADD", "And the fills did worse than random buys: they tended to come before further "
                                        "falls."))
    else:
        out.append(("H1_INCONCLUSIVE", "The data can't tell. Deep fills come from about a dozen independent crash "
                                       f"months, so an edge would have to be about {_pct(b.get('M'))} per fill or "
                                       "more to show up, and an edge that lives only in the two or three biggest "
                                       "crashes could not show up at any size. No flip target."))
    if h1 != "PASS" and v.get("h1_bot_only"):
        out.append(("H1_BOT_ONLY", "The flip worked only for sell orders placed within a minute of the fill, which "
                                   "you cannot do by hand. No flip target."))
    c = n.get("H4", {})
    h4 = v["H4"]
    if h4 == "PASS":
        out.append(("H4_PASS", f"Method {c.get('j')}'s levels beat plain volatility-scaled levels at the same depth, "
                               f"in the same wicks, by {_pct(c.get('X'))} per fill ({_ci(c.get('lo'), c.get('hi'))}). "
                               "The sheet shows them."))
    elif h4.startswith("NO EDGE"):
        out.append(("H4_NOEDGE", "Chart levels (swing lows, round numbers, volume nodes, liquidation bands) were not "
                                 "better places for a bid than a plain volatility-scaled level at the same depth, by "
                                 "1% per fill or more."))
    else:
        out.append(("H4_INCONCLUSIVE", "Can't tell; the sheet uses plain volatility-scaled levels."))
    return out


def fixed_sentences(nums: dict) -> list:
    """§11 'Sentences printed with every answer' with their computed numbers (coding choice 10)."""
    wd = nums.get("worst_day", {}) or {}
    kn = nums.get("knife", {}) or {}
    ml = nums.get("moneyline", {}) or {}
    cap = nums.get("capacity", []) or []
    capt = "; ".join(f"rung k = {sbdesc._f(r.get('rung')):g}: 10th percentile ${sbdesc._f(r.get('C_p10')):,.0f}, "
                     f"cap about ${sbdesc._f(r.get('Q_max')):,.0f} per order" for r in cap) or "n/a"
    red = ml.get("red_share_of_defined")
    out = [("DISCOUNT", DISCOUNT),
           ("TAIL_TOGETHER", f"Bids fill together. On the worst day, {_pct(wd.get('share'), 0)} of the live bids in "
                             "the study's main universe filled the same day. Size the whole ladder as one position you "
                             f"are willing to hold through a further 50-80% fall. [day {wd.get('day')}: "
                             f"{wd.get('filled')} of {wd.get('live')} live P1 bids on U-Q1]"),
           ("TAIL_BOTTOM", f"A fill is not a bottom: {_pct(kn.get('A'))} of past fills were 50% or more below the fill "
                           f"price a year later, against {_pct(kn.get('B'))} for random buys of the same coins. "
                           f"[{kn.get('n')} P1 fills with a year observed]"),
           ("TAIL_NEWS", TAIL_NEWS),
           ("MONEYLINE", MONEYLINE + " " + MONEYLINE_NOTE + f" [computed: {_pct(red)} of P1 fills with a defined "
                         f"state were red at placement ({ml.get('red')} red, {ml.get('green')} green, "
                         f"{ml.get('undefined')} undefined)"
                         + ("; note: not a majority" if (red is not None and np.isfinite(sbdesc._f(red))
                                                         and sbdesc._f(red) <= 0.5) else "") + "]"),
           ("CAPACITY", "Capacity: assume every rung fills on the same day, and keep each order within the size cap "
                        "(a quarter of the 10th percentile of past seller-initiated dollars printed below the level "
                        f"on Binance spot): {capt}.")]
    return out


def answer_flags(fv: pd.DataFrame, P: dict) -> dict:
    """Flags of §11's further rules (coding choices 5, 6, 8)."""
    vd = dict(zip(fv["test"], fv["verdict"]))
    lv = dict(zip(fv["test"], fv["holm_level"]))
    rows = P["rows"]
    # bot latency: H1-bot's p in H1's place
    p = [sbdesc._f(P["bot"]["row"].get("p_decide")), sbdesc._f(rows["H2R"].get("p_decide")),
         sbdesc._f(rows["H4"].get("p_decide"))]
    ph = sbs.holm(p)
    # "is PASS" under the same rule as every verdict (prereg Addendum 1, A1.8): a bot version whose 98.33% bound is
    # below E is NO EDGE, not PASS, even when its Holm-adjusted p and every bot gate pass
    bot_ub = sbdesc._f(P["bot"]["row"].get("ub"))
    e_h1 = dict(zip(fv["test"], fv["E"])).get("H1", sbs.E["H1"]) if "E" in fv else sbs.E["H1"]
    bot_verdict = sbs.verdict(ph[0], P["bot"]["gates"], bot_ub, e_h1)
    bot_pass = bool(bot_verdict == "PASS")
    h1_bot_only = bool(vd["H1"] != "PASS" and bot_pass)
    binance_only = {}
    for t in FAMILY:
        if vd[t] == "PASS":
            pk = sbdesc._f(P["f3kept"].get(t, {}).get("p_decide"))
            binance_only[t] = not (np.isfinite(pk) and pk < lv[t])
    b = P["beside"]["H1"]
    e3, e3d = sbdesc._f(b.get("F3_1", {}).get("estimate")), sbdesc._f(b.get("F3d_1", {}).get("estimate"))
    dips = bool(np.isfinite(e3) and np.isfinite(e3d) and np.sign(e3) != np.sign(e3d))
    return dict(verdicts=vd, holm_level=lv, bot_pass=bot_pass, h1_bot_only=h1_bot_only, bot_p_holm=float(ph[0]),
                bot_verdict=bot_verdict, bot_ub=bot_ub,
                binance_only=binance_only, index_dips_only=dips, show_flip_target=bool(vd["H1"] == "PASS"),
                tests_passed=[t for t in FAMILY if vd[t] == "PASS"])


def run_on_robinhood(flags: dict, P: dict, d7r: dict | None) -> dict:
    """§11 further rule (coding choice 7)."""
    vd = flags["verdicts"]
    passing = [t for t in ("H1", "H2R") if vd[t] == "PASS"]
    if not passing:
        return dict(ok=False, why="neither H1 nor H2R passed")
    uc = {t: sbdesc._f((P["beside"][t].get("U_C_F3") or {}).get("estimate")) for t in passing}
    uc_ok = [t for t in passing if np.isfinite(uc[t]) and uc[t] > 0]
    acc_ok = bool(d7r and d7r.get("ok"))
    ok = bool(uc_ok and acc_ok)
    why = []
    if not acc_ok:
        why.append("the D7 flip account on F3 did not beat B-MIX with a 12-month block-bootstrap interval above "
                   f"zero ({(d7r or {}).get('why', 'not computed')})")
    if not uc_ok:
        why.append(f"the effect on the Robinhood-listed row (U-C, hindsight) under F3 was not above zero ({uc})")
    return dict(ok=ok, passing=passing, uc_f3=uc, account=d7r, why="; ".join(why) if why else "all conditions hold")


def verdict_line(t: str, r: pd.Series, rb: dict, flags: dict, beside: dict) -> str:
    """The verdict of one test, stated first (§11), worded by §11's rules (NO EDGE: "not by E or more";
    INCONCLUSIVE: "the data cannot tell" with the MDE; every interval with its cluster unit, G and G*)."""
    v = r["verdict"]
    est = sbdesc._f(r["estimate"])
    stats = (f"estimate {_pct(est, sign=True)} per fill, {_ci(r['ci95_lo'], r['ci95_hi'])}; {int(r['n'])} "
             f"{'stacked ' if t == 'H4' else ''}fills, {r['unit']} clusters G = {int(r['G'])}, G* = "
             f"{sbdesc._f(r['gstar']):.1f}; p = {sbdesc._f(r['p_decide']):.4f}, Holm-adjusted "
             f"{sbdesc._f(r['p_holm']):.4f} at level {sbdesc._f(r['holm_level']):.4f}"
             + (f"; method {r['argmax']}" if t == "H4" and isinstance(r.get("argmax"), str) else "")
             + ("; K3 simulation-calibrated" if r.get("calibrated") else ""))
    head = f"{NAMES[t]}: {v}."
    if v == "PASS":
        s = f"{head} Yes: {CLAIM[t]}, by {_pct(est)} per fill ({_ci(r['ci95_lo'], r['ci95_hi'])}); every gate held."
        if flags["binance_only"].get(t):
            s += " This is a Binance-only result: it relies on events the Robinhood-route proxy (F3) removes."
    elif v == "NO EDGE":
        s = (f"{head} Not by {E_TXT[t]} or more: the 98.33% upper bound is {_pct(r['ub'], 2, True)} (below E = "
             f"{E_TXT[t]}).")
        if bool(r.get("pass_and_noedge")):
            s += (f" The effect was above zero (Holm-adjusted p = {sbdesc._f(r['p_holm']):.4f}, every gate held) but "
                  f"surely below {E_TXT[t]}, the smallest effect worth acting on, so the NO EDGE advice applies "
                  "(prereg Addendum 1, A1.8).")
    elif v == "NO EDGE (HARMS)":
        s = (f"{head} Not by {E_TXT[t]} or more, and the 98.33% upper bound ({_pct(r['ub'], 2, True)}) is below zero: "
             "the effect went the other way.")
    else:
        s = (f"{head} The data cannot tell: an effect under about {_pct(r['mde'])} per fill would not show (MDE at "
             "80% power).")
        if bool(r.get("holm_rejected")) and not bool(r.get("gates_ok")):
            s += " The p-value cleared Holm but not every gate held."
    if t == "H1" and flags.get("index_dips_only"):
        s += " Under F3 and F3d the effect has opposite signs: only on brief index dips."
    cs = sbdesc.concentration_sentence(rb, v == "PASS")
    if cs:
        s += " " + cs
    return s + f" [{stats}]"


def e_sensitivity(fv: pd.DataFrame) -> dict:
    """§10.3 "2.26% (r_res = 3.35%) is a sensitivity" (coding choice 16): H1's verdict re-mapped with E =
    stinkbid_stats.E_SENS["H1_gold"] from the same Holm-adjusted p, gates and 98.33% bound (NO EDGE precedes PASS
    when both hold: prereg Addendum 1, A1.8). Never changes the primary verdict."""
    r = fv.set_index("test").loc["H1"]
    e = float(sbs.E_SENS["H1_gold"])
    ub = sbdesc._f(r["ub"])
    v = sbs.verdict(sbdesc._f(r["p_holm"]), bool(r["gates_ok"]), ub, e)
    head = (f"Sensitivity (§10.3; not the verdict): with E = {_pct(e, 2)} per fill (reserved cash earning 3.35%, the "
            f"Gold sweep), H1 would be {v}")
    if v.startswith("NO EDGE"):
        txt = f"{head}: not by {_pct(e, 2)} or more (98.33% upper bound {_pct(ub, 2, True)})."
    elif v == "PASS":
        txt = f"{head} (the 98.33% upper bound {_pct(ub, 2, True)} is not below {_pct(e, 2)})."
    else:
        txt = f"{head}: the 98.33% upper bound {_pct(ub, 2, True)} is not below {_pct(e, 2)}."
    return dict(test="H1", E=e, label="E at r_res = 3.35% (Gold sweep), sensitivity", verdict=v, ub=ub,
                primary_verdict=str(r["verdict"]), text=txt)


def _numbers_for_answer(fv: pd.DataFrame, P: dict, mu_star: dict) -> dict:
    by = {r["test"]: r for _, r in fv.iterrows()}
    rows = P["rows"]
    out = {}
    for t in FAMILY:
        r = by[t]
        out[t] = dict(X=sbdesc._f(r["estimate"]), lo=sbdesc._f(r["ci95_lo"]), hi=sbdesc._f(r["ci95_hi"]),
                      N=int(r["n"]), G=int(r["G"]), gstar=sbdesc._f(r["gstar"]), M=sbdesc._f(r["mde"]))
    out["H1"]["R"] = sbdesc._f(P["beside"]["H1"].get("mean_r"))
    out["H4"]["j"] = rows["H4"].get("argmax")
    return out


def compose_answer(fv: pd.DataFrame, P: dict, flags: dict, rh: dict, nums: dict, desc_sent: list,
                   mode: str) -> tuple:
    """The answer as printed (§11): (text lines, recommendation [(key, text)], fixed sentences [(key, text)])."""
    v = dict(flags["verdicts"], h1_bot_only=flags["h1_bot_only"], numbers=nums["tests"], mu_star=nums["mu_star"])
    rec = recommendation(v)
    fx = fixed_sentences(nums)
    lines = ["Stink bids: the answer (STINKBID_PREREG.md §11)", "",
             f"Mode: {mode}" + ("  -- SYNTHETIC DATA: NOT A RESULT" if mode != "real" else ""), ""]
    by = {r["test"]: r for _, r in fv.iterrows()}
    lines.append("The verdicts (H2R, then H1, then H4):")
    for i, t in enumerate(ORDER, 1):
        lines.append(f"{i}. " + verdict_line(t, by[t], P["robust"].get(t, {}), flags, P["beside"].get(t, {})))
    lines += ["", "What you are told (the pre-registered recommendation table, applied in order):"]
    lines += [f"- {txt}" for _, txt in rec]
    lines += ["", "Printed with every answer:"] + [f"- {txt}" for _, txt in fx]
    lines += ["", "Further rules:"]
    if rh.get("ok"):
        lines.append("- You could run it on Robinhood: " + ", ".join(rh["passing"]) + " passed, the D7 account on "
                     "the Robinhood-route proxy (F3) beat B-MIX with a 12-month block-bootstrap interval above zero, "
                     "and the effect was above zero on the Robinhood-listed coins (U-C, hindsight) under F3.")
    else:
        lines.append(f"- The study does not say you could run it on Robinhood ({rh.get('why')}).")
    nb = [t for t, b in flags["binance_only"].items() if b]
    if nb:
        lines.append(f"- {', '.join(nb)}: a Binance-only result (it relies on events F3 removes).")
    if flags["show_flip_target"]:
        lines.append("- The sheet shows the flip target R1/2 and 'sell at market after 72 h' (H1 PASS under rule M).")
    else:
        lines.append("- The sheet shows no flip target.")
    lines += ["- Wording: 'it does not work' is said only for NO EDGE; otherwise 'not shown' or 'the data cannot "
              "tell'.", "", "Descriptive sentences (no verdict):"] + [f"- {s}" for s in desc_sent]
    return lines, rec, fx


def stage_report(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "report")
    started = _now()
    P = _jload(ctx.out / "primary" / "primary.json")
    if not isinstance(P, dict):
        raise StageRefused("report refuses: primary/primary.json is missing")
    cs = controls_status(ctx)
    fv = sbs.family_verdicts(P["rows"], P["gates"])
    flags = answer_flags(fv, P)
    runs = runs_for(ctx, ANSWER_RUNS)
    Pr = runs["P1/U_Q1"]
    tb = tbill_at_fn(ctx)
    # numbers for the fixed sentences
    bft = sbdesc.bid_fill_table(Pr, ("F1",))
    kn = sbdesc.per_bench(Pr, "F1", "knife")
    knife = dict(A=float(kn["y"].mean()) if len(kn) else NAN,
                 B=float(np.nanmean(pd.to_numeric(kn["twin_knife"], errors="coerce"))) if len(kn) and
                 "twin_knife" in kn else NAN, n=int(len(kn)))
    d6 = sbdesc.d6(Pr, tb, ctx.B)
    d6 = d6[d6["rule"] == "F1"] if len(d6) and "rule" in d6 else d6       # H2R's sentence: the F1 + C-RH route
    mu = {float(r["rung"]): sbdesc._f(r["mu_star"]) for _, r in d6.iterrows()} if len(d6) else {}
    nums = dict(tests=_numbers_for_answer(fv, P, mu), mu_star=mu, worst_day=sbdesc.worst_day(bft),
                knife=knife, moneyline=sbdesc.ml_split(Pr["fills"]) if len(Pr["fills"]) else {},
                capacity=sbdesc.capacity_cap(Pr).to_dict("records"))
    # the answer's descriptive sentences (D-H2, D-H3, D-H5, D8) from stinkbid_desc
    T = dict(dh2=sbdesc.dh2(Pr, ctx.B, k1c=k1c_delta90(ctx, cs.get("summary"))),
             dh3=sbdesc.dh3(Pr, ctx.B),
             dh5=sbdesc.dh5(runs["P1/U_B"], ctx.B) if runs.get("P1/U_B") is not None else {},
             d8=sbdesc.d8(Pr, tb, ctx.B))
    dsent = sbdesc.desc_sentences(T)
    bad = sbdesc.check_wording(dsent)
    if bad:
        raise RuntimeError(f"wording rule (§11) violated by a descriptive sentence: {bad}")
    # "You could run it on Robinhood": the account part only when H1 or H2R passed
    d7r = None
    if any(flags["verdicts"][t] == "PASS" for t in ("H1", "H2R")):
        d7r = sbdesc.d7_robinhood(sbdesc.d7(Pr, ctx.data, ctx.B, routes=("F3_1",), r_res=(0.0,)))
    rh = run_on_robinhood(flags, P, d7r)
    lines, rec, fx = compose_answer(fv, P, flags, rh, nums, dsent, ctx.mode)
    # details
    det = ["", "=" * 100, "Details", "=" * 100, ""]
    d12 = sbdesc.d12(Pr)
    if len(d12):
        a = d12[d12["split"] == "all"]
        hcols = ["rule", "who", "n"] + [f"R_{h}" for h in sbdesc.REC_LABELS] + \
            [f"P0_{h}" for h in sbdesc.REC_LABELS] + ["dn10_first"]
        det += ["D12 recovery curve (§10.4, reported before H1's table): the share of fills, and of their twins, "
                "trading at or above R1/2 (R_) and at or above P0 (P0_) within 15 min .. 30 days, and the share first "
                "trading a further 10% below L (dn10_first); F3_1 = the Robinhood-route proxy. Splits in desc/d12.csv.",
                a[[c for c in hcols if c in a]].to_string(index=False, float_format=lambda x: f"{x:.3f}"), ""]
    det += ["Holm family of three one-sided tests at 5% (§10.3); p = max(p_WCR, p_G*); NO EDGE bound at 98.33%:"]
    cols = ["test", "verdict", "estimate", "ci95_lo", "ci95_hi", "n", "G", "gstar", "unit", "p_wcr", "p_gstar",
            "p_decide", "p_holm", "holm_level", "holm_rejected", "gates_ok", "ub", "E", "mde", "calibrated", "argmax"]
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        det.append(fv[cols].to_string(index=False))
    es = e_sensitivity(fv)
    det += ["", es["text"]]
    det += ["", "Gates (every gate must hold for a PASS):"]
    for t in ORDER:
        det.append(f"  {t}: " + ", ".join(f"{k} {'held' if v else 'NOT held'}" for k, v in P["gates"][t].items()
                                          if isinstance(v, bool)))
    det += ["", "Beside every headline (F3 = Robinhood market-maker-route proxy; U-C = Robinhood-listed, hindsight):"]
    for t in ORDER:
        for k, r in (P["beside"].get(t) or {}).items():
            if isinstance(r, dict) and "estimate" in r:
                det.append(f"  {t} {k:7s}: {_pct(r.get('estimate'), 2, True)} ({_ci(r.get('ci_lo'), r.get('ci_hi'))}; "
                           f"{sbdesc.unc(r)}) {r.get('label', '')}")
    det += ["", "Concentration and single events (every headline):"]
    for t in ORDER:
        rb = P["robust"].get(t, {})
        det.append(f"  {t}: top-3 episodes {', '.join(rb.get('top3_names') or [])} give "
                   f"{_pct(rb.get('top3_share'))} of the {'total' if rb.get('top3_basis') == 'sum' else 'fills'}; "
                   f"without them {_pct(rb.get('top3_without'), 2, True)}; without 2025-10-10 "
                   f"{_pct(rb.get('without_2025-10-10'), 2, True)}; without 2021-05-19 "
                   f"{_pct(rb.get('without_2021-05-19'), 2, True)}; without the top month-block "
                   f"{_pct(rb.get('without_top_block'), 2, True)}")
    det += ["", f"Bot latency (X-FLIP-bot, H1): p {sbdesc._f(P['bot']['row'].get('p_decide')):.4f}, Holm-adjusted in "
                f"H1's place {flags['bot_p_holm']:.4f}, gates "
                f"{'held' if sbs._gates_ok(P['bot']['gates']) else 'not all held'}, 98.33% upper bound "
                f"{_pct(flags.get('bot_ub'), 2, True)}: {flags.get('bot_verdict')}; passes only at bot latency: "
                f"{flags['h1_bot_only']}",
            f"K3 rule per test: {P.get('calibration')}",
            "K3 power re-run (synthetic nulls; empirical MDE at 80% power by scenario): " + "; ".join(
                f"{t}: " + ", ".join(f"{sc} {_pct(v.get('mde_empirical'), 2)}" for sc, v in
                                     ((cs.get('calib') or {}).get('tests', {}).get(t, {}).get('by_scenario') or
                                      {}).items()) for t in ORDER),
            f"Warnings: {P.get('warnings') or 'none'}", "",
            "Deviations (§12): " + ("none" if not deviations(ctx) else json.dumps(deviations(ctx))), "", RH_PROXY]
    txt = "\n".join(lines + det) + "\n"
    (ctx.out / "verdicts.txt").write_text(txt)
    vt = fv.copy()
    for t in FAMILY:
        for k, g in P["gates"][t].items():
            if isinstance(g, bool):
                vt.loc[vt["test"] == t, f"gate_{k}"] = g
        for k, r in (P["beside"].get(t) or {}).items():
            if isinstance(r, dict) and "estimate" in r:
                vt.loc[vt["test"] == t, f"beside_{k}"] = sbdesc._f(r.get("estimate"))
        rb = P["robust"].get(t, {})
        for k in ("top3_share", "top3_without", "without_2025-10-10", "without_2021-05-19", "without_top_block"):
            vt.loc[vt["test"] == t, k] = sbdesc._f(rb.get(k))
        vt.loc[vt["test"] == t, "binance_only"] = bool(flags["binance_only"].get(t, False))
    vt["h1_bot_only"] = np.where(vt["test"] == "H1", flags["h1_bot_only"], False)
    vt["e_sens"] = np.where(vt["test"] == "H1", es["E"], NAN)
    vt["verdict_e_sens"] = np.where(vt["test"] == "H1", es["verdict"], "")
    vt.to_csv(ctx.out / "verdicts.csv", index=False)
    h4m = P["rows"]["H4"].get("methods") or []
    h4lv = flags["holm_level"]["H4"]
    shown = [m["method"] for m in h4m if flags["verdicts"]["H4"] == "PASS" and
             np.isfinite(sbdesc._f(m.get("p_rw"))) and sbdesc._f(m.get("p_rw")) < h4lv]
    ans = dict(mode=ctx.mode, generated=_now(), order=list(ORDER), verdicts=flags["verdicts"],
               recommendation=[dict(key=k, text=x) for k, x in rec], fixed_sentences=[dict(key=k, text=x)
                                                                                         for k, x in fx],
               descriptive_sentences=dsent, numbers=nums, flags=dict(
                   show_flip_target=flags["show_flip_target"], h1_bot_only=flags["h1_bot_only"],
                   binance_only=flags["binance_only"], index_dips_only=flags["index_dips_only"],
                   run_on_robinhood=rh["ok"]), run_on_robinhood=rh, tests_passed=flags["tests_passed"],
               h4=dict(argmax=P["rows"]["H4"].get("argmax"), holm_level=h4lv, verdict=flags["verdicts"]["H4"],
                       methods=h4m, chart_methods_shown=shown),
               holm={t: dict(p=sbdesc._f(fv.loc[fv.test == t, "p_decide"].iloc[0]),
                             p_holm=sbdesc._f(fv.loc[fv.test == t, "p_holm"].iloc[0]), level=flags["holm_level"][t])
                     for t in FAMILY},
               sensitivity=dict(H1_E_gold=es), deviations=deviations(ctx))
    _jdump(ctx.out / "answer.json", ans)
    info = dict(started=started, outputs=[str(ctx.out / f) for f in ("verdicts.txt", "verdicts.csv", "answer.json")])
    write_marker(ctx, "report", t0, info)
    ctx.log(f"report: the answer -> {ctx.out / 'verdicts.txt'} (and verdicts.csv, answer.json)")
    return info


# ============================================================================ 6. desc, 7. explore
def stage_desc(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "desc")
    started = _now()
    cs = controls_status(ctx)
    runs = runs_for(ctx, ANSWER_RUNS + DESC_RUNS)
    T = sbdesc.compute_desc(runs, data=ctx.data, calib=_with_d11(ctx, cs["calib"]), tbill_at=tbill_at_fn(ctx),
                            B=ctx.B, controls=dict(K1c=dict(delta90=k1c_delta90(ctx, cs.get("summary")))),
                            log=ctx.log)
    sent = sbdesc.desc_sentences(T)
    bad = sbdesc.check_wording(sent)
    if bad:
        raise RuntimeError(f"wording rule (§11) violated: {bad}")
    errs = {k: v["error"] for k, v in T.items() if isinstance(v, dict) and "error" in v}
    written = sbdesc.write_tables(ctx.out / "desc", T, "Stink bids: descriptive estimands and sensitivity rows "
                                  f"(STINKBID_PREREG.md §10.4; no verdict) [{ctx.mode}]", sent)
    info = dict(started=started, outputs=written, tables=sorted(T), errors=errs)
    write_marker(ctx, "desc", t0, info)
    ctx.log(f"desc: {len(T)} tables -> {ctx.out / 'desc'}" + (f" (errors in {sorted(errs)})" if errs else ""))
    return info


def _with_d11(ctx: Ctx, calib: dict | None) -> dict | None:
    """D11's null totals: the calibration's null H1 totals, else controls/d11_null.parquet (a scenario column and a
    column whose name contains 'total')."""
    if calib and any("total" in (d or {}) for d in (calib.get("null", {}).get("H1") or {}).values()):
        return calib
    f = ctx.out / "controls" / "d11_null.parquet"
    if not f.exists():
        return calib
    try:
        t = pd.read_parquet(f)
        tc = [c for c in t.columns if "total" in c.lower()][0]
        sc = [c for c in t.columns if "scen" in c.lower()]
        groups = t.groupby(sc[0]) if sc else [("all", t)]
        null = {str(k): {"total": g[tc].to_numpy(float).tolist()} for k, g in groups}
        out = dict(calib or {})
        out["null"] = dict(out.get("null", {}), H1=null)
        return out
    except Exception:
        return calib


def _metrics_fn(ctx: Ctx):
    if ctx.injected:
        return None
    from analysis_2026 import stinkbid_data as sbd
    cache = {}

    def f(coin, t_min):
        try:
            if coin not in cache:
                k = sbd.metrics(coin)
                cache[coin] = (pd.DatetimeIndex(k["create_time"]).asi8 // 60_000_000_000, k["oi"].to_numpy(float))
            tm, oi = cache[coin]
            i1 = np.searchsorted(tm, t_min, side="right") - 1
            i0 = np.searchsorted(tm, t_min - 60, side="right") - 1
            if i0 < 0 or i1 < 0 or oi[i0] <= 0:
                return NAN
            return float(oi[i1] / oi[i0] - 1)
        except Exception:
            return NAN
    return f


HYPE_LABEL = ("short history, perpetual-index proxy, no verdict; levels from the index through Saturday (d0 - 1), "
              "§6.1")


def _hype_world(ctx: Ctx, k: pd.DataFrame | None = None, end: str | None = None) -> dict | None:
    """HYPE on its perpetual's index price (§5): an injected world built from the cached 1m index months (prices as
    bars, index updates as trades, no volume), HYPE a member of U_Q1 and U_B in every month it has (exploratory,
    "short history, perpetual-index proxy, no verdict"). Tick 0.001 (HYPEUSDT perpetual). The level inputs (P0,
    sigma30, ATR14) read the index's daily bars lagged one day, so a Monday placement sees the index only through
    Saturday (§6.1: futures-based inputs, HYPE's index included, use data through d0 - 1; coding choice 17); fills,
    exits and twins trade on the 1m index itself. k: 1m index klines (open_time, open, high, low, close, updates);
    default the cached months."""
    from analysis_2026 import stinkbid_data as sbd
    end = end or sbd.END
    if k is None:
        d = sbd.OUT / "fut1m" / "index" / "HYPE"
        fs = sorted(d.glob("*.parquet")) if d.exists() else []
        if not fs:
            return None
        k = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    if not len(k):
        return None
    k = k.copy()
    k["open_time"] = pd.to_datetime(k["open_time"], utc=True)
    k = k.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
    m1 = pd.DataFrame({"open_time": k["open_time"], "open": k["open"], "high": k["high"], "low": k["low"],
                       "close": k["close"], "volume": 0.0, "quote_volume": 0.0,
                       "trades": k["updates"].astype(np.int32), "taker_buy_quote": 0.0})
    # daily index bars labelled one day later: the row of day d holds day d - 1's bar, so stinkbid_levels' "spot
    # through d0" reads the index through d0 - 1 (the levels apply their own §4.1 boundary rule: no seg column)
    lag = _engine()._daily_from_m1(m1).drop(columns=["seg"], errors="ignore")
    lag["open_time"] = lag["open_time"] + pd.Timedelta("1D")
    months = m1["open_time"].dt.strftime("%Y-%m").unique()
    u = pd.DataFrame([dict(month=m, coin="HYPE", U_Q1=True, U_B=True) for m in months])
    return dict(universe=u, coins={"HYPE": {"m1": m1, "tick": "0.001", "levels": {"d1": lag}}}, end=end, tbill=0.0)


def stage_explore(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "explore")
    started = _now()
    runs = runs_for(ctx, ANSWER_RUNS + DESC_RUNS + EXPLORE_RUNS)
    hype = dict(note="injected world: HYPE's index is not available") if ctx.injected else None
    if not ctx.injected:
        hw = _hype_world(ctx)
        if hw is None:
            hype = dict(note="HYPE index months not cached (run the data stage)")
        else:
            sbe = _engine()
            res = sbe.run_program("P1", "U_Q1", data=hw, cfg=dict(rules=("F1",), exits={"F1": (sbe.FLIP,)},
                                                                  twin_sens=False, drift=False,
                                                                  verbose=ctx.verbose))
            hype = dict(res=res, label=HYPE_LABEL)
    T = sbdesc.explore_tables(runs, metrics_fn=_metrics_fn(ctx), B=ctx.B, hype=hype)
    written = sbdesc.write_tables(ctx.out / "explore", T, "Stink bids: exploratory splits (STINKBID_PREREG.md "
                                  f"§10.4; BH within each table; no verdict) [{ctx.mode}]")
    # what the sheet needs (§13): verdicts, earned items, fill odds inputs
    ans = _jload(ctx.out / "answer.json", {})
    dj = _jload(ctx.out / "desc" / "desc.json", {})
    dg = T.get("depth_gradient")
    grad = dg[dg["is_gradient"].fillna(False).astype(bool) & (dg["rule"] == "F1" if "rule" in dg else True)] \
        if isinstance(dg, pd.DataFrame) and len(dg) and "is_gradient" in dg else pd.DataFrame()
    fam = dj.get("d10_family") or []
    si = dict(mode=ctx.mode, generated=_now(), verdicts=ans.get("verdicts"), flags=ans.get("flags"),
              tests_passed=ans.get("tests_passed"), h4=ans.get("h4"),
              d10_family=fam, chart_methods_by_d10=[r["test"] for r in fam if r.get("rejected") and r["test"] != "D9"],
              round_number_advice=bool(any(r.get("rejected") for r in fam if r.get("test") == "D9")),
              depth_gradient_q=sbdesc._f(grad["q_bh"].iloc[0]) if len(grad) else None,
              best_rung_allowed=bool(len(grad) and sbdesc._f(grad["q_bh"].iloc[0]) < 0.10),
              d6=dj.get("d6"), dh5=dj.get("dh5"), capacity=(ans.get("numbers") or {}).get("capacity"),
              fixed_sentences=ans.get("fixed_sentences"), recommendation=ans.get("recommendation"))
    _jdump(ctx.out / "sheet_inputs.json", si)
    written.append(str(ctx.out / "sheet_inputs.json"))
    info = dict(started=started, outputs=written, tables=sorted(T))
    write_marker(ctx, "explore", t0, info)
    ctx.log(f"explore: {len(T)} tables -> {ctx.out / 'explore'}; sheet inputs -> {ctx.out / 'sheet_inputs.json'}")
    return info


# ============================================================================ 8. sheet
def stage_sheet(ctx: Ctx) -> dict:
    t0 = _begin(ctx, "sheet")
    started = _now()
    if importlib.util.find_spec("analysis_2026.stinkbid_sheet") is None:
        raise StageRefused("sheet refuses: analysis_2026/stinkbid_sheet.py does not exist yet (the sheet agent's "
                           "module)")
    # in-process, on this run's OUT and CACHE (stinkbid_sheet coding choice 18): rc 2 = refused as a whole (nothing
    # written), rc 1 = every coin refused (written, an error here), rc 0 = written with at least one priced coin
    sbsheet = importlib.import_module("analysis_2026.stinkbid_sheet")
    sdir = ctx.out / "sheet"
    r = sbsheet.run_stage(ctx.out, ctx.cache, list(ctx.sheet_args), world=ctx.data, echo=ctx.verbose)
    if r.get("rc") == 2:
        raise StageRefused(f"sheet refuses: {r.get('why')}")
    outs = [str(p) for p in (r.get("outputs") or [])]
    if r.get("rc") != 0 or not outs:
        raise RuntimeError(f"sheet: rc {r.get('rc')} ({r.get('why')}); refused coins {r.get('refused')}; "
                           f"outputs {outs}")
    info = dict(started=started, outputs=outs, args=list(ctx.sheet_args), refused=r.get("refused"))
    write_marker(ctx, "sheet", t0, info)
    ctx.log(f"sheet: {', '.join(Path(p).name for p in outs)} -> {sdir}")
    return info


# ============================================================================ status
def status(ctx: Ctx) -> list:
    lines = [f"Stink-bid study stages ({ctx.mode}); results {ctx.out}; run cache {ctx.cache}"]
    nxt = None
    for s in STAGES:
        m = read_marker(ctx, s)
        if m is None:
            st = "not run"
        elif m.get("mode") != ctx.mode:
            st = f"ran in mode {m.get('mode')} (not {ctx.mode})"
        else:
            st = f"complete {m.get('finished')} ({m.get('seconds')} s)"
            if s == "controls":
                st += f"; all_passed {m.get('all_passed')}"
        if nxt is None and not stage_complete(ctx, s):
            nxt = s
        lines.append(f"  {STAGES.index(s) + 1}. {s:9s} {st}")
    cg = controls_gate(ctx)
    lines.append(f"  controls gate: {'open' if cg['ok'] else 'closed: ' + cg['why']}")
    lines.append(f"  next stage: {nxt or '(all complete; audit and write-up are §14 step 9)'}")
    dv = deviations(ctx)
    lines.append(f"  deviations logged: {len(dv)}")
    print("\n".join(lines))
    return lines


# ============================================================================ CLI
STAGE_FN = {"data": stage_data, "controls": stage_controls, "fcount": stage_fcount, "primary": stage_primary,
            "report": stage_report, "desc": stage_desc, "explore": stage_explore, "sheet": stage_sheet}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    rest = []
    if "--" in argv:
        i = argv.index("--")
        argv, rest = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(prog="stinkbid_run")
    ap.add_argument("stage", choices=STAGES + ("status", "selftest"))
    ap.add_argument("--out", default=str(RES))
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--B", type=int, default=sbs.B_BOOT)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--ub-f3", action="store_true", help="F3 rows on U-B too (whole index histories; ~36 GB bound)")
    a = ap.parse_args(argv)
    if a.stage == "selftest":
        return 0 if selftest() else 1
    ctx = Ctx(out=Path(a.out), cache=Path(a.cache), n_jobs=a.jobs, B=a.B, verbose=not a.quiet, rerun=a.rerun,
              reason=a.reason, sheet_args=rest, ub_f3=a.ub_f3)
    if a.stage == "status":
        status(ctx)
        return 0
    try:
        STAGE_FN[a.stage](ctx)
    except StageRefused as e:
        if (ctx.out / "stages").exists():
            _append_log(ctx, "log.jsonl", dict(event="refused", stage=a.stage, why=str(e)))
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    return 0


# ============================================================================ selftest
def _synthetic_world(seed: int = 5, days: int = 560, n_coins: int = 6) -> dict:
    """An injected world (stinkbid_engine.synth_world) with every universe column the plans use: U_B all coins;
    U_Q1 SYN0-3; U_Q1_12 SYN0-4; U_Q1_xm SYN0-2; U_A SYN1, SYN3, SYN5; U_C SYN0, SYN2, SYN4; T-bill 4%."""
    sbe = _engine()
    W = sbe.synth_world(n_coins=n_coins, days=days, start="2022-03-01", seed=seed, jumps_per_year=12)
    u = W["universe"]
    names = [f"SYN{i}" for i in range(n_coins)]
    u["U_Q1"] = u["coin"].isin(names[:4])
    u["U_Q1_12"] = u["coin"].isin(names[:5])
    u["U_Q1_xm"] = u["coin"].isin(names[:3])
    u["U_A"] = u["coin"].isin(names[1::2])
    u["U_C"] = u["coin"].isin(names[0::2])
    W["tbill"] = 4.0
    # market-wide days (data_inventory §6.1's leave-one-out rule, written here from the daily bars): a coin-day is
    # market-wide when at least 10% of the OTHER active coins had a low at or below 0.85 x the previous close
    flags = {}
    for c, fr in W["coins"].items():
        k = fr["m1"]
        k = k[k["trades"] > 0]
        dd = k.groupby(k["open_time"].dt.floor("D")).agg(low=("low", "min"), close=("close", "last"))
        cont = dd.index.to_series().diff() == pd.Timedelta("1D")
        pc = dd["close"].shift(1)
        flags[c] = pd.DataFrame({"hit": ((dd["low"] <= 0.85 * pc) & cont).astype(int),
                                 "act": (pc.notna() & cont).astype(int)})
    parts = []
    for c in flags:
        idx = flags[c].index
        H = sum(flags[o]["hit"].reindex(idx, fill_value=0) for o in flags if o != c)
        A = sum(flags[o]["act"].reindex(idx, fill_value=0) for o in flags if o != c)
        share = (H / A.where(A > 0)).to_numpy(float)
        parts.append(pd.DataFrame({"coin": c, "day": idx, "mw": (share >= 0.10).astype(float), "mw_share": share}))
    W["mw"] = pd.concat(parts, ignore_index=True)
    return W


def _toy_controls(all_passed: bool = True, calibrate: bool = True, reps: int = 24, B: int = 199):
    """A controls writer for the selftest: summary.json with all_passed and a K3 calibration from
    stinkbid_stats.inference_calibration on its toy simulator (synthetic; no market data)."""
    def fn(ctx: Ctx):
        cdir = ctx.out / "controls"
        cdir.mkdir(parents=True, exist_ok=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            C = sbs.inference_calibration(sbs._toy_k3_sim, n_reps=reps, B=B, n_jobs=1)
        if not calibrate:
            for t in C["tests"]:
                C["tests"][t]["needs_calibration"] = False
        _jdump(cdir / "k3_calibration.json", C)
        _jdump(cdir / "summary.json", dict(all_passed=all_passed, quick=False,
                                           K1=dict(K1c=dict(HOLD90=dict(engine_delta_RH=-0.012, engine_delta=-0.003))),
                                           note="synthetic selftest controls (not the study's controls)"))
        (cdir / "summary.txt").write_text("synthetic selftest controls\n")
    return fn


def _expected_keys(h2r, h1, h4, bot) -> list:
    """The answer map's truth table written separately from recommendation(): the expected keys in order."""
    tab_h2r = {"PASS": ["H2R_PASS"], "NO EDGE": ["H2R_NOEDGE"], "NO EDGE (HARMS)": ["H2R_NOEDGE", "H2R_HARMS_ADD"],
               "INCONCLUSIVE": ["H2R_INCONCLUSIVE"]}
    tab_h1 = {"PASS": ["H1_PASS"], "NO EDGE": ["H1_NOEDGE"], "NO EDGE (HARMS)": ["H1_NOEDGE", "H1_HARMS_ADD"],
              "INCONCLUSIVE": ["H1_INCONCLUSIVE"]}
    tab_h4 = {"PASS": ["H4_PASS"], "NO EDGE": ["H4_NOEDGE"], "NO EDGE (HARMS)": ["H4_NOEDGE"],
              "INCONCLUSIVE": ["H4_INCONCLUSIVE"]}
    return tab_h2r[h2r] + tab_h1[h1] + (["H1_BOT_ONLY"] if (bot and h1 != "PASS") else []) + tab_h4[h4]


def _t_answer_map(say) -> int:
    """Every verdict combination (4 x 4 x 4 x bot-only x Robinhood conditions) against the separately written truth
    table, with the sentences' content, the further rules and the wording rules."""
    V = ("PASS", "NO EDGE", "NO EDGE (HARMS)", "INCONCLUSIVE")
    nums = {"H2R": dict(X=0.031, lo=0.01, hi=0.05, N=812, G=41, gstar=11.3, M=0.012),
            "H1": dict(X=0.061, lo=0.02, hi=0.1, N=900, G=44, gstar=12.1, M=0.055, R=0.024),
            "H4": dict(X=0.015, lo=0.002, hi=0.03, N=3000, G=40, gstar=10.0, M=0.016, j="M5b")}
    mu = {6.0: 0.19, 8.0: 0.10, 10.0: 0.06}
    n = 0
    for h2r in V:
        for h1 in V:
            for h4 in V:
                for bot in (False, True):
                    v = {"H2R": h2r, "H1": h1, "H4": h4, "h1_bot_only": bot, "numbers": nums, "mu_star": mu}
                    rec = recommendation(v)
                    keys = [k for k, _ in rec]
                    exp = _expected_keys(h2r, h1, h4, bot)
                    assert keys == exp, (h2r, h1, h4, bot, keys, exp)
                    txt = " ".join(t for _, t in rec)
                    # targets: shown only for H1 PASS under rule M
                    assert ("The sheet shows the flip target" in txt) == (h1 == "PASS")
                    assert ("No flip target" in txt) == (h1 == "INCONCLUSIVE" or (bot and h1 != "PASS"))
                    assert ("which you cannot do by hand" in txt) == (bot and h1 != "PASS")
                    if h2r == "PASS":
                        assert "3.1%" in txt and "812 fills in 41 months" in txt and "k = 8: 10.0% a year" in txt
                    if h2r == "INCONCLUSIVE":
                        assert "an edge under about 1.2%" in txt
                    if h1 == "INCONCLUSIVE":
                        assert "about 5.5% per fill or more" in txt
                    if h1 == "PASS":
                        assert "by 6.1% per fill" in txt and "a flip made +2.4% on average" in txt
                    if h4 == "PASS":
                        assert "Method M5b's levels" in txt
                    low = txt.lower()
                    assert "does not work" not in low and "doesn't work" not in low
                    n += 1
    # the further rules: "You could run it on Robinhood" truth table
    m = 0
    P = dict(beside={"H1": {"U_C_F3": {"estimate": 0.0}}, "H2R": {"U_C_F3": {"estimate": 0.0}}})
    for h1 in V:
        for h2r in V:
            for acc in (False, True):
                for uc1 in (-0.01, 0.02):
                    for uc2 in (-0.01, 0.02):
                        P["beside"]["H1"]["U_C_F3"]["estimate"] = uc1
                        P["beside"]["H2R"]["U_C_F3"]["estimate"] = uc2
                        fl = dict(verdicts={"H1": h1, "H2R": h2r, "H4": "INCONCLUSIVE"})
                        r = run_on_robinhood(fl, P, dict(ok=acc, why="x"))
                        exp = acc and ((h1 == "PASS" and uc1 > 0) or (h2r == "PASS" and uc2 > 0))
                        assert r["ok"] == exp, (h1, h2r, acc, uc1, uc2, r)
                        m += 1
    # fixed sentences always printed, with their numbers
    fx = fixed_sentences(dict(worst_day=dict(share=0.95, day="2025-10-10", filled=95, live=100),
                              knife=dict(A=0.12, B=0.07, n=500),
                              moneyline=dict(red_share_of_defined=0.63, red=63, green=37, undefined=0),
                              capacity=[dict(rung=6.0, C_p10=200000.0, Q_max=50000.0)]))
    keys = [k for k, _ in fx]
    assert keys == ["DISCOUNT", "TAIL_TOGETHER", "TAIL_BOTTOM", "TAIL_NEWS", "MONEYLINE", "CAPACITY"], keys
    tx = dict(fx)
    assert "On the worst day, 95% of the live bids" in tx["TAIL_TOGETHER"]
    assert "12.0% of past fills" in tx["TAIL_BOTTOM"] and "against 7.0% for random buys" in tx["TAIL_BOTTOM"]
    assert "pre-October-2026 MoneyLine" in tx["MONEYLINE"] and "assume every rung fills on the same day" in \
        tx["CAPACITY"] and "$50,000" in tx["CAPACITY"]
    say(f"  answer map: {n} verdict combinations match the separately written truth table (order H2R, H1, H4; flip "
        f"target only on H1 PASS; bot-only sentence); 'You could run it on Robinhood' truth table {m} cases; the six "
        "fixed sentences with their numbers")
    return n


def _t_verdict_lines(say):
    """Verdict lines: NO EDGE says "not by E or more", INCONCLUSIVE "the data cannot tell" with the MDE, PASS with
    'a Binance-only result' when flagged; S16 names the episodes above 50%."""
    base = dict(test="H1", estimate=0.02, ci95_lo=-0.01, ci95_hi=0.05, n=100, G=20, gstar=8.2, unit="month-block",
                p_decide=0.2, p_holm=0.4, holm_level=0.025, holm_rejected=False, gates_ok=False, ub=0.06, mde=0.05,
                argmax=None, calibrated=False)
    flags = dict(binance_only={"H1": True}, index_dips_only=False)
    rb = dict(top3_above_half=True, top3_names=["2022-11-08..2022-11-10", "2025-10-10", "2021-05-19"],
              top3_basis="sum")
    s = verdict_line("H1", pd.Series(dict(base, verdict="NO EDGE", ub=0.03)), rb, flags, {})
    assert "Not by 3.75% per fill or more" in s and "More than half of the total came from three" in s
    s = verdict_line("H1", pd.Series(dict(base, verdict="NO EDGE (HARMS)", ub=-0.01)), {}, flags, {})
    assert "below zero" in s
    s = verdict_line("H1", pd.Series(dict(base, verdict="INCONCLUSIVE")), {}, flags, {})
    assert "The data cannot tell" in s and "5.0% per fill would not show" in s and "G* = 8.2" in s
    s = verdict_line("H1", pd.Series(dict(base, verdict="PASS", p_holm=0.01, gates_ok=True)), rb,
                     dict(flags, index_dips_only=True), {})
    assert "Binance-only result" in s and "only on brief index dips" in s and "it pays only if crashes" in s
    for t in ("H2R", "H4"):
        s = verdict_line(t, pd.Series(dict(base, test=t, verdict="NO EDGE", ub=0.001, argmax="M6")), {}, flags, {})
        assert f"Not by {E_TXT[t]} or more" in s
    say("  verdict lines: NO EDGE 'not by E or more', HARMS below zero, INCONCLUSIVE with the MDE, G and G*; "
        "Binance-only, index-dips and top-three-episode sentences")
    # "passes only at bot latency" follows the rule of every verdict (A1.8): a bot version that passes Holm and every
    # bot gate but whose 98.33% bound is below E is NO EDGE, so it is not "PASS" (review of Addendum 1, finding F1)
    fv = sbs.family_verdicts({"H1": dict(p_decide=0.3, ub=0.08, estimate=0.01),
                              "H2R": dict(p_decide=0.5, ub=0.05, estimate=0.0),
                              "H4": dict(p_decide=0.6, ub=0.03, estimate=0.0)},
                             gates={"H1": {"g": True}, "H2R": {"g": True}, "H4": {"g": True}})
    assert dict(zip(fv.test, fv.verdict))["H1"] == "INCONCLUSIVE"
    gates_ok = {"half1_pos": True, "half2_pos": True}
    P = dict(rows={"H2R": dict(p_decide=0.5), "H4": dict(p_decide=0.6)}, f3kept={},
             beside={"H1": {}}, bot=dict(row=dict(p_decide=0.001, ub=0.030, estimate=0.025), gates=gates_ok))
    fl = answer_flags(fv, P)
    assert fl["bot_p_holm"] < sbs.ALPHA and fl["bot_verdict"] == "NO EDGE", fl
    assert fl["bot_pass"] is False and fl["h1_bot_only"] is False, fl
    P["bot"]["row"]["ub"] = 0.06                                     # bound not below E = 3.75%: PASS
    fl = answer_flags(fv, P)
    assert fl["bot_verdict"] == "PASS" and fl["bot_pass"] is True and fl["h1_bot_only"] is True, fl
    P["bot"]["gates"] = dict(gates_ok, half2_pos=False)              # a failed bot gate: not PASS
    fl = answer_flags(fv, P)
    assert fl["bot_verdict"] == "INCONCLUSIVE" and fl["h1_bot_only"] is False, fl
    say("  bot latency: a bot version below E is NO EDGE, not 'passes only at bot latency'; PASS needs Holm, gates "
        "and a bound not below E")


# ---------------------------------------------------------------- known answers for primary_compute (review finding 1)
# Hand-built engine results with planted values, and an oracle written here (not with the module's helpers): the
# samples (rule F1, exit X-FLIP, cost C-RH, whole horizon observed), the means and every gate of H1, H2R and H4.
_KR_EPIS = (  # (half, [(UTC day, fills that day)]): 60 fills, 14 episodes, 13 month-blocks (e4 + e5 share 2022-02,
    # e9 spans 2023-10 and 2023-11 and merges them); e4 is the biggest episode (8 fills)
    (0, [("2020-06-10", 2), ("2020-06-11", 2)]), (0, [("2020-11-10", 2), ("2020-11-11", 2)]),
    (0, [("2021-04-10", 2), ("2021-04-11", 2)]), (0, [("2021-09-10", 2), ("2021-09-11", 2)]),
    (0, [("2022-02-02", 4), ("2022-02-03", 4)]), (0, [("2022-02-20", 2), ("2022-02-21", 2)]),
    (0, [("2022-07-10", 2), ("2022-07-11", 2)]), (1, [("2023-03-10", 2), ("2023-03-11", 2)]),
    (1, [("2023-08-10", 2), ("2023-08-11", 2)]), (1, [("2023-10-31", 2), ("2023-11-01", 2)]),
    (1, [("2024-01-10", 2), ("2024-01-11", 2)]), (1, [("2024-06-10", 2), ("2024-06-11", 2)]),
    (1, [("2025-01-10", 2), ("2025-01-11", 2)]), (1, [("2025-06-10", 2), ("2025-06-11", 2)]))
# the variants: which single gate the planted values break (None: every gate holds)
_KR_VARIANTS = {"all": None, "half2": "half2_pos", "half1": "half1_pos", "block": "no_worst_block_pos",
                "episode": "no_biggest_episode_pos", "r": "mean_r_pos", "ub": "u_b_pos", "f3": "f3_pos"}


def _kr_min(s: str) -> int:
    return int(pd.Timestamp(s, tz="UTC").value // 60_000_000_000)


def _kr_layout():
    """(fill minutes, episode index, half) of the 60 complete fills."""
    t, e, h = [], [], []
    for k, (half, days) in enumerate(_KR_EPIS):
        for day, n in days:
            for j in range(n):
                t.append(_kr_min(f"{day} {5 + 2 * j:02d}:17"))
                e.append(k)
                h.append(half)
    return np.array(t, np.int64), np.array(e), np.array(h)


def _kr_pattern(name: str, ep: np.ndarray, half: np.ndarray) -> np.ndarray:
    """Per-fill values (Delta for H1, a_f for H2R) that break exactly one of halves / worst block / biggest episode."""
    n = len(ep)
    if name == "half2":
        v = np.where(half == 0, 0.10, -0.01)
    elif name == "half1":
        v = np.where(half == 0, -0.01, 0.10)
    elif name == "block":                                 # 2023-08 (e8) carries everything; both halves stay > 0
        v = np.where(half == 0, 0.01, np.where(ep == 8, 1.0, -0.16))
    elif name == "episode":                               # e4 (biggest) +, e5 (same block) -: the block nets out
        v = np.where(ep == 4, 0.3, np.where(ep == 5, -0.5, 1.0 / 48))
    else:
        v = np.full(n, 0.02)
    return v + 0.004 * ((np.arange(n) % 5) - 2)           # jitter summing to zero over every five fills


def _kr_p1(variant: str, coin: str = "KRA") -> dict:
    """A hand-built P1 result: 60 complete F1 fills (+ 6 fills whose X-FLIP horizon is not observed), F3_1 / F3d_1 /
    F3_3 / F2 fills, outcome rows for (F1, FLIP, C-RH) and distractors (C-0, FLIP_bot, incomplete rows, F2), bench
    rows with a_f (alert_M) and distractors (alert_2h, F2)."""
    t, ep, half = _kr_layout()
    n = len(t)
    pat = "all" if variant in ("r", "ub", "f3", "all") else variant
    y = _kr_pattern(pat, ep, half)
    a = _kr_pattern(pat, ep, half) + 0.001
    r = np.full(n, -0.05) + 0.002 * (np.arange(n) % 3) if variant == "r" else y.copy()
    jit = 0.003 * ((np.arange(n) % 4) - 1.5)
    f3y = (-0.02 if variant == "f3" else 0.015) + jit
    f3a = (-0.02 if variant == "f3" else 0.016) + jit
    has3 = (np.arange(n) % 5) != 4                        # 48 fills also fill under F3 (s = 1%)
    has33 = (np.arange(n) % 3) != 2
    tx = np.r_[t, _kr_min("2025-09-10 06:00") + np.arange(6) * 60]      # 6 fills with an unobserved horizon
    N = len(tx)
    F = pd.DataFrame(dict(fill_id=np.arange(N), bid_id=np.arange(N), coin=coin, rung=6.0, variant="M2 k=6",
                          real=True, delta=6.0, L=1.0, P0=1.5, month=0, t_F1=tx, t_F2=tx,
                          t_F3_1=np.r_[np.where(has3, t, -1), np.full(6, -1)],
                          t_F3d_1=np.r_[np.where(has3, t, -1), np.full(6, -1)],
                          t_F3_3=np.r_[np.where(has33, t, -1), np.full(6, -1)]))
    O = []

    def add(rule, ex, cost, ids, delta, rr=None, complete=True):
        ids = np.asarray(ids)
        dd = np.broadcast_to(np.asarray(delta, float), ids.shape)
        r_ = dd if rr is None else np.broadcast_to(np.asarray(rr, float), ids.shape)
        O.append(pd.DataFrame(dict(fill_id=ids, coin=coin, rule=rule, exit=ex, lat="M", cost=cost, r=r_,
                                   twin_mean=r_ - dd, delta=dd, complete=complete)))
    ids = np.arange(n)
    add("F1", "FLIP", "C-RH", ids, y, r)
    add("F1", "FLIP", "C-RH", np.arange(n, N), 7.0, complete=False)              # horizon not observed: left out
    add("F1", "FLIP", "C-0", ids, y + 5.0, r + 5.0)                             # gross cost: never the H1 sample
    add("F1", "FLIP_bot", "C-RH", ids, y + 0.01, r + 0.01)
    add("F2", "FLIP", "C-RH", ids, -3.0)
    add("F3_1", "FLIP", "RH", ids[has3], f3y[has3])
    add("F3_1", "FLIP_bot", "RH", ids[has3], f3y[has3] + 0.01)
    add("F3d_1", "FLIP", "RH", ids[has3], 0.011 + jit[has3])
    add("F3_3", "FLIP", "RH", ids[has33], 0.007 + jit[has33])
    Bn = pd.concat([pd.DataFrame(dict(fill_id=ids, coin=coin, rule="F1", alert_M=a, alert_2h=-9.0)),
                    pd.DataFrame(dict(fill_id=np.arange(n, N), coin=coin, rule="F1", alert_M=np.nan, alert_2h=-9.0)),
                    pd.DataFrame(dict(fill_id=ids[has3], coin=coin, rule="F3_1", alert_M=f3a[has3], alert_2h=9.0)),
                    pd.DataFrame(dict(fill_id=ids[has3], coin=coin, rule="F3d_1", alert_M=0.012, alert_2h=9.0)),
                    pd.DataFrame(dict(fill_id=ids[has33], coin=coin, rule="F3_3", alert_M=0.008, alert_2h=9.0)),
                    pd.DataFrame(dict(fill_id=ids, coin=coin, rule="F2", alert_M=9.0, alert_2h=9.0))],
                   ignore_index=True)
    return dict(fills=F, outcomes=pd.concat(O, ignore_index=True), bench=Bn, bids=F[["bid_id", "coin", "rung"]],
                program="P1", universe="U_Q1", meta={})


def _kr_ub(variant: str) -> dict:
    """U-B's hand-built result: the same layout, Delta and a_f negative only in the 'ub' variant."""
    res = _kr_p1("all", coin="KRB")
    O, Bn = res["outcomes"], res["bench"]
    s = -1.0 if variant == "ub" else 1.0
    m = (O["rule"] == "F1") & (O["cost"] == "C-RH") & O["complete"].astype(bool)
    O.loc[m, "delta"] = s * O.loc[m, "delta"].abs()
    O.loc[m, "r"] = O.loc[m, "delta"]
    b = Bn["rule"] == "F1"
    Bn.loc[b, "alert_M"] = s * Bn.loc[b, "alert_M"].abs()
    return res


def _kr_uc() -> dict:
    res = _kr_p1("all", coin="KRC")
    O, Bn = res["outcomes"], res["bench"]
    O.loc[(O["rule"] == "F1") & (O["exit"] == "FLIP") & (O["cost"] == "C-RH"), "delta"] += 0.01
    O.loc[(O["rule"] == "F3_1") & (O["exit"] == "FLIP"), "delta"] += 0.02
    Bn.loc[Bn["rule"] == "F3_1", "alert_M"] += 0.03
    return res


_KR_H4_MONTHS = ("2020-03", "2020-08", "2021-01", "2021-06", "2022-01",
                 "2023-02", "2023-07", "2024-02", "2024-08", "2025-03")


def _kr_h4(variant: str = "all") -> tuple:
    """A hand-built H4 result: four chart methods, 40 coin-weeks (4 per month on days 3 / 10 / 17 / 24, so episodes
    stay inside a month and month-blocks are the months), each with its real level and four placebos (all filled);
    Delta = alpha_cw + b_j real + 0.003 (delta_f - delta_real) + noise; distractor rows at C-0, at FLIP_bot and with
    an unobserved horizon. M5b is the argmax (the other methods have b < 0). Returns (res, planted frames)."""
    rng = np.random.default_rng(7)
    bj = {"M4": -0.005, "M6": -0.01, "M7": -0.02}
    names = {"M4": "M4 N=90 buffer=0.5", "M5b": "M5b", "M6": "M6", "M7": "M7"}
    shifts = (0.0, -1.0, -0.5, 0.5, 1.0)
    bids, fills, outs = [], [], []
    fid = 0
    for k in range(40):
        month = _KR_H4_MONTHS[k // 4]
        tf = _kr_min(f"{month}-{3 + 7 * (k % 4):02d} 06:00")
        half = int(month >= "2023")
        if variant == "h4_half2":
            b5 = 0.05 if half == 0 else -0.02
        elif variant == "h4_block":
            b5 = 0.005 if half == 0 else (0.5 if month == "2024-02" else -0.12)
        else:
            b5 = 0.03
        b3 = -0.02 if variant == "h4_f3" else 0.02
        alpha = 0.05 * math.sin(k)
        dreal = 8.0 + 0.1 * (k % 7)
        for m in ("M4", "M5b", "M6", "M7"):
            cw = f"KRH|{k}"
            for s_ in shifts:
                real = s_ == 0.0
                dep = dreal - 0.6 * s_
                bids.append(dict(bid_id=fid, variant=names[m], cw=cw, delta=dep, real=real, shift=s_, coin="KRH"))
                b_ = b5 if m == "M5b" else bj[m]
                y = alpha + b_ * real + 0.003 * (dep - dreal) + 0.001 * rng.standard_normal()
                y3 = alpha + (b3 if m == "M5b" else bj[m]) * real + 0.003 * (dep - dreal) + \
                    0.001 * rng.standard_normal()
                t3 = tf + fid % 7 if not (s_ == -1.0 and k % 2) else -1        # some placebos never fill on F3
                fills.append(dict(fill_id=fid, bid_id=fid, coin="KRH", variant=names[m], cw=cw, delta=dep, real=real,
                                  shift=s_, t_F1=tf + fid % 7, t_F3_1=t3, rung=0.0))
                inc = bool(real and k == 0)                                  # the horizon is not observed
                outs += [dict(fill_id=fid, rule="F1", exit="FLIP", cost="C-RH", complete=not inc,
                              delta=y + (9.0 if inc else 0.0)),
                         dict(fill_id=fid, rule="F1", exit="FLIP", cost="C-0", complete=True, delta=y + 1.0 * real),
                         dict(fill_id=fid, rule="F1", exit="FLIP_bot", cost="C-RH", complete=True,
                              delta=y + 0.5 * real)]
                if t3 >= 0:
                    outs.append(dict(fill_id=fid, rule="F3_1", exit="FLIP", cost="RH", complete=True, delta=y3))
                fid += 1
    O = pd.DataFrame(outs)
    O["coin"], O["lat"] = "KRH", "M"
    O["r"] = O["delta"]
    res = dict(bids=pd.DataFrame(bids), fills=pd.DataFrame(fills), outcomes=O, bench=pd.DataFrame(),
               program="H4", universe="U_Q1", meta={})
    return res


def _kr_frames(res: dict, rule: str, cost: str, keep_ids=None) -> dict:
    """The oracle's stacked frames, built here from the planted rows (not with stinkbid_engine.h4_frames)."""
    F, O, B = res["fills"], res["outcomes"], res["bids"]
    o = O[(O["rule"] == rule) & (O["exit"] == "FLIP") & (O["cost"] == cost) & O["complete"].astype(bool)]
    f = F[F["t_" + rule] >= 0].merge(o[["fill_id", "delta"]].rename(columns={"delta": "y"}), on="fill_id")
    if keep_ids is not None:
        f = f[f["fill_id"].isin(keep_ids)]
    dr = B[B["real"]].set_index(["variant", "cw"])["delta"]
    f = f.assign(depth=f["delta"].to_numpy() - dr.reindex(pd.MultiIndex.from_frame(f[["variant", "cw"]])).to_numpy(),
                 month=pd.to_datetime(f["t_" + rule] * 60_000_000_000, utc=True).dt.strftime("%Y-%m"))
    inv = {"M4 N=90 buffer=0.5": "M4", "M5b": "M5b", "M6": "M6", "M7": "M7"}
    return {inv[v]: g.reset_index(drop=True) for v, g in f.groupby("variant")}


def _kr_b(fr: pd.DataFrame, mask=None) -> float:
    """b of y = alpha_cw + b real + c depth by least squares with coin-week dummies (the oracle)."""
    g = fr if mask is None else fr[np.asarray(mask, bool)]
    cws = sorted(g["cw"].unique())
    D = (g["cw"].to_numpy()[:, None] == np.array(cws)[None, :]).astype(float)
    X = np.column_stack([g["real"].astype(float).to_numpy(), g["depth"].to_numpy(float), D])
    return float(np.linalg.lstsq(X, g["y"].to_numpy(float), rcond=None)[0][0])


def _kr_oracle_blocks(days) -> tuple:
    """(episode, month-block) per fill, written here: episodes are runs of fill days at most 3 days apart; months are
    merged (transitively) when an episode has fills in both."""
    days = [pd.Timestamp(d).normalize() for d in days]
    ud = sorted(set(days))
    epd, e, prev = {}, -1, None
    for d in ud:
        if prev is None or (d - prev).days > 3:
            e += 1
        epd[d] = e
        prev = d
    ep = [epd[d] for d in days]
    mon = [(d.year, d.month) for d in days]
    parent = {m: m for m in set(mon)}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for e_ in set(ep):
        ms = sorted({mon[i] for i in range(len(days)) if ep[i] == e_})
        for x, z in zip(ms[:-1], ms[1:]):
            rx, rz = find(x), find(z)
            if rx != rz:
                parent[max(rx, rz)] = min(rx, rz)
    return np.array(ep), np.array([find(m)[0] * 100 + find(m)[1] for m in mon])


def _kr_oracle_gates(y, days, r=None, ub=None, f3=None) -> dict:
    y = np.asarray(y, float)
    ep, blk = _kr_oracle_blocks(days)
    half = np.array([pd.Timestamp(d) >= pd.Timestamp("2023-01-01") for d in days])
    g = {}
    if r is not None:
        g["mean_r_pos"] = bool(np.mean(r) > 0)
    g["half1_pos"] = bool(y[~half].mean() > 0)
    g["half2_pos"] = bool(y[half].mean() > 0)
    g["no_worst_block_pos"] = bool(min(y[blk != b].mean() for b in np.unique(blk)) > 0)
    cnt = {e: int((ep == e).sum()) for e in np.unique(ep)}
    big = sorted(cnt, key=lambda e: (-cnt[e], e))[0]                   # most fills; ties: the earliest
    g["no_biggest_episode_pos"] = bool(y[ep != big].mean() > 0)
    g["u_b_pos"] = bool(np.mean(ub) > 0)
    g["f3_pos"] = bool(np.mean(f3) > 0)
    return g


def _t_primary_known(say) -> int:
    """primary_compute on hand-built results (review finding 1): H1 / H2R estimates equal the means of the intended
    samples (F1, X-FLIP, C-RH, horizon observed; a_f = alert_M on F1), every gate equals the oracle, and in each
    variant exactly the planted gate fails; H4's per-method b, argmax, gates (halves, worst block, F3) and F3-kept
    estimate equal least-squares oracles on frames built here."""
    ctx = Ctx(B=99, verbose=False)
    t, ep, half = _kr_layout()
    days = list(pd.to_datetime(t * 60_000_000_000, utc=True).tz_localize(None))
    has3 = (np.arange(len(t)) % 5) != 4
    H4_all = _kr_h4("all")
    UC = _kr_uc()
    n_checked = 0
    for v, broken in _KR_VARIANTS.items():
        P, UB = _kr_p1(v), _kr_ub(v)
        out = primary_compute({"P1/U_Q1": P, "P1/U_B": UB, "H4/U_Q1": H4_all, "P1/U_C": UC}, None, ctx)
        O, Bn = P["outcomes"], P["bench"]
        s1 = O[(O["rule"] == "F1") & (O["exit"] == "FLIP") & (O["cost"] == "C-RH") & O["complete"].astype(bool)]
        s1 = s1.sort_values("fill_id")
        y1, r1 = s1["delta"].to_numpy(float), s1["r"].to_numpy(float)
        a1 = Bn[(Bn["rule"] == "F1") & Bn["alert_M"].notna()].sort_values("fill_id")["alert_M"].to_numpy(float)
        f3d = O[(O["rule"] == "F3_1") & (O["exit"] == "FLIP")]["delta"].to_numpy(float)
        f3a = Bn[Bn["rule"] == "F3_1"]["alert_M"].to_numpy(float)
        Ou, Bu = UB["outcomes"], UB["bench"]
        ubd = Ou[(Ou["rule"] == "F1") & (Ou["exit"] == "FLIP") & (Ou["cost"] == "C-RH") &
                 Ou["complete"].astype(bool)]["delta"].to_numpy(float)
        uba = Bu[(Bu["rule"] == "F1") & Bu["alert_M"].notna()]["alert_M"].to_numpy(float)
        # the samples and the estimates
        R1, R2 = out["rows"]["H1"], out["rows"]["H2R"]
        assert R1["n"] == len(y1) == 60 and math.isclose(R1["estimate"], y1.mean(), rel_tol=0, abs_tol=1e-12), \
            (v, R1["n"], R1["estimate"], y1.mean())
        assert R2["n"] == len(a1) == 60 and math.isclose(R2["estimate"], a1.mean(), abs_tol=1e-12), (v, R2)
        assert np.isfinite(R1["p_decide"]) and np.isfinite(R2["p_decide"]) and R1["unit"] == "month-block"
        assert math.isclose(out["beside"]["H1"]["mean_r"], r1.mean(), abs_tol=1e-12)
        assert math.isclose(out["bot"]["row"]["estimate"], (y1 + 0.01).mean(), abs_tol=1e-12)
        assert math.isclose(out["f3kept"]["H1"]["estimate"], y1[has3].mean(), abs_tol=1e-12)
        assert math.isclose(out["f3kept"]["H2R"]["estimate"], a1[has3].mean(), abs_tol=1e-12)
        for k, val in (("F3_1", f3d.mean()), ("U_B", ubd.mean()), ("F3d_1", None), ("F3_3", None)):
            got = out["beside"]["H1"][k]["estimate"]
            exp = val if val is not None else O[(O["rule"] == k) & (O["exit"] == "FLIP")]["delta"].mean()
            assert math.isclose(got, exp, abs_tol=1e-12), (v, k, got, exp)
        for k in ("F3_1", "F3d_1", "F3_3"):
            assert math.isclose(out["beside"]["H2R"][k]["estimate"], Bn[Bn["rule"] == k]["alert_M"].mean(),
                                abs_tol=1e-12), (v, k)
        Ouc = UC["outcomes"]
        assert math.isclose(out["beside"]["H1"]["U_C"]["estimate"], Ouc[(Ouc["rule"] == "F1") & (
            Ouc["exit"] == "FLIP") & (Ouc["cost"] == "C-RH") & Ouc["complete"].astype(bool)]["delta"].mean(),
            abs_tol=1e-12)
        assert math.isclose(out["beside"]["H2R"]["U_C_F3"]["estimate"],
                            UC["bench"].query("rule == 'F3_1'")["alert_M"].mean(), abs_tol=1e-12)
        # every gate against the oracle; exactly the planted gate fails
        o1 = _kr_oracle_gates(y1, days, r=r1, ub=ubd, f3=f3d)
        o2 = _kr_oracle_gates(a1, days, ub=uba, f3=f3a)
        assert out["gates"]["H1"] == o1, (v, out["gates"]["H1"], o1)
        assert out["gates"]["H2R"] == o2, (v, out["gates"]["H2R"], o2)
        assert {k for k, x in o1.items() if not x} == ({broken} if broken else set()), (v, o1)
        assert {k for k, x in o2.items() if not x} == ({broken} if broken and broken != "mean_r_pos" else set()), \
            (v, o2)
        sb = O[(O["rule"] == "F1") & (O["exit"] == "FLIP_bot") & (O["cost"] == "C-RH") &
               O["complete"].astype(bool)].sort_values("fill_id")
        ubb = Ou[(Ou["rule"] == "F1") & (Ou["exit"] == "FLIP_bot") & (Ou["cost"] == "C-RH")]["delta"].to_numpy(float)
        f3b = O[(O["rule"] == "F3_1") & (O["exit"] == "FLIP_bot")]["delta"].to_numpy(float)
        ob = _kr_oracle_gates(sb["delta"].to_numpy(float), days, r=sb["r"].to_numpy(float), ub=ubb, f3=f3b)
        assert out["bot"]["gates"] == ob, (v, out["bot"]["gates"], ob)
        n_checked += 1
    # H4: per-method b, argmax, gates and the F3-kept estimate against least-squares oracles
    for v, broken in (("all", None), ("h4_half2", "half2_pos"), ("h4_block", "no_worst_block_pos"),
                      ("h4_f3", "f3_pos")):
        H4 = _kr_h4(v)
        out = primary_compute({"P1/U_Q1": _kr_p1("all"), "P1/U_B": _kr_ub("all"), "H4/U_Q1": H4, "P1/U_C": UC},
                              None, ctx)
        fr = _kr_frames(H4, "F1", "C-RH")
        f3 = _kr_frames(H4, "F3_1", "RH")
        R4 = out["rows"]["H4"]
        tab = R4["methods"].set_index("method")
        for m in ("M4", "M5b", "M6", "M7"):
            assert math.isclose(tab.loc[m, "b"], _kr_b(fr[m]), abs_tol=1e-10), (v, m, tab.loc[m, "b"], _kr_b(fr[m]))
            assert tab.loc[m, "n"] == len(fr[m])
        assert R4["argmax"] == "M5b" and math.isclose(R4["estimate"], _kr_b(fr["M5b"]), abs_tol=1e-10), (v, R4)
        g5 = fr["M5b"]
        hv = g5["month"].to_numpy() >= "2023"
        og = dict(half1_pos=_kr_b(g5, ~hv) > 0, half2_pos=_kr_b(g5, hv) > 0,
                  no_worst_block_pos=min(_kr_b(g5, g5["month"] != mo) for mo in g5["month"].unique()) > 0,
                  f3_pos=_kr_b(f3["M5b"]) > 0)
        assert out["gates"]["H4"] == og, (v, out["gates"]["H4"], og)
        assert {k for k, x in og.items() if not x} == ({broken} if broken else set()), (v, og)
        kept = H4["fills"].loc[H4["fills"]["t_F3_1"] >= 0, "fill_id"].to_numpy()
        fk = _kr_frames(H4, "F1", "C-RH", keep_ids=kept)
        assert len(fk["M5b"]) < len(fr["M5b"]) and out["f3kept"]["H4"]["argmax"] == "M5b"
        assert math.isclose(out["f3kept"]["H4"]["estimate"], _kr_b(fk["M5b"]), abs_tol=1e-10), v
        assert math.isclose(out["beside"]["H4"]["F3_1"]["estimate"], _kr_b(f3["M5b"]), abs_tol=1e-10), v
        n_checked += 1
    say(f"  primary known answers: {n_checked} hand-built cases; H1 / H2R estimates are the means of the intended "
        "samples (F1, X-FLIP, C-RH, horizon observed; alert_M on F1; distractors at C-0, FLIP_bot, F2 and unobserved "
        "horizons left out); every gate of H1, H2R, the bot row and H4 equals an oracle written here, and each "
        "variant breaks exactly its planted gate; H4's b, argmax and F3-kept estimate equal least squares")
    return n_checked


def _t_review_units(say):
    """Regressions for review findings 3 (aggTrades only where capacity is reported), 5 (HYPE's levels from the index
    through d0 - 1), 6 (fcount with a program that has bids but no fill) and 9 (H1's E sensitivity)."""
    sbe = _engine()
    # (3) capacity modes: 'auto' (aggTrades on real U-Q1) only for P1 on U-Q1, C1 for every other run and stage
    for injected in (False, True):
        cx = Ctx(data={} if injected else None, n_jobs=1, verbose=False)
        for prog, univ, plan in FCOUNT_RUNS:
            for co in (False, True):
                c = plan_cfg(plan, univ, cx, counts_only=co, rules=("F1",) if co else None, prog=prog)
                assert c["capacity"] == ("auto" if (prog, univ) == ("P1", "U_Q1") else "c1"), (prog, univ, co, c)
    full = plan_cfg("full", "U_Q1", Ctx(n_jobs=1, verbose=False), prog="P1")
    assert sbe.THETA in full["exits"]["F3_1"] and sbe.THETA in full["exits"]["F1"]
    s1 = _sig("P1", "U_Q1", "full", False, Ctx(), None, full)
    s2 = _sig("P1", "U_Q1", "full", False, Ctx(), None, dict(full, capacity="c1"))
    assert s1 != s2, "the run cache's signature must change with the capacity mode"
    src = inspect.getsource(stage_data)
    assert 'cfg["capacity"] = "auto"' not in src and "prog=prog" in src
    # (6) fcount: a program with bids but no fill next to one with fills
    b0 = pd.DataFrame(dict(bid_id=[0, 1], coin="X", variant="M2 k=6", real=True, rung=6.0))
    r0, _ = fill_counts(dict(bids=b0, fills=pd.DataFrame(columns=["bid_id", "t_F1"])), "P1-90", "U_Q1")
    assert r0[0]["months"] == 0 and r0[0]["episodes"] == 0 and r0[0]["fills"] == 0, r0[0]
    tf = _kr_min("2022-05-10 06:00")
    f1 = pd.DataFrame(dict(bid_id=[0], coin="X", variant="M2 k=6", real=True, rung=6.0, t_F1=[tf]))
    r1, _ = fill_counts(dict(bids=b0, fills=f1), "P1", "U_Q1")
    txt = fcount_text(pd.DataFrame(r0 + r1 + [dict(program="M8", universe="U_Q1", variant="(none)", real=True,
                                                   rule="F1", bids=0, fills=0)]), "injected:selftest")
    assert "P1-90" in txt and "months   0" in txt and "M8" in txt and "no bid placed" in txt, txt
    # (9) H1 with E = 2.26% (r_res = 3.35%): the same p, gates and bound, never the primary verdict
    for ub, ph, gok, v_main, v_sens in ((0.03, 0.3, False, "NO EDGE", "INCONCLUSIVE"),
                                        (0.02, 0.3, False, "NO EDGE", "NO EDGE"),
                                        (-0.01, 0.3, False, "NO EDGE (HARMS)", "NO EDGE (HARMS)"),
                                        (0.05, 0.3, False, "INCONCLUSIVE", "INCONCLUSIVE"),
                                        (0.03, 0.01, True, "NO EDGE", "PASS"),        # A1.8: below E = 3.75%
                                        (0.05, 0.01, True, "PASS", "PASS")):
        fv = pd.DataFrame([dict(test="H1", p_holm=ph, gates_ok=gok, ub=ub, verdict=v_main)])
        assert sbs.verdict(ph, gok, ub, E["H1"]) == v_main
        es = e_sensitivity(fv)
        assert es["verdict"] == v_sens and es["E"] == sbs.E_SENS["H1_gold"] == 0.0226 and \
            es["primary_verdict"] == v_main, (ub, es)
        assert "2.26%" in es["text"] and ("not by 2.26% or more" in es["text"]) == v_sens.startswith("NO EDGE")
    # (5) HYPE: a synthetic 1m index; every bid's P0 is the index close of Saturday (d0 - 1), not Sunday's
    W = sbe.synth_world(n_coins=1, days=150, start="2025-06-01", seed=11, jumps_per_year=12)
    k = W["coins"]["SYN0"]["m1"]
    k = pd.DataFrame({"open_time": k["open_time"], "open": k["open"] * 3, "high": k["high"] * 3, "low": k["low"] * 3,
                      "close": k["close"] * 3, "updates": np.where(k["trades"].to_numpy() > 0, 60, 0)})
    end = str(k["open_time"].iloc[-1].date())
    hw = _hype_world(Ctx(verbose=False), k=k, end=end)
    res = sbe.run_program("P1", "U_Q1", data=hw, cfg=dict(counts_only=True, rules=("F1",), capacity="c1",
                                                          verbose=False, mw=False, ml=False, usd=False))
    bids = res["bids"].drop_duplicates("t0")
    kk = k[k["updates"] > 0]
    close = kk.groupby(kk["open_time"].dt.floor("D"))["close"].last()
    t0 = pd.to_datetime(bids["t0"].to_numpy(np.int64) * 60_000_000_000, utc=True)
    sat = close.reindex(t0.floor("D") - pd.Timedelta("2D")).to_numpy(float)
    sun = close.reindex(t0.floor("D") - pd.Timedelta("1D")).to_numpy(float)
    P0 = bids["P0"].to_numpy(float)
    assert len(P0) >= 8 and np.allclose(P0, sat, rtol=0, atol=1e-12), (P0[:4], sat[:4], sun[:4])
    assert not np.allclose(P0, sun), "HYPE's P0 still reads Sunday's index close"
    say(f"  units: capacity 'auto' only for P1/U_Q1 ({len(FCOUNT_RUNS) - 1} other runs on C1; the cache signature "
        f"carries it; TH72 on F3_1 in the full plan); fcount text with a zero-fill program; H1's E sensitivity at "
        f"2.26% (5 cases); HYPE's P0 = Saturday's index close at all {len(P0)} placements")


def _t_gating(say, W: dict, out: Path, cache: Path) -> Ctx:
    """Refusals: each stage before its predecessor; a failed control stops the study; fcount with outcomes present;
    primary without fcount; a rerun without --rerun; the controls gate's strictness."""
    ctx = Ctx(out=out, cache=cache, data=W, label="selftest", n_jobs=1, B=999, verbose=False)
    for st in ("controls", "fcount", "primary", "report", "desc", "explore", "sheet"):
        try:
            STAGE_FN[st](ctx)
            raise AssertionError(f"{st} ran before its previous stage")
        except StageRefused as e:
            assert "previous stage" in str(e), e
    stage_data(ctx)
    try:
        stage_data(ctx)
        raise AssertionError("data ran twice without --rerun")
    except StageRefused as e:
        assert "--rerun" in str(e)
    for st in ("fcount", "primary"):
        try:
            STAGE_FN[st](ctx)
            raise AssertionError(f"{st} ran before the controls")
        except StageRefused:
            pass
    # a failed control: the controls stage completes, every later stage refuses
    ctx.controls_fn = _toy_controls(all_passed=False, reps=8, B=99)
    stage_controls(ctx)
    assert stage_complete(ctx, "controls") and read_marker(ctx, "controls")["all_passed"] is False
    for st in ("fcount", "primary", "report"):
        try:
            STAGE_FN[st](ctx)
            raise AssertionError(f"{st} ran after a failed control")
        except StageRefused as e:
            assert "all_passed" in str(e) or "previous stage" in str(e), e
    # review finding 2: replacing summary.json after the failed run (e.g. by the controls module's own CLI after a
    # fix) does not reopen the gate: the marker recorded all_passed false and the hashes of the controls' files; only
    # a logged `controls --rerun` does
    S0 = _jload(out / "controls" / "summary.json")
    _jdump(out / "controls" / "summary.json", dict(S0, all_passed=True))
    assert controls_status(ctx)["ok"], controls_status(ctx)["why"]          # the replaced file alone would pass
    nd = len(deviations(ctx))
    try:
        stage_fcount(ctx)
        raise AssertionError("fcount ran after summary.json was replaced without a controls rerun")
    except StageRefused as e:
        assert "recorded all_passed = False" in str(e) and "--rerun" in str(e), e
    assert len(deviations(ctx)) == nd and not stage_complete(ctx, "fcount")
    _jdump(out / "controls" / "summary.json", S0)
    # strictness of the gate: not true, quick, no calibration
    S = _jload(out / "controls" / "summary.json")
    for bad, frag in ((dict(S, all_passed="true"), "not true"), (dict(S, all_passed=True, quick=True), "quick"),):
        _jdump(out / "controls" / "summary.json", bad)
        assert frag in controls_status(ctx)["why"], controls_status(ctx)
    kc = out / "controls" / "k3_calibration.json"
    kc_b = kc.read_text()
    kc.unlink()
    _jdump(out / "controls" / "summary.json", dict(S, all_passed=True))
    assert "K3 calibration" in controls_status(ctx)["why"]
    kc.write_text(kc_b)
    # rerun the controls with passing controls: --rerun required, logged as a deviation
    ctx.controls_fn = _toy_controls(all_passed=True, reps=24, B=199)
    try:
        stage_controls(ctx)
        raise AssertionError("controls reran without --rerun")
    except StageRefused:
        pass
    (out / "controls" / "summary.json").unlink()
    ctx.rerun, ctx.reason = True, "selftest: the first controls run failed on purpose"
    stage_controls(ctx)
    ctx.rerun = False
    assert controls_status(ctx)["ok"], controls_status(ctx)["why"]
    assert controls_gate(ctx)["ok"], controls_gate(ctx)["why"]
    assert any(d.get("stages") == ["controls"] for d in deviations(ctx))
    # a controls file changed after the passing run (here the K3 calibration) closes the gate until a rerun
    kb = kc.read_bytes()
    kc.write_bytes(kb + b" ")
    g = controls_gate(ctx)
    assert not g["ok"] and "changed" in g["why"] and "k3_calibration.json" in g["why"], g
    try:
        _begin(ctx, "fcount")
        raise AssertionError("fcount's gate opened with a changed K3 calibration")
    except StageRefused as e:
        assert "--rerun" in str(e), e
    kc.write_bytes(kb)
    assert controls_gate(ctx)["ok"], controls_gate(ctx)["why"]
    # primary refuses before fcount
    try:
        stage_primary(ctx)
        raise AssertionError("primary ran before fcount")
    except StageRefused as e:
        assert "previous stage" in str(e)
    # fcount refuses while an outcome run exists
    fake = cache / "outcomes" / "P1__U_Q1"
    fake.mkdir(parents=True, exist_ok=True)
    (fake / "done.json").write_text("{}")
    try:
        stage_fcount(ctx)
        raise AssertionError("fcount ran with outcomes present")
    except StageRefused as e:
        assert "outcome" in str(e)
    shutil.rmtree(cache / "outcomes")
    say("  gating: every stage refuses before its predecessor; a failed control stops fcount, primary and report, "
        "also after summary.json is replaced (the marker's all_passed and file hashes decide; no deviation logged); a "
        "changed K3 calibration closes the gate; the gate needs all_passed true (not 'true', not quick) and the K3 "
        "calibration; reruns need --rerun and are logged; fcount refuses while outcomes exist; primary refuses before "
        "fcount")
    return ctx


def _t_shapes(say, ctx: Ctx):
    out = ctx.out
    must = ["data/coverage.json", "controls/summary.json", "fcount/counts.csv", "fcount/by_month.csv",
            "fcount/fcount.txt", "fcount/summary.json", "primary/primary.json", "primary/gates.csv",
            "primary/samples_H1.csv", "primary/samples_H2R.csv", "verdicts.txt", "verdicts.csv", "answer.json",
            "desc/desc.json", "desc/desc.txt", "desc/sensitivity.csv", "desc/d12.csv", "desc/d6.csv",
            "desc/t1_summary.csv", "desc/t1_episodes.csv", "desc/d7_summary.csv", "desc/d7_compare.csv",
            "desc/d1.csv", "desc/d2.csv", "desc/d3.csv", "desc/d4.csv", "desc/d5.csv", "desc/d10.csv",
            "desc/d10_family.csv", "desc/dml.csv", "desc/sheet_coin_rung.csv", "explore/explore.json",
            "explore/explore.txt",
            "explore/depth_gradient.csv", "explore/breadth.csv", "explore/weekday.csv", "explore/user_coins.csv",
            "sheet_inputs.json"]
    miss = [f for f in must if not (out / f).exists()]
    assert not miss, miss
    v = pd.read_csv(out / "verdicts.csv")
    assert list(v["test"]) == ["H2R", "H1", "H4"], list(v["test"])
    for c in ("verdict", "estimate", "ci95_lo", "ci95_hi", "G", "gstar", "unit", "p_decide", "p_holm", "holm_level",
              "ub", "mde", "gates_ok", "binance_only"):
        assert c in v, c
    assert set(v["verdict"]) <= {"PASS", "NO EDGE", "NO EDGE (HARMS)", "INCONCLUSIVE"}
    ref = sbs.holm(v.set_index("test").loc[list(FAMILY), "p_decide"].to_numpy(float))
    assert np.allclose(v.set_index("test").loc[list(FAMILY), "p_holm"].to_numpy(float), ref, equal_nan=True)
    A = _jload(out / "answer.json")
    keys = [r["key"] for r in A["recommendation"]]
    exp = _expected_keys(A["verdicts"]["H2R"], A["verdicts"]["H1"], A["verdicts"]["H4"], A["flags"]["h1_bot_only"])
    assert keys == exp, (keys, exp)
    assert [r["key"] for r in A["fixed_sentences"]] == ["DISCOUNT", "TAIL_TOGETHER", "TAIL_BOTTOM", "TAIL_NEWS",
                                                         "MONEYLINE", "CAPACITY"]
    assert len(A["descriptive_sentences"]) == 5 and not sbdesc.check_wording(A["descriptive_sentences"])
    txt = (out / "verdicts.txt").read_text()
    i2, i1, i4 = (txt.index(NAMES[t] + ":") for t in ORDER)
    assert i2 < i1 < i4 < txt.index("What you are told") < txt.index("Printed with every answer")
    assert "SYNTHETIC DATA: NOT A RESULT" in txt and "G* =" in txt and "month-block clusters" in txt
    assert "K1c, regime timing alone: -1.2% per 90 days" in txt            # K1 -> K1c -> HOLD90 of the controls
    assert txt.index("D12 recovery curve") < txt.index("Holm family of three")
    C = pd.read_csv(out / "fcount" / "counts.csv")
    got = set(zip(C["program"], C["universe"]))
    assert all((p, u) in got for p, u, _ in FCOUNT_RUNS), sorted(got)
    S = pd.read_csv(out / "desc" / "sensitivity.csv")
    for sec in ("primary", "program", "rungs", "levels", "fill rule", "exit", "cost", "size", "benchmark",
                "clusters", "delisting", "bad prints", "universe"):
        assert sec in set(S["section"]), sec
    f3 = S[(S["section"] == "primary") & (S["rule"] == "F3_1")]
    assert len(f3) == 2 and f3["label"].str.contains("Robinhood-route proxy").all()
    assert S.loc[S["rule"] == "F5", "label"].str.contains("not fills this user could get").all()
    assert S.loc[S["universe"].isin(["U_A", "U_C"]), "label"].str.contains("hindsight").all()
    assert (S.loc[S["rule"] == "F6", "label"] == sbdesc.LABEL_NOT_BUILT).all()
    assert S.loc[(S["universe"] == "U_B") & (S["rule"] == "F3_1"), "label"].str.contains("not computed").all()
    D = _jload(out / "desc" / "desc.json")
    errs = {k: v for k, v in D.items() if isinstance(v, dict) and "error" in v}
    assert not errs, errs
    for sec in ("d12", "dh2", "dh3", "dh5", "t1", "d6", "d7", "dml", "d8", "d1", "d2", "d3", "d4", "d5", "d10",
                "d9", "d10_family", "d11", "sensitivity"):
        assert sec in D, sec
    X = _jload(out / "explore" / "explore.json")
    for t in ("depth_gradient", "breadth", "weekday", "flow", "m3_m8", "user_coins", "user_fills", "hype"):
        assert t in X, t
    br = pd.read_csv(out / "explore" / "breadth.csv")
    assert (br.loc[br["row"].str.endswith("market-wide") & (br["rule"] == "F1"), "n"] > 0).all(), br
    sc = pd.read_csv(out / "desc" / "sheet_coin_rung.csv")
    assert {"ALL"} <= set(sc["coin"]) and {"F1", "F3_1"} == set(sc["rule"])
    assert (sc["wilson_hi"] >= sc["wilson_lo"]).all()
    dg = pd.read_csv(out / "explore" / "depth_gradient.csv")
    if len(dg) and "p" in dg:
        for rule, g in dg.groupby("rule"):
            assert np.allclose(g["q_bh"].to_numpy(float), sbs.bh(g["p"].to_numpy(float)), equal_nan=True), rule
    # review findings 4, 8, 9, 10 on the end-to-end outputs
    s3 = sc[(sc["rule"] == "F3_1") & (sc["coin"] == "ALL")]
    assert np.isfinite(s3["p_no_fill_year"].to_numpy(float)).all(), s3            # the sheet's waits on F3 (4)
    d6 = pd.read_csv(out / "desc" / "d6.csv")
    assert set(d6["rule"]) == {"F1", "F3_1"} and all(f"mu_star_{k}" in d6 for k in sbdesc.EVENT_NAMES), d6.columns
    assert np.isfinite(d6.loc[d6["rule"] == "F3_1", "W"].to_numpy(float)).all()
    assert np.isfinite(d6.loc[d6["rule"] == "F3_1", "theta"].to_numpy(float)).any()   # TH72 on F3_1 (choice 18)
    d7s = pd.read_csv(out / "desc" / "d7_summary.csv")
    ml3 = d7s[(d7s["route"] == "F3_1") & (d7s["account"] == "D7-OWN-ML")]
    assert len(ml3) and (ml3["note"] == sbdesc.LABEL_NO_XML).all() and ml3["cagr"].isna().all(), ml3    # (10)
    assert np.isfinite(d7s.loc[(d7s["route"] == "F1") & (d7s["account"] == "D7-OWN-ML"), "cagr"]).all()
    d7c = pd.read_csv(out / "desc" / "d7_compare.csv")
    assert (d7c.loc[(d7c["route"] == "F3_1") & (d7c["account"] == "D7-OWN-ML"), "benchmark"] == "(none)").all()
    for f in ("breadth", "weekday", "depth_gradient", "user_coins"):                 # (8) F3 beside, single events
        x = pd.read_csv(out / "explore" / f"{f}.csv")
        assert {"F1", "F3_1"} <= set(x["rule"]) and all(k in x for k in sbdesc.EVENT_NAMES), f
    d12 = pd.read_csv(out / "desc" / "d12.csv")
    assert {f"all, {sbdesc.EVENT_LABELS[k]}" for k in sbdesc.EVENT_NAMES} <= set(d12["split"]), set(d12["split"])
    t1s = pd.read_csv(out / "desc" / "t1_summary.csv")
    assert (t1s.groupby("universe")["subset"].nunique() == 4).all(), t1s[["universe", "subset"]]
    dls = S[S["section"] == "delisting"]
    assert set(dls["rule"]) == {"F1", "F3_1"} and (dls["stat"] == "H1 mean r_f (fill valuation only)").all()
    assert {"F1", "F3_1"} <= set(S.loc[S["section"] == "clusters", "rule"])
    assert S.loc[S["section"] == "cost", "f3_note"].str.startswith("no F3 row").all()
    h1 = v.set_index("test").loc["H1"]                                                # (9) the E sensitivity
    assert math.isclose(h1["e_sens"], 0.0226) and h1["verdict_e_sens"] == sbs.verdict(
        h1["p_holm"], bool(h1["gates_ok"]), h1["ub"], 0.0226), h1
    assert A["sensitivity"]["H1_E_gold"]["verdict"] == h1["verdict_e_sens"]
    assert "Sensitivity (§10.3; not the verdict): with E = 2.26% per fill" in txt
    say(f"  outputs: {len(must)} files with the expected shapes (verdicts in the order H2R, H1, H4 with Holm "
        f"recomputed; the answer's keys equal the truth table for {A['verdicts']}; {len(C)} count rows for "
        f"{len(got)} programs; {len(S)} sensitivity rows with their labels; BH within the exploratory tables per "
        "route; F3 rows beside F1 in the exploratory, cluster, delisting and level rows; single events in D12, T1, D6 "
        "and the exploratory rows; the sheet's and D6's waits on F3; D7-OWN-ML on F3 labelled; H1's E sensitivity)")


def _t_report_pass(say, ctx: Ctx):
    """The report's PASS-only paths on the cached synthetic runs, with a fabricated primary.json in which H1 and H2R
    pass (p = 0.0005, every gate held, U-C effect under F3 > 0) and only H2R's F3-kept subset stays significant: the
    keys follow the truth table, H1 is labelled a Binance-only result and H2R is not, the flip target is shown, the
    D7 account on F3 is evaluated for "You could run it on Robinhood", and mu*_k is printed in H2R's sentence. The
    real primary.json is restored and the report re-run afterwards."""
    f = ctx.out / "primary" / "primary.json"
    keep = f.read_text()
    P = json.loads(keep)
    for t in ("H1", "H2R"):
        P["rows"][t].update(p_decide=0.0005, p_wcr=0.0005, p_gstar=0.0005, estimate=0.05, ci95=[0.02, 0.08],
                            ub=0.09, mde=0.03)
        P["gates"][t] = {k: True for k in P["gates"][t]}
        P["beside"][t]["U_C_F3"]["estimate"] = 0.01
    P["f3kept"]["H1"]["p_decide"] = 0.9
    P["f3kept"]["H2R"]["p_decide"] = 0.001
    P["bot"]["row"]["p_decide"] = 0.5
    f.write_text(json.dumps(P))
    try:
        ctx.rerun, ctx.reason = True, "selftest: fabricated PASS rows (report paths)"
        stage_report(ctx)
        A = _jload(ctx.out / "answer.json")
        assert A["verdicts"]["H1"] == "PASS" and A["verdicts"]["H2R"] == "PASS", A["verdicts"]
        keys = [r["key"] for r in A["recommendation"]]
        assert keys == _expected_keys("PASS", "PASS", A["verdicts"]["H4"], False), keys
        assert A["flags"]["binance_only"] == {"H1": True, "H2R": False}, A["flags"]
        assert A["flags"]["show_flip_target"] is True and A["tests_passed"] == ["H1", "H2R"]
        rh = A["run_on_robinhood"]
        assert rh["account"] is not None and "lo_12m" in rh["account"], rh
        assert rh["ok"] == bool(rh["account"]["ok"]), rh
        txt = (ctx.out / "verdicts.txt").read_text()
        assert "Yes:" in txt and "Binance-only result" in txt and "mu*_k a year (D6): k = 6:" in txt
        say(f"  report PASS paths (fabricated rows): keys {keys}; H1 Binance-only, H2R not; flip target shown; D7 "
            f"on F3 against B-MIX evaluated (12-month CI {_pct(rh['account']['lo_12m'])} to "
            f"{_pct(rh['account']['hi_12m'])}: run on Robinhood = {rh['ok']})")
    finally:
        f.write_text(keep)
        stage_report(ctx)
        ctx.rerun = False


def selftest(e2e: bool = True) -> bool:
    t_all = time.time()
    say = lambda m: print(m, flush=True)
    timings = {}
    t = time.time()
    _t_answer_map(say)
    _t_verdict_lines(say)
    timings["answer map"] = time.time() - t
    t = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        _t_primary_known(say)
    timings["primary known answers"] = time.time() - t
    t = time.time()
    _t_review_units(say)
    timings["review units"] = time.time() - t
    if e2e:
        base = SCRATCH / "selftest"
        if base.exists():
            shutil.rmtree(base)
        out, cache = base / "results", base / "cache"
        t = time.time()
        W = _synthetic_world()
        timings["world"] = time.time() - t
        t = time.time()
        ctx = _t_gating(say, W, out, cache)
        timings["gating"] = time.time() - t
        ctx.verbose = False
        for st in ("fcount", "primary", "report", "desc", "explore"):
            t = time.time()
            STAGE_FN[st](ctx)
            timings[st] = time.time() - t
            say(f"  stage {st}: complete ({timings[st]:.0f}s)")
        t = time.time()
        info = stage_sheet(ctx)        # in-process on the injected world (stinkbid_sheet.run_stage)
        timings["sheet"] = time.time() - t
        assert info["outputs"] and all(Path(p).parent == out / "sheet" for p in info["outputs"]), info
        assert any(Path(p).name.startswith("sheet_") and p.endswith(".csv") for p in info["outputs"]), info
        assert stage_complete(ctx, "sheet")
        say(f"  stage sheet: complete ({len(info['outputs'])} files in OUT/sheet)")
        _t_shapes(say, ctx)
        # resuming: a rerun of report with --rerun reproduces the same verdicts from the cached runs
        v1 = pd.read_csv(out / "verdicts.csv")
        ctx.rerun, ctx.reason = True, "selftest: reproducibility of the report"
        t = time.time()
        stage_report(ctx)
        timings["report rerun"] = time.time() - t
        ctx.rerun = False
        v2 = pd.read_csv(out / "verdicts.csv")
        assert v1[["test", "verdict", "p_decide", "p_holm"]].equals(v2[["test", "verdict", "p_decide", "p_holm"]])
        assert not stage_complete(ctx, "desc") and not stage_complete(ctx, "explore")
        say("  rerun of report (logged): identical verdicts; desc and explore invalidated until they run again")
        t = time.time()
        _t_report_pass(say, ctx)
        timings["report PASS paths"] = time.time() - t
        status(ctx)
    say("timings: " + ", ".join(f"{k} {v:.0f}s" for k, v in timings.items()))
    say(f"stinkbid_run selftest: all passed ({time.time() - t_all:.0f}s)")
    return True


if __name__ == "__main__":
    sys.exit(main())
