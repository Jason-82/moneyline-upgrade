import io, json, subprocess
import pandas as pd

def show(commit, path):
    return subprocess.run(["git", "-C", "/home/user/moneyline-upgrade", "show", f"{commit}:{path}"],
                          capture_output=True, text=True, check=True).stdout

vc = pd.read_csv(io.StringIO(show("eee2ddf", "analysis_2026/results_stinkbid/verdicts.csv")))
bc = [c for c in vc.columns if c.startswith("beside_")]
print("verdicts.csv beside columns:", bc)
print(vc[["test"] + bc].to_string())

pj = json.loads(show("eee2ddf", "analysis_2026/results_stinkbid/primary/primary.json"))
for t, d in pj["beside"].items():
    print(t, "beside keys:", list(d.keys()))
print("primary.json runs:", pj.get("runs"))

aj = show("eee2ddf", "analysis_2026/results_stinkbid/answer.json")
for needle in ("U_C", "U-C", "hindsight", "Robinhood-listed"):
    idx = [i for i in range(len(aj)) if aj.startswith(needle, i)]
    print(f"answer.json occurrences of {needle!r}: {len(idx)}")
a = json.loads(aj)
def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, o
for p, v in walk(a):
    s = str(v)
    if "U_C" in p or "U-C" in s or "U_C" in s or "hindsight" in s or "Robinhood-listed" in s:
        print(p, "=", s[:200])
