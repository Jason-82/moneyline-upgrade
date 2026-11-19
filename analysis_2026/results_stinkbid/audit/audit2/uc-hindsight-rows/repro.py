"""Reproduce uc-hindsight-rows on the committed results of record (read-only, git show only)."""
import io, json, os, re, subprocess
import pandas as pd
REPO = "/home/user/moneyline-upgrade"
def show(c, p):
    return subprocess.run(["git", "-C", REPO, "show", f"{c}:{p}"], capture_output=True, text=True, check=True).stdout
R = "analysis_2026/results_stinkbid/"
v = show("eee2ddf", R + "verdicts.txt")
hl = [l for l in v.splitlines() if "hindsight" in l.lower()]
assert hl == ["Beside every headline (F3 = Robinhood market-maker-route proxy; U-C = Robinhood-listed, hindsight):"], hl
rows = {m.group(1) + " " + m.group(2): m.group(3) for m in
        re.finditer(r"^  (H2R|H1|H4) (\S+)\s*: .*?G\* = [\d.]+\) ?(.*)$", v, re.M)}
print("beside rows and their trailing labels:"); [print(f"  {k:12s} -> {lab!r}") for k, lab in rows.items()]
assert rows["H1 U_C"] == "" and rows["H2R U_C"] == ""
assert rows["H1 U_C_F3"] == rows["H2R U_C_F3"] == "Robinhood-route proxy"
assert not any(k.startswith("H4 U_C") for k in rows)
p = json.loads(show("eee2ddf", R + "primary/primary.json"))
b = p["beside"]
assert b["H1"]["U_C"]["label"] == "" and b["H2R"]["U_C"]["label"] == ""
assert b["H1"]["U_C_F3"]["label"] == b["H2R"]["U_C_F3"]["label"] == "Robinhood-route proxy"
assert list(b["H4"].keys()) == ["F3_1", "F3_1_omnibus"], list(b["H4"].keys())
for f in ("primary/primary.json", "answer.json", "verdicts.csv"):
    print(f"'hindsight' in {f}:", show("eee2ddf", R + f).lower().count("hindsight"))
a = json.loads(show("eee2ddf", R + "answer.json"))
print("answer.json run_on_robinhood.uc_f3 (unlabelled U-C number):", a["run_on_robinhood"]["uc_f3"])
# H4 never run on U-C: plans, fill counts, cached runs, desc/explore tables
src = show("eee2ddf", "analysis_2026/stinkbid_run.py")
ns = {}
exec(re.search(r"^ANSWER_RUNS = .*?^EXPLORE_RUNS = .*?\n", src, re.S | re.M).group(0), ns)
plan = ns["ANSWER_RUNS"] + ns["DESC_RUNS"] + ns["EXPLORE_RUNS"]
print("H4 programs in every plan:", [(pg, u) for pg, u, _ in plan if pg.startswith("H4")])
print("U_C programs in every plan:", [(pg, u) for pg, u, _ in plan if u == "U_C"])
fc = pd.read_csv(io.StringIO(show("e354251", R + "fcount/counts.csv")), usecols=["program", "universe"])
print("fcount H4 universes:", sorted(fc.loc[fc["program"].str.startswith("H4"), "universe"].unique()))
print("cached outcome runs on U_C:", [d for d in os.listdir(f"{REPO}/data/stinkbid/runs/outcomes") if d.endswith("__U_C")])
for c in ("7949037", "b8b2279"):
    S = pd.read_csv(io.StringIO(show(c, R + "desc/sensitivity.csv")))
    print(c, "sensitivity H4 rows:", int(S["stat"].str.contains("H4").sum()),
          "| U_C labels:", S.loc[S["universe"] == "U_C", "label"].tolist())
dv = show("eee2ddf", R + "stages/deviations.jsonl")
print("deviations of record mentioning U-C / H4:", [l for l in dv.splitlines() if re.search(r"U-C|U_C|H4", l)])
print("ALL CLAIMS REPRODUCED")
