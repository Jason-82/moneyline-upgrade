"""Read-only check: every printed interval / bound in the record's verdicts.txt and answer.json (commit eee2ddf),
and whether the same line states a cluster unit, G and G*. Reads from git only; writes nothing."""
import json
import re
import subprocess

REPO = "/home/user/moneyline-upgrade"


def show(commit, path):
    return subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], capture_output=True, text=True,
                          check=True).stdout


txt = show("eee2ddf", "analysis_2026/results_stinkbid/verdicts.txt").splitlines()
end = next(i for i, l in enumerate(txt) if l.startswith("=====")) if any(l.startswith("=====") for l in txt) else len(txt)
print("== verdicts.txt (eee2ddf): lines with a 95% CI or a 98.33% bound, and whether the line states unit, G, G*")
for i, l in enumerate(txt, 1):
    n_ci = len(re.findall(r"95% CI", l))
    n_ub = len(re.findall(r"98\.33% upper bound", l))
    if not (n_ci or n_ub):
        continue
    has_g = bool(re.search(r"\bG = \d+", l)) or "G_coin" in l
    has_gs = "G* =" in l or "t at" in l
    has_unit = bool(re.search(r"(month-block|quarter-block|coin x quarter) clusters", l))
    where = "answer" if i <= end else "details"
    print(f"line {i:3d} [{where}] CI x{n_ci} bound x{n_ub}  unit={has_unit} G={has_g} G*={has_gs} :: {l[:110]}")

ans = json.loads(show("eee2ddf", "analysis_2026/results_stinkbid/answer.json"))
print("\n== answer.json (eee2ddf) texts with a 95% CI")
for sec in ("recommendation", "fixed_sentences", "descriptive_sentences"):
    v = ans.get(sec) or []
    items = v.items() if isinstance(v, dict) else enumerate(v)
    for k, r in items:
        t = r.get("text", "") if isinstance(r, dict) else str(r)
        key = r.get("key", k) if isinstance(r, dict) else k
        if "95% CI" in t:
            print(f"{sec}:{key}: G*={'G* =' in t or 't at' in t}  unit={'clusters' in t} :: {t[:100]}")
h1 = ans["numbers"]["tests"]["H1"]
print("\nnumbers.tests.H1:", {k: h1[k] for k in ("lo", "hi", "N", "G", "gstar")})
rec = next(r for r in ans["recommendation"] if r["key"] == "H1_PASS")["text"]
m = re.search(r"\(95% CI ([+-][\d.]+)% to ([+-][\d.]+)%\)", rec)
print("H1_PASS interval:", m.groups(), "== numbers lo/hi:", f"{100*h1['lo']:+.1f}", f"{100*h1['hi']:+.1f}")

# the frozen §11 template for H1 PASS and H2R PASS, and S9's proposal (critique) for comparison
pre = show("72ac2a4", "analysis_2026/STINKBID_PREREG.md")
for key in ("| H1 PASS (rule M) |", "| H2R PASS |"):
    row = next(l for l in pre.splitlines() if l.startswith(key))
    print(f"\nfrozen {key.strip('| ')}: G-clause present = {'independent months' in row}")
crit = show("eee2ddf", "analysis_2026/research_notes/Stink bids/critique_statistics.md")
s9 = next(l for l in crit.splitlines() if l.startswith("| H1 | \"Selling"))
print("S9 proposal for H1 PASS has G-clause:", "independent months" in s9)
