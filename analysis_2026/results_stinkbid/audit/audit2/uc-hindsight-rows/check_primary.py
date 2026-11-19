import json, subprocess, sys
def show(commit, path):
    return subprocess.run(["git", "-C", "/home/user/moneyline-upgrade", "show", f"{commit}:{path}"],
                          capture_output=True, text=True, check=True).stdout
p = json.loads(show("eee2ddf", "analysis_2026/results_stinkbid/primary/primary.json"))
print("top keys:", list(p.keys()))
b = p.get("beside")
print("beside type:", type(b).__name__)
if isinstance(b, dict):
    for t, rows in b.items():
        print("TEST", t, "keys:", list(rows.keys()) if isinstance(rows, dict) else type(rows).__name__)
        if isinstance(rows, dict):
            for k, v in rows.items():
                if isinstance(v, dict):
                    print("   ", k, "label=%r" % v.get("label"), {kk: vv for kk, vv in v.items() if kk in ("universe","fill","route","program","n","estimate","hindsight")})
                else:
                    print("   ", k, repr(v)[:200])
# search for any 'hindsight' strings anywhere in primary.json and answer.json
s = show("eee2ddf", "analysis_2026/results_stinkbid/primary/primary.json")
print("primary.json 'hindsight' occurrences:", s.lower().count("hindsight"))
a = show("eee2ddf", "analysis_2026/results_stinkbid/answer.json")
print("answer.json 'hindsight' occurrences:", a.lower().count("hindsight"))
v = show("eee2ddf", "analysis_2026/results_stinkbid/verdicts.txt")
print("verdicts.txt 'hindsight' occurrences:", v.lower().count("hindsight"))
for line in v.splitlines():
    if "hindsight" in line.lower():
        print("  >>", line)
c = show("eee2ddf", "analysis_2026/results_stinkbid/verdicts.csv")
print("verdicts.csv:\n", c)
