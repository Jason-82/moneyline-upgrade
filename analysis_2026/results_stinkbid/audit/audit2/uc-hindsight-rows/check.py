"""Reproduce finding uc-hindsight-rows against the record (git objects only; read-only)."""
import json, os, re, subprocess

REPO = "/home/user/moneyline-upgrade"

def show(commit, path):
    return subprocess.run(["git", "-C", REPO, "show", f"{commit}:{path}"], capture_output=True, text=True,
                          check=True).stdout

R = "analysis_2026/results_stinkbid/"
# 1. primary.json beside block (record eee2ddf)
pj = json.loads(show("eee2ddf", R + "primary/primary.json"))
for t, rows in pj["beside"].items():
    print(t, {k: (v.get("label") if isinstance(v, dict) else None) for k, v in rows.items()})
print("H4 beside keys:", list(pj["beside"]["H4"].keys()))

# 2. verdicts.txt beside block
vt = show("eee2ddf", R + "verdicts.txt").splitlines()
i = next(j for j, l in enumerate(vt) if l.startswith("Beside every headline"))
print("\n".join(vt[i:i + 15]))
print("H4 U_C line present:", any(re.match(r"\s+H4 U_C", l) for l in vt))
print("'hindsight' occurrences in verdicts.txt:", sum("hindsight" in l for l in vt),
      [l.strip()[:90] for l in vt if "hindsight" in l])

# 3. which programs run on which universe, in every stage (run code of record)
src = show("eee2ddf", "analysis_2026/stinkbid_run.py")
for name in ("ANSWER_RUNS", "DESC_RUNS", "EXPLORE_RUNS"):
    k = src.index(name + " = (") + len(name) + 3
    depth, j = 0, k
    while True:
        depth += {"(": 1, ")": -1}.get(src[j], 0)
        j += 1
        if depth == 0:
            break
    runs = eval(src[k:j])
    print(name, [r[:2] for r in runs if r[1] == "U_C" or r[0].startswith("H4")])

# 4. cached engine runs on disk
print("cached runs:", sorted(os.listdir(os.path.join(REPO, "data/stinkbid/runs/outcomes"))))

# 5. desc (7949037) and explore (b8b2279): any H4 statistic on U-C?
dj = json.loads(show("7949037", R + "desc/desc.json"))
hits = []
def walk(x, p):
    if isinstance(x, dict):
        for k, v in x.items():
            walk(v, p + "/" + str(k))
    elif isinstance(x, list):
        for n, v in enumerate(x):
            walk(v, p + f"[{n}]")
    elif "U_C" in str(x) or "U-C" in str(x):
        hits.append(p)
walk(dj, "")
print("H4-related U-C hits in desc.json:", [h for h in hits if "h4" in h.lower()])
print("desc.json U-C hits by table:", sorted({h.split("[")[0] for h in hits}))
sens = show("7949037", R + "desc/sensitivity.csv").splitlines()
print("sensitivity U_C rows:", [l.split(",")[2:7] for l in sens if ",U_C," in l])
ex = show("b8b2279", R + "explore/explore.json")
print("explore.json mentions U_C:", ("U_C" in ex) or ("U-C" in ex))
