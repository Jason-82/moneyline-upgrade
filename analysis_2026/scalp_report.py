"""
Combine the scalping study's primary cells (analysis_2026/SCALPING_PREREG.md, "General rules") into verdicts.

    python3 -m analysis_2026.scalp_report

Reads results_scalping/{A,B,C}/primary_cells.csv (Part B's file also holds the four E cells), applies one Holm
correction across all 36 primary tests, and writes results_scalping/verdicts.csv and verdicts.txt:
  PASS          Holm-adjusted one-sided p < 0.05 and every cond_* column True
  NO EDGE       one-sided (1 - 0.05/36) upper bound of the edge below the cell's threshold E
  INCONCLUSIVE  neither
Also reported: the one-sided 95% upper bound of the edge ("largest edge ruled out at 95%") and the MDE at 80% power.
Each part's PASS conditions are its own cond_* columns (True = met or not applicable; empty = not evaluable = not
met). A True `force_inconclusive` (Part C: failed Roll-market positive control or bar-size sign disagreement) caps
the verdict at INCONCLUSIVE, i.e. neither PASS nor NO EDGE.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from analysis_2026 import scalp_stats as ss

ROOT = Path(__file__).resolve().parent
RES = ROOT / "results_scalping"


def _q(level, df):
    return stats.t.ppf(level, df) if np.isfinite(df) and df > 0 else stats.norm.ppf(level)


def main():
    parts, conds = [], []
    for p in ("A", "B", "C"):
        f = RES / p / "primary_cells.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f)
        # each part's own conditions; an empty cond_* means "not evaluable" and counts as not met
        cc = [k for k in d.columns if k.startswith("cond_")]
        d["other_ok"] = d[cc].apply(lambda s: s.map({True: True, "True": True}).fillna(False)).all(axis=1) if cc else True
        d["conds_checked"] = ",".join(cc)
        conds += [k for k in cc if k not in conds]
        parts.append(d)
    c = pd.concat(parts, ignore_index=True)
    if len(c) != ss.N_PRIMARY:
        print(f"WARNING: {len(c)} primary cells found, {ss.N_PRIMARY} pre-registered")
    c["p_holm"] = ss.holm(c["p_one_sided"].to_numpy())
    if "force_inconclusive" not in c:
        c["force_inconclusive"] = False
    c["force_inconclusive"] = c["force_inconclusive"].map({True: True, "True": True}).fillna(False)
    df = c["edge_df"].astype(float).to_numpy()
    c["edge_ub_strict"] = [e + _q(1 - ss.ALPHA / ss.N_PRIMARY, d) * s for e, s, d in zip(c.edge_estimate, c.edge_se, df)]
    c["edge_ub95"] = [e + _q(0.95, d) * s for e, s, d in zip(c.edge_estimate, c.edge_se, df)]
    c["edge_mde80"] = [(_q(1 - ss.ALPHA / ss.N_PRIMARY, d) + stats.norm.ppf(0.8)) * s for s, d in zip(c.edge_se, df)]
    c["verdict"] = [ss.verdict(p, ok, ub, E) for p, ok, ub, E in zip(c.p_holm, c.other_ok, c.edge_ub_strict, c.threshold_E)]
    # Part A, Control (ii): "a cell whose verdict changes under the F1 bias correction is INCONCLUSIVE". Recompute the
    # verdicts with the corrected statistic and edge (Holm re-run on the corrected p-values) and compare.
    if "corr_p_one_sided" in c:
        has = c.corr_p_one_sided.notna()
        p2 = np.where(has, c.corr_p_one_sided, c.p_one_sided)
        ph2 = ss.holm(p2)
        e2 = np.where(has, c.get("corr_edge_estimate", c.edge_estimate), c.edge_estimate)
        s2 = np.where(has, c.get("corr_edge_se", c.edge_se), c.edge_se)
        d2 = np.where(has, c.get("corr_edge_df", c.edge_df), c.edge_df).astype(float)
        ub2 = [e + _q(1 - ss.ALPHA / ss.N_PRIMARY, d) * s for e, s, d in zip(e2, s2, d2)]
        c["verdict_corrected"] = [ss.verdict(p, ok, ub, E) for p, ok, ub, E in zip(ph2, c.other_ok, ub2, c.threshold_E)]
        c["corr_changes_verdict"] = has & (c.verdict_corrected != c.verdict)
        c.loc[c.corr_changes_verdict, "verdict"] = "INCONCLUSIVE"
    # a failed positive control (Part C) or a sign disagreement across bar sizes caps the verdict at INCONCLUSIVE:
    # it can neither PASS nor be read as NO EDGE
    c.loc[c.force_inconclusive, "verdict"] = "INCONCLUSIVE"
    c.to_csv(RES / "verdicts.csv", index=False)
    cols = ["test_id", "estimate", "t", "p_one_sided", "p_holm", "other_ok", "edge_estimate", "edge_ub95",
            "edge_ub_strict", "threshold_E", "edge_mde80", "verdict"]
    with open(RES / "verdicts.txt", "w") as f:
        f.write(f"{len(c)} primary cells; Holm across all; conditions: {', '.join(conds)}\n\n")
        f.write(c[cols].to_string(index=False, float_format=lambda x: f"{x:.4g}"))
        f.write("\n\n" + c.verdict.value_counts().to_string() + "\n")
    print(open(RES / "verdicts.txt").read())


if __name__ == "__main__":
    main()
