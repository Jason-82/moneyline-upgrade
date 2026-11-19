"""Reproduce audit finding h4-no-uc-row on the committed files of record (read-only; git show only).

Checks:
 1. prereg (eee2ddf) §5: U-C's role text, and §11: the headlines (H2R, H1, H4).
 2. verdicts.txt (eee2ddf): the rows printed in the 'Beside every headline' block, per test.
 3. verdicts.csv (eee2ddf): beside_U_C / beside_U_C_F3 per test.
 4. primary/primary.json (eee2ddf): beside keys per test and the runs list.
 5. answer.json (eee2ddf): any U-C number for H4.
 6. stinkbid_run.py (eee2ddf): ANSWER_RUNS, DESC_RUNS, EXPLORE_RUNS parsed with ast; any H4* program on U_C?
 7. fcount counts (e354251): universes each H4* program was counted on.
 8. desc (7949037) / explore (b8b2279) / controls (989e134): any H4 row on U-C.
 9. the engine run cache: any H4*__U_C directory (outcomes, fcount).
10. stinkbid_engine.py (eee2ddf): U_C is an accepted universe for any program (feasibility of the fix).
"""
import ast
import io
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path("/home/user/moneyline-upgrade")
R = "analysis_2026/results_stinkbid"


def show(commit, path):
    return subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:{path}"], check=True,
                          capture_output=True, text=True).stdout


def ls_tree(commit, path):
    out = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", commit, path], check=True,
                         capture_output=True, text=True).stdout
    return [x for x in out.splitlines() if x]


print("=" * 100)
print("1. Pre-registration (eee2ddf)")
pre = show("eee2ddf", "analysis_2026/STINKBID_PREREG.md")
for line in pre.splitlines():
    if line.startswith("| U-C") or line.startswith("| U-B ") or line.startswith("| **U-Q1"):
        print("  ", line)
m = re.search(r"The answer is the verdicts of.*?\n.*?\n", pre)
print("   §11:", m.group(0).strip().replace("\n", " ") if m else "?")
for line in pre.splitlines():
    if "Every headline" in line or "Completeness" in line:
        print("  ", line.strip())

print("=" * 100)
print("2. verdicts.txt (eee2ddf): 'Beside every headline' block")
vt = show("eee2ddf", f"{R}/verdicts.txt").splitlines()
i0 = next(i for i, l in enumerate(vt) if l.startswith("Beside every headline"))
block = []
for l in vt[i0 + 1:]:
    if not l.strip():
        break
    block.append(l)
print("  ", vt[i0])
per_test = {}
for l in block:
    t, k = l.split()[0], l.split()[1]
    per_test.setdefault(t, []).append(k)
for t, ks in per_test.items():
    print(f"   {t:4s}: {ks}")
print("   H4 has a U_C row:", any(k.startswith("U_C") for k in per_test.get("H4", [])))
print("   H4 lines:", [l.strip() for l in block if l.split()[0] == "H4"])

print("=" * 100)
print("3. verdicts.csv (eee2ddf)")
vc = pd.read_csv(io.StringIO(show("eee2ddf", f"{R}/verdicts.csv")))
print(vc[["test", "verdict", "estimate", "beside_F3_1", "beside_U_B", "beside_U_C", "beside_U_C_F3"]].to_string(index=False))

print("=" * 100)
print("4. primary/primary.json (eee2ddf)")
pj = json.loads(show("eee2ddf", f"{R}/primary/primary.json"))
for t, v in pj["beside"].items():
    print(f"   beside.{t}: {list(v.keys())}")
print("   runs:", pj["runs"])
print("   H4 beside has U_C:", "U_C" in pj["beside"].get("H4", {}))

print("=" * 100)
print("5. answer.json (eee2ddf): U-C numbers")
aj = json.loads(show("eee2ddf", f"{R}/answer.json"))
print("   run_on_robinhood.uc_f3:", aj["run_on_robinhood"].get("uc_f3"))
print("   answer.json mentions U_C/U-C for H4:",
      bool(re.search(r"H4[^\n]{0,200}U[_-]C", json.dumps(aj))))

print("=" * 100)
print("6. stinkbid_run.py (eee2ddf): run plans")
src = show("eee2ddf", "analysis_2026/stinkbid_run.py")
tree = ast.parse(src)
plans = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        nm = node.targets[0].id
        if nm in ("ANSWER_RUNS", "DESC_RUNS", "EXPLORE_RUNS"):
            plans[nm] = ast.literal_eval(node.value)
for nm, p in plans.items():
    print(f"   {nm}: {[f'{a}/{b}' for a, b, _ in p]}")
allr = [r for p in plans.values() for r in p]
h4 = [f"{a}/{b}" for a, b, _ in allr if a.startswith("H4")]
print("   H4 programs in any plan:", h4)
print("   any H4 program on U_C:", any(a.startswith("H4") and b == "U_C" for a, b, _ in allr))
print("   U_C runs:", [f"{a}/{b}" for a, b, _ in allr if b == "U_C"])
# what primary_compute puts beside H4
m = re.search(r'out\["beside"\]\["H4"\] = \{.*?\n.*?\n', src)
print("   primary_compute's H4 beside:", m.group(0).strip() if m else "?")

print("=" * 100)
print("7. fcount counts (e354251): universes per H4* program")
cc = pd.read_csv(io.StringIO(show("e354251", f"{R}/fcount/counts.csv")))
pcol = [c for c in cc.columns if c.lower() in ("program",)][0]
ucol = [c for c in cc.columns if c.lower() in ("universe",)][0]
print("   ", cc[cc[pcol].astype(str).str.startswith("H4")].groupby(pcol)[ucol].unique().to_dict())
print("   U_C programs counted:", sorted(cc.loc[cc[ucol] == "U_C", pcol].unique().tolist()))

print("=" * 100)
print("8. Any H4 row on U-C in desc (7949037), explore/sheet_inputs (b8b2279), controls (989e134), fcount (e354251)")
hits = []
for commit, paths in (("7949037", [f"{R}/desc/"]), ("b8b2279", [f"{R}/explore/", f"{R}/sheet_inputs.json"]),
                      ("989e134", [f"{R}/controls/"]), ("e354251", [f"{R}/fcount/"]),
                      ("eee2ddf", [f"{R}/primary/", f"{R}/verdicts.txt", f"{R}/verdicts.csv", f"{R}/answer.json"])):
    for p in paths:
        for f in ls_tree(commit, p):
            if f.endswith((".parquet",)):
                continue
            try:
                txt = show(commit, f)
            except subprocess.CalledProcessError:
                continue
            for ln, line in enumerate(txt.splitlines(), 1):
                if re.search(r"\bH4", line) and re.search(r"U[_-]C\b|Robinhood-listed", line):
                    hits.append((commit, f, ln, line[:160]))
print("   lines naming both H4 and U-C:", len(hits))
for h in hits[:10]:
    print("    ", h)
# sensitivity.csv stats (desc first pass)
sv = pd.read_csv(io.StringIO(show("7949037", f"{R}/desc/sensitivity.csv")))
print("   desc/sensitivity.csv stats:", sv["stat"].value_counts().to_dict())
print("   desc/sensitivity.csv U_C rows:", sv.loc[sv["universe"] == "U_C", ["stat", "rule", "label"]].values.tolist())

print("=" * 100)
print("9. Engine run cache")
for sub in ("outcomes", "fcount"):
    d = REPO / "data/stinkbid/runs" / sub
    names = sorted(x.name for x in d.iterdir()) if d.exists() else []
    print(f"   runs/{sub}: H4* dirs {[n for n in names if n.startswith('H4')]}; U_C dirs {[n for n in names if n.endswith('__U_C')]}")

print("=" * 100)
print("10. stinkbid_engine.py (eee2ddf): accepted universes")
es = show("eee2ddf", "analysis_2026/stinkbid_engine.py")
for line in es.splitlines()[:40]:
    if "universe:" in line:
        print("   ", line.strip())
