"""Reproduce finding h1-rec-interval-without-g on the committed files (read-only; git show only).

1. Re-run the COMMITTED recommendation() (stinkbid_run.py @ eee2ddf) on the COMMITTED numbers (answer.json @ eee2ddf),
   with the committed formatting helpers from stinkbid_desc.py @ eee2ddf, and check it reproduces the printed text.
2. List which per-test numbers each PASS branch reads (AST), and whether its interval carries unit, G and G*.
3. Scan every interval / bound printed in verdicts.txt and answer.json @ eee2ddf for its cluster unit, G and G*.
"""
import ast
import json
import math
import re
import subprocess
import sys
import types

import numpy as np

REPO = "/home/user/moneyline-upgrade"
REC = "eee2ddf"


def show(path, commit=REC):
    return subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], check=True, capture_output=True,
                          text=True).stdout


def funcs(src, names):
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            out[node.name] = (ast.get_source_segment(src, node), node)
    missing = set(names) - set(out)
    assert not missing, missing
    return out


run_src = show("analysis_2026/stinkbid_run.py")
desc_src = show("analysis_2026/stinkbid_desc.py")
verdicts_txt = show("analysis_2026/results_stinkbid/verdicts.txt")
answer = json.loads(show("analysis_2026/results_stinkbid/answer.json"))
primary = json.loads(show("analysis_2026/results_stinkbid/primary/primary.json"))

# --- the committed helpers, executed verbatim -------------------------------------------------------------------
dfun = funcs(desc_src, ["_f", "fmt_pct", "fmt_ci", "unc"])
sbdesc = types.ModuleType("sbdesc_committed")
sbdesc.np = np
sbdesc.NAN = math.nan
for name in ["_f", "fmt_pct", "fmt_ci", "unc"]:
    exec(dfun[name][0], sbdesc.__dict__)
rfun = funcs(run_src, ["_pct", "_ci", "recommendation"])
ns = {"sbdesc": sbdesc}
for name in ["_pct", "_ci", "recommendation"]:
    exec(rfun[name][0], ns)
recommendation = ns["recommendation"]

# --- 1. reproduce the printed recommendation from the committed numbers -----------------------------------------
v = dict(answer["verdicts"], h1_bot_only=answer["flags"]["h1_bot_only"], numbers=answer["numbers"]["tests"],
         mu_star={float(k): x for k, x in answer["numbers"]["mu_star"].items()})
rec = recommendation(v)
committed_rec = [(r["key"], r["text"]) for r in answer["recommendation"]]
print("1. committed recommendation() on committed numbers reproduces answer.json:", rec == committed_rec)
vt_lines = verdicts_txt.splitlines()
i0 = vt_lines.index("What you are told (the pre-registered recommendation table, applied in order):")
printed = [ln[2:] for ln in vt_lines[i0 + 1:i0 + 1 + len(rec)]]
print("   ... and verdicts.txt lines", i0 + 2, "to", i0 + 1 + len(rec), ":", printed == [t for _, t in rec])
h1 = dict(rec)["H1_PASS"]
print("   H1_PASS (verdicts.txt line", i0 + 3, "):", h1)
has = {k: (k in h1) for k in ["95% CI", "G =", "G* =", "G*", "month-block", "clusters", "1541", "months"]}
print("   contains:", has)

# --- 2. which numbers each PASS branch reads ------------------------------------------------------------------
node = rfun["recommendation"][1]


def keys_in_append(key):
    """Keys read with x.get('...') inside the out.append(("KEY", ...)) call."""
    for n in ast.walk(node):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "append" and n.args
                and isinstance(n.args[0], ast.Tuple) and isinstance(n.args[0].elts[0], ast.Constant)
                and n.args[0].elts[0].value == key):
            ks = []
            for m in ast.walk(n):
                if (isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute) and m.func.attr == "get"
                        and m.args and isinstance(m.args[0], ast.Constant)):
                    ks.append(f"{m.func.value.id}.get({m.args[0].value!r})")
            return ks
    return None


for key in ["H2R_PASS", "H1_PASS", "H4_PASS"]:
    print(f"2. {key} reads:", keys_in_append(key))
print("   numbers available to recommendation() for H1:", sorted(answer["numbers"]["tests"]["H1"]))
print("   committed unc() helper ('the uncertainty note every interval carries (§12)') used in stinkbid_run.py:",
      "unc(" in run_src)

# the PASS templates under every verdict combination, with the committed numbers (shows which ones carry G/G*)
for t in ["H2R", "H1", "H4"]:
    vv = dict(v, **{x: "INCONCLUSIVE" for x in ["H2R", "H1", "H4"]})
    vv[t] = "PASS"
    txt = dict(recommendation(vv))[f"{t}_PASS"]
    print(f"   {t}_PASS with committed numbers -> 'G'/'G*' stated: "
          f"{bool(re.search(r'G\\*|independent months|G =', txt))}; text: {txt[:170]}...")

# --- 3. every interval or bound in the committed outputs ---------------------------------------------------------
print("3. intervals / bounds in verdicts.txt @", REC, "lacking cluster unit, G or G* on the same line:")
pat_iv = re.compile(r"95% CI|upper bound|interval")
for i, ln in enumerate(vt_lines, 1):
    if not pat_iv.search(ln):
        continue
    unit = bool(re.search(r"month-block|quarter-block|coin x quarter|clusters", ln))
    g = bool(re.search(r"\bG =|G_coin =|G_quarter =|in \d+ months", ln))
    gs = bool(re.search(r"G\* =|independent months", ln))
    if not (unit and g and gs):
        print(f"   line {i:3d}: unit={unit} G={g} G*={gs} :: {ln[:150]}")
print("   answer.json recommendation texts with an interval but no G*:",
      [r["key"] for r in answer["recommendation"] if "95% CI" in r["text"] and "G*" not in r["text"]])
print("   answer.json descriptive sentences with an interval but no G*:",
      [s[:60] for s in answer["descriptive_sentences"] if "95% CI" in s and "G*" not in s])

# the bound-only lines: the numbers behind them exist in the committed primary.json
b = primary["bot"]["row"]
print("   bot latency row in primary.json: n", b["n"], "G", b["G"], "G*", round(b["gstar"], 2), "unit", b["unit"],
      "ub", round(b["ub"], 4), "ci95", [round(x, 4) for x in b["ci95"]])
h1row = primary["rows"]["H1"]
print("   H1 row in primary.json: n", h1row.get("n"), "G", h1row.get("G"), "G*", round(h1row.get("gstar"), 2),
      "unit", h1row.get("unit"), "ci95", [round(x, 4) for x in h1row.get("ci95", [])])
