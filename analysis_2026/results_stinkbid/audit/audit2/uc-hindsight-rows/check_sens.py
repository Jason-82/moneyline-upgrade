import io, subprocess
import pandas as pd
def show(commit, path):
    return subprocess.run(["git", "-C", "/home/user/moneyline-upgrade", "show", f"{commit}:{path}"],
                          capture_output=True, text=True, check=True).stdout
for commit in ("7949037", "b8b2279"):
    S = pd.read_csv(io.StringIO(show(commit, "analysis_2026/results_stinkbid/desc/sensitivity.csv")))
    print("==", commit, "rows", len(S))
    print("stat values:", sorted(S["stat"].dropna().unique()))
    print("universes by stat:")
    print(S.groupby("stat")["universe"].apply(lambda s: sorted(s.dropna().unique())).to_string())
    uc = S[S["universe"] == "U_C"]
    print("U_C rows:")
    print(uc[["section", "row", "stat", "program", "rule", "label", "n", "estimate"]].to_string())
    h4 = S[S["stat"].astype(str).str.contains("H4")]
    print("H4 rows:", len(h4), "universes:", sorted(h4["universe"].dropna().unique()))
    print(h4[["section", "row", "stat", "program", "universe", "rule", "label", "n"]].head(40).to_string())
