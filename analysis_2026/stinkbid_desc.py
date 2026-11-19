"""
Descriptive estimands, sensitivity rows and exploratory splits of the stink-bid study, as frozen in
analysis_2026/STINKBID_PREREG.md (FROZEN 2026-11-18, commit 72ac2a4): §10.4 "Pre-registered descriptive estimands"
(D-H2, D-H3, D-H5, T1, D12, D6, D7, D-ML, D8, D1-D5, D9, D10, D11, concentration (S16), single events), its
"Sensitivity rows" and "Exploratory splits", the reporting rules of §12 and the descriptive sentences of §11.
Contract: research_notes/Stink bids/build_spec.md, "stinkbid_run.py and stinkbid_desc.py". The stages that call it
(report, desc, explore) and every engine run live in stinkbid_run.py; this module only computes and writes tables
from engine results (stinkbid_engine.run_program dicts, possibly reloaded from the run cache), with the statistics of
stinkbid_stats (none of them is edited). Nothing here reads market data, except D7's accounts (stinkbid_engine.accounts
with the world the runner passes) and the flow split's open interest (stinkbid_data.metrics, real data only).

    python3 -m analysis_2026.stinkbid_desc selftest      # synthetic known answers for the helpers (about 20 s)

Public API
  Samples       per_fill(res, rule, exit, cost, value) / per_bench(res, rule, col) -> one row per fill with y,
                time, day, clusters mb (month-block), ep (episode), qb (quarter-block), hf (half), wk (bid week)
                stat_row(y, clusters, unit, X, j, fe, w) -> estimate, 95% interval, G, G*, MDE (no p-value)
                mean_row(d, ...) -> stat_row of a per-fill mean with the single-event columns (event_cols)
                robust(d) / robust_fit(d, fit) -> concentration (top three episodes) and single events
  Estimands     dh2, dh3, dh5, t1, d12, d6 (km_waits, worst_day), d7 (d7_robinhood), dml (ml_split), d8, d1, d2,
                d3, d4 (capacity_cap), d5, d9, d10 (d10_family), d11; sheet_stats (the sheet's per coin-rung counts)
  Rows          sensitivity(runs, ...) -> the sensitivity rows (F1 and F3 side by side, labelled)
  Explore       explore_tables(runs, ...) -> the exploratory splits, BH within each table
  Sentences     sentence_dh2 / _dh3 / _dh5 / _d8 (§11 descriptive sentences with their numbers), check_wording()
  Stages        compute_desc(runs, ...) / write_desc(dir, tables); compute_explore(...) / write_explore(dir, tables)

Reporting rules applied (§12)
- Every row states its cluster unit, G and G*; descriptive estimands have no p-value. A p-value appears only in the
  exploratory tables (labelled exploratory, BH-adjusted within the table) and in D10's own Holm family (D9 + the four
  H4 methods, used only for the sheet).
- Every Binance (F1) number has its F3 (s = 1%) number beside it (the same statistic on the F3_1 rows) wherever
  the engine's outputs have an F3 counterpart; rows without one say why (f3_note, coding choices 14 and 17); F5 rows are
  labelled "deeper-wick sensitivity: not fills this user could get"; F2 rows "illusion baseline (touch fills)"; F3 and
  F4 rows "Robinhood-route proxy"; U-A and U-C rows "hindsight"; F6 and U-Q2 rows "not built (later session)".
- No descriptive sentence says "made no difference", "is just" or "works" (check_wording asserts it).

Coding choices the pre-registration leaves open (most literal reading; listed in the build report)
 1. Samples: a fill enters a horizon's statistic only if its whole horizon is observed (the engine's `complete`);
    clusters are rebuilt on each analysed sample from its own fill times (month-blocks, episodes and quarter-blocks
    of stinkbid_stats), so a subset (a half, a rung, the F3 rows) has the partition of its own fills.
 2. Single events: "without 2025-10-10 / 2021-05-19" drops the fills of that UTC day; "its top month-block" is the
    month-block with the most fills (ties: the earliest). Concentration: the three largest episodes by fill count;
    for a mean, their share of the summed values (stinkbid_stats.top_k_share); for a regression coefficient (H4,
    D-H3) the share of fills and the coefficient re-fitted without them.
 3. D-H2: Delta90 = the X-HOLD-90 delta (F1, C-RH) against B-TWIN and r - B-POST's mean (same cost), quarter-block
    clusters; the regime caveat (S10) is printed beside it, with K1c's Delta90 when the controls report one.
 4. D-H3: fast = s24 >= 0.75, slow = s24 < 0.5 (fills between are left out); primary Delta = a_episode + b fast +
    rung dummies (episode fixed effects, month-block clusters); drafted: Delta = a + b fast + rung dummies; s6 and s1
    versions of the primary. X-FLIP, F1, C-RH.
 5. D-H5: the U-B run's F1 fills with a finite 365-day knife flag (the engine's VWAP rule; delistings at the §4.1
    value; knife_dl0 / knife_dl100 for the haircut checks); notQ = 1 - membership of U-Q1 (or U-Q1-12) in the
    placement month; quarter = calendar quarter of the fill. The sentence's Y' is the 12-month row's b.
 6. T1: fills and their twins on U-Q1, U-Q1-12 and U-B. The twins' quantiles are taken over the per-fill twin means
    the engine returns (it does not return single twins' lowest prices), so their spread is understated (labelled).
    Item 4 uses the filled dollars at Q = $10k, theta = 1 and the lowest price within 365 days (low365 <= 0.5). Each
    universe's row is repeated without 2025-10-10, without 2021-05-19 and without the top month-block of the run's
    F1 fills (column subset).
 7. D12: the engine's per-fill flags (rec_*), shares over fills whose horizon is observed (finite flags); twins are
    the per-fill twin shares (twin_rec_*) averaged over fills.
 8. D6: W_k and F_k from Kaplan-Meier waits under weekly re-placement: every weekly bid of a (coin, rung) is a start;
    its wait is the time to the first fill among it and the bids that follow it without a break (the next bid
    placed when the previous life ended); a break or the data end censors. theta_k = the TH72 delta (P(M(fill) +
    72 h) / L - 1 minus the twins' 72-hour return) at C-0 on F1, on the route's own spread (RH) on F3, month-block
    clusters; mu*_k = F_k theta_k / W_k with theta_k's interval. Rows per rule: F1 and F3 (s = 1%; theta and mu*
    need a TH72 exit on F3_1, which stinkbid_run's full plan adds). Single events: W, F, theta and mu* with the
    rung's fills on 2025-10-10, on 2021-05-19 or in its top month-block treated as not having happened. B-MKT ("the
    sample's drift", F1 rows): per placement, (bid held 365 days if filled, else the T-bill yield at placement)
    minus the market buy held 365 days, averaged by placement month, stationary bootstrap with 12-month mean blocks
    (S12).
 9. D7: stinkbid_engine.accounts on F1 and F3 (s = 1%), r_res = 0 and 3.35%; every account against its benchmarks
    (B-MIX first): the CAGR difference with a stationary block bootstrap of the paired monthly returns, mean block 6
    months (12 as the sensitivity and for "You could run it on Robinhood"). An account whose 6-month-block interval
    against B-MIX is not above zero is labelled "a low-exposure crypto holding with extra steps". D7-OWN-ML (X-ML as
    the second row) needs X-ML exits on the route's bench rows; the engine computes them on F1 only, so on F3 the
    row is reported as not computed, with no comparison (it would repeat D7-OWN). D7 has no single-event version (an
    account's path cannot drop one day).
10. D8: part 1 = the alert buyer's coin-count advantage at a 72-hour delay (alert_72h); part 2 = the X-HOLD-90 exit
    price over the TH72 price, minus the T-bill yield at the fill pro rata over the days between, quarter-block
    clusters.
11. D5: bids are clustered by placement week, weeks linked when one episode of fills spans them (an episode
    bootstrap over bid-weeks). M3: realized fills per bid against its target p; the sheet: walk-forward by calendar
    year, predicted = (coin-rung fills before the year + 52 p_pool) / (coin-rung bids before the year + 52) with
    p_pool the U-Q1 rate at the rung before the year; on F1 and on F3 (s = 1%).
12. D9 (exchange route, F4): per coin-week, (fill M5f - fill M5a) of the real levels minus the mean of the same
    difference over the placebo shifts both have; D10: per H4 method, a logit of the F1 fill on delta fitted to the
    method's four placebos, evaluated at each real bid's delta; the statistic is the mean of (fill - expected) over
    real bids. Both one-sided (> 0), test_mean's p with the bid-week clusters of choice 11; D10's family = the four
    methods + D9, Holm at 5%. F3 (s = 1%) is reported beside D10.
13. D11: P1's total Delta (the sum over H1's sample) against K3's null totals (stinkbid_stats.d11_percentile); the
    random-time "program" (the sum of the twins' means) is shown as a level only.
14. Sensitivity rows report H1's statistic (mean Delta, X-FLIP rule M, C-RH) and H2R's (mean a_f) with F3's beside;
    size-weighted rows weight each fill by its filled dollars (share_<Q>_<theta> x Q); the bad-print filter drops
    fills whose fill minute had < $1k of seller-initiated notional below L (aggTrades, else C1) or whose index low in
    that minute stayed above L; cost rows report H1 only (the alert buyer's cost under C-EX / C-BUS is not
    specified). Delisting rows: the engine values twins at the primary rule only (no twin mean per delisting rule),
    and r_dl_* - twin_mean would compare fills and twins under different valuations (draft §4.4: "Twins and
    benchmarks follow the same rule"; K1d), so each row reports the fills' mean r_f under the valuation ("fill
    valuation only (twins unchanged)") with the primary valuation's row beside it, the change in mean r_f
    (change_vs_primary) and the number of delisted exits, on F1 and on F3. Rows that have no F3 counterpart in the
    engine's outputs (flip grid, spot cost scenarios, size weights, twin variants and drift, bad prints) say why in
    f3_note.
15. Exploratory p-values: one-sided (> 0) for means, two-sided (twice the smaller one-sided p) for differences and
    slopes; each is max(p_WCR, p_G*) (the §10.2 rule), then BH within its table, separately for the F1 rows and the
    F3 rows beside them. The F1 depth gradient's slope row is the one the sheet's "best rung" reads (q < 0.10).
16. "Every estimate is also shown without 2025-10-10, without 2021-05-19 and without its top month-block": every
    per-fill mean row carries those three means (event_cols; weighted rows weighted); exploratory differences and
    slopes re-fit their coefficient (event_coefs); D-H5 re-fits b without them; regression headlines (H4, D-H3)
    re-fit their coefficient (robust_fit); D12 adds the three as splits of "all"; T1 adds them as rows (subset);
    D6 as W / F / theta / mu* columns (coding choice 8). The top month-block is the one with the most fills of the
    estimate's own sample (event_drop_masks).
17. F3 beside the descriptive estimands where the engine's plan provides F3 rows: D-H2 (X-HOLD-90 on F3), D-H3
    (primary version; speeds are the F1 fill's), D-ML (B-ML), D8 parts 1 and 2 (part 2 with the full plan's TH72 on
    F3), D12, D6, D10, the sheet's counts, every sensitivity row that has an F3 counterpart and every exploratory
    row. T1 and D-H5 have no F3 version (the engine computes their fields on F1 only) and say so.
18. sheet_stats (desc/sheet_coin_rung.csv): per coin and rung of P1 on U-Q1, the weekly F1 and F3 fill rates, the
    shrunken estimate (n_fill + 52 p_pool) / (n_bids + 52), Wilson intervals widened by sqrt(phi) of the rung's
    yearly counts (S14), "N fills in E episodes", the Kaplan-Meier median wait and no-fill chance on each row's own
    rule (§7 "The sheet's numbers come from F3"; the F1 row is labelled "Binance spot (upper bound)"), and the
    capacity quantiles with Q_max (the Binance spot book of the F1 fills, on both rows; context only on the
    market-maker route), counts and capacity only, for the sheet agent to read.
19. worst_day (§11 "On the worst day, S% of the live bids ... filled the same day"): a bid is live on a day when its
    life overlaps the day and it had not filled before the day's start; each (coin, rung, variant) order slot counts
    once per day (a Monday's outgoing and incoming bids of a slot are one live order).
"""
from __future__ import annotations

import json
import math
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import stinkbid_stats as sbs  # noqa: E402

# ============================================================================ constants (prereg section in brackets)
MIN_NS = 60_000_000_000
DAY_M = 1440
B_DEFAULT = sbs.B_BOOT                               # 9,999 (§10.2)
SEED = sbs.SEED
EVENT_DAYS = ("2025-10-10", "2021-05-19")            # §10.4 single events
FAST, SLOW = 0.75, 0.5                               # §10.4 D-H3
Q_SIZES = (("1k", 1_000.0), ("10k", 10_000.0), ("100k", 100_000.0))   # §6.3
THETAS = (1.0, 0.25)                                 # §7
RUNGS_P1 = (6.0, 8.0, 10.0)
KNIFE = 0.5
BAD_PRINT_USD = 1_000.0                              # §4.1 bad-print sensitivity
R_RES = (0.0, 0.0335)                                # §9
D7_BLOCKS = (6.0, 12.0)                              # §10.4 D7, S12
D6_BLOCK = 12.0                                      # S12
D5_LEVEL = 0.90
LABEL_HINDSIGHT = "hindsight"
LABEL_F5 = "deeper-wick sensitivity: not fills this user could get"
LABEL_F2 = "illusion baseline (touch fills)"
LABEL_RH = "Robinhood-route proxy"
LABEL_NOT_BUILT = "not built (later session)"
LABEL_EXTRA_STEPS = "a low-exposure crypto holding with extra steps"
LABEL_DL = ("the engine values twins at the primary rule only (no twin mean per delisting rule), so no Delta under "
            "this valuation is computed")
F3_NOTE = {"grid": "no F3 row: the engine's plan has the flip grid on F1 only",
           "cost": "no F3 row: the F3 route has its own costs (the spread is embedded); C-0 / C-EX / C-BUS are spot "
                   "cost scenarios",
           "size": "no F3 row: F3 positions are Q (capacity is context only on the market-maker route), so it would "
                   "repeat the primary F3_1 row",
           "benchmark": "no F3 row: the engine computes these twins and the drift on (F1, X-FLIP) only",
           "bad prints": "no F3 row: the rule concerns Binance spot prints in the F1 fill minute; F3 fills are decided "
                         "on the index"}
HYPE_NOTE = ("HYPE: about 17 months of Binance perpetual data and 2 months of Binance spot. Its only deep-wick day "
             "(2025-10-10) came 13 days before Robinhood listed it. HYPE is a venue token: its value depends on "
             "Hyperliquid's volume and solvency, a risk no price history here can measure (FTT, the token of FTX, fell "
             "97.6%). Not tradable on Robinhood for New York residents.")
REGIME_CAVEAT = ("Random buys here exclude the six months around each fill, so the comparison also reflects whether "
                 "crashes fell in bear or bull stretches.")
FORBIDDEN = ("made no difference", "is just", "works")          # §11 wording
NAN = float("nan")


# ============================================================================ small helpers
def _f(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return NAN
    return v


def route_cost(rule: str) -> str:
    """The cost label of a rule's route in the engine's outcome rows: C-RH on spot rules (F1, F2, F5), RH on the
    market-maker route (F3*), C-EX on the exchange route (F4)."""
    if rule.startswith("F3"):
        return "RH"
    return "C-EX" if rule == "F4" else "C-RH"


def rule_label(rule: str) -> str:
    if rule == "F2":
        return LABEL_F2
    if rule == "F5":
        return LABEL_F5
    if rule.startswith("F3") or rule == "F4":
        return LABEL_RH
    if rule == "F6":
        return LABEL_NOT_BUILT
    return ""


def ts_min(m) -> pd.DatetimeIndex:
    """Minutes since 1970 UTC -> tz-aware timestamps."""
    return pd.to_datetime(np.asarray(m, np.int64) * MIN_NS, utc=True)


def fmt_pct(x, nd: int = 1, sign: bool = False) -> str:
    x = _f(x)
    if not np.isfinite(x):
        return "n/a"
    return f"{100 * x:+.{nd}f}%" if sign else f"{100 * x:.{nd}f}%"


def fmt_ci(lo, hi, nd: int = 1) -> str:
    return f"95% CI {fmt_pct(lo, nd, True)} to {fmt_pct(hi, nd, True)}"


def fmt_pts(x, nd: int = 1, sign: bool = True) -> str:
    x = _f(x)
    if not np.isfinite(x):
        return "n/a"
    return f"{100 * x:+.{nd}f}" if sign else f"{100 * x:.{nd}f}"


def unc(row: dict) -> str:
    """The uncertainty note every interval carries (§12): cluster unit, G and G*."""
    return (f"{int(row.get('n', 0) or 0)} fills, {row.get('unit', '')} clusters G = {int(row.get('G', 0) or 0)}, "
            f"G* = {_f(row.get('gstar')):.1f}")


def check_wording(texts) -> list:
    """§11 wording rule for descriptive rows: the phrases that must not appear (returns the offending texts)."""
    bad = []
    for t in texts:
        low = str(t).lower()
        if any(w in low for w in FORBIDDEN):
            bad.append(t)
    return bad


def _empty(cols) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=float) for c in cols})


def add_clusters(d: pd.DataFrame, tcol: str = "time") -> pd.DataFrame:
    """Clusters of a per-fill sample from its own fill times (coding choice 1): mb month-block, ep episode, qb
    quarter-block, hf half (0: 2020-22, 1: 2023-), wk bid week, mo calendar month (YYYYMM), qu calendar quarter
    (YYYYQ), yr fill year, day UTC fill day."""
    names = ("mb", "ep", "qb", "hf", "wk", "mo", "qu", "yr", "day")
    d = d.drop(columns=[c for c in names if c in d])
    if not len(d):
        new = {c: pd.Series(dtype=np.int64, index=d.index) for c in names[:-1]}
        new["day"] = pd.Series(dtype="datetime64[s]", index=d.index)
    else:
        t = d[tcol]
        new = dict(mb=sbs.month_blocks(t)[0], ep=sbs.episodes(t)[0], qb=sbs.quarter_blocks(t)[0],
                   hf=sbs.half_key(t), wk=sbs.week_key(t), mo=sbs.month_key(t), qu=sbs.quarter_key(t),
                   yr=sbs.year_key(t), day=sbs.fill_days(t))
    return pd.concat([d, pd.DataFrame(new, index=d.index)], axis=1)


def per_fill(res: dict, rule: str = "F1", exit: str = "FLIP", cost: str | None = None, value: str = "delta",
             complete: bool = True) -> pd.DataFrame:
    """One row per fill of `rule` with an outcome row (rule, exit, cost): the fill's columns, the outcome's columns
    and y = `value` (delta, r, delta_x30, delta_pool, delta_drift, r_dl_last / r_dl0 / r_dl100 (the fill's r_f under
    a delisting valuation), or dl_last / dl0 / dl100 = r_dl_* - r, the fill-side change of r_f under that valuation:
    the engine values twins at the primary rule only, so no Delta under another valuation exists; coding choice 14).
    Only fills whose whole horizon is observed (complete) and with a finite y; clusters from the fill times. The
    fills' own `delta` (the bid's depth delta(L) in sigma) is renamed `depth`, so `delta` is the outcome's Delta_f."""
    F, O = res.get("fills"), res.get("outcomes")
    tcol = "t_" + rule
    if F is None or O is None or not len(F) or not len(O) or tcol not in F or "rule" not in O:
        return add_clusters(pd.DataFrame({"y": pd.Series(dtype=float), "time": pd.Series(dtype="datetime64[ns, UTC]")}))
    cost = cost or route_cost(rule)
    o = O[(O["rule"] == rule) & (O["exit"] == exit) & (O["cost"] == cost)]
    if complete and "complete" in o:
        o = o[o["complete"].astype(bool)]
    keep = [c for c in o.columns if c not in ("coin", "rule", "exit", "lat", "cost")]
    f = F[F[tcol].to_numpy() >= 0].rename(columns={"delta": "depth"})      # the bid's depth in sigma, not Delta_f
    d = f.merge(o[keep], on="fill_id", how="inner", suffixes=("", "_o"))
    if value.startswith("dl"):
        # never r_dl_* - twin_mean: twin_mean holds the twins valued at the primary rule (finding of the review)
        y = (d["r_" + value] - d["r"]).to_numpy(float)
    else:
        y = d[value].to_numpy(float) if value in d else np.full(len(d), np.nan)
    d = d.loc[np.isfinite(y)].reset_index(drop=True)
    tf = d[tcol].to_numpy(np.int64)
    d = pd.concat([d.drop(columns=[c for c in ("y", "time", "t_fill") if c in d]),
                   pd.DataFrame({"y": y[np.isfinite(y)], "time": ts_min(tf), "t_fill": tf}, index=d.index)], axis=1)
    return add_clusters(d)


def per_bench(res: dict, rule: str = "F1", col: str = "alert_M") -> pd.DataFrame:
    """One row per fill of `rule` with a finite benchmark column (bench, e.g. alert_M = a_f of H2R, knife, ml_a)."""
    F, Bn = res.get("fills"), res.get("bench")
    tcol = "t_" + rule
    if F is None or Bn is None or not len(F) or not len(Bn) or tcol not in F or col not in Bn:
        return add_clusters(pd.DataFrame({"y": pd.Series(dtype=float), "time": pd.Series(dtype="datetime64[ns, UTC]")}))
    b = Bn[Bn["rule"] == rule].drop(columns=["rule", "coin"], errors="ignore")
    f = F[F[tcol].to_numpy() >= 0].rename(columns={"delta": "depth"})      # the bid's depth in sigma
    d = f.merge(b, on="fill_id", how="inner", suffixes=("", "_b"))
    y = pd.to_numeric(d[col], errors="coerce").to_numpy(float)
    d = d.loc[np.isfinite(y)].reset_index(drop=True)
    tf = d[tcol].to_numpy(np.int64)
    d = pd.concat([d.drop(columns=[c for c in ("y", "time", "t_fill") if c in d]),
                   pd.DataFrame({"y": y[np.isfinite(y)], "time": ts_min(tf), "t_fill": tf}, index=d.index)], axis=1)
    return add_clusters(d)


def stat_row(y, clusters, unit: str = "month-block", X=None, j: int = 0, fe=None, w=None, B: int = B_DEFAULT,
             seed=SEED) -> dict:
    """A descriptive estimate (§10.4): estimate, 95% interval (stinkbid_stats.describe: the union of the wild
    bootstrap-t and the t(G*-1) intervals), SE, G, G*, MDE; no p-value."""
    y = np.asarray(y, float)
    out = dict(n=0, G=0, gstar=NAN, unit=unit, estimate=NAN, ci_lo=NAN, ci_hi=NAN, se=NAN, mde=NAN)
    if len(y) == 0:
        return out
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = sbs.describe(y, clusters, X=X, j=j, fe=fe, weights=w, B=B, seed=seed, unit=unit)
    ci = r.get("ci95", (NAN, NAN))
    out.update(n=int(r.get("n", 0)), G=int(r.get("G", 0)), gstar=_f(r.get("gstar")), estimate=_f(r.get("estimate")),
               ci_lo=_f(ci[0]), ci_hi=_f(ci[1]), se=_f(r.get("se")), mde=_f(r.get("mde")))
    return out


def event_cols(d: pd.DataFrame, value: str = "y", w=None) -> dict:
    """§10.4 single events for a (weighted) mean: without 2025-10-10, without 2021-05-19 (UTC fill days) and without
    the top month-block (the one with the most fills; coding choice 2)."""
    out = {f"without_{dd}": NAN for dd in EVENT_DAYS}
    out["without_top_block"] = NAN
    if not len(d) or "day" not in d:
        return out
    y = d[value].to_numpy(float)
    ww = np.ones(len(y)) if w is None else np.asarray(w, float)
    ok = np.isfinite(y) & np.isfinite(ww) & (ww > 0)

    def m(mask):
        mask = mask & ok
        sw = ww[mask].sum()
        return float((ww[mask] * y[mask]).sum() / sw) if mask.any() and sw > 0 else NAN
    day = d["day"].to_numpy()
    for dd in EVENT_DAYS:
        out[f"without_{dd}"] = m(day != np.datetime64(dd))
    tb = _top_block(d["mb"].to_numpy())
    out["without_top_block"] = m(d["mb"].to_numpy() != tb)
    return out


EVENT_NAMES = tuple(f"without_{dd}" for dd in EVENT_DAYS) + ("without_top_block",)
EVENT_LABELS = {**{f"without_{dd}": f"without {dd}" for dd in EVENT_DAYS},
                "without_top_block": "without the top month-block"}


def _dti(x) -> pd.DatetimeIndex:
    """Timestamps (tz-aware Series / Index / datetime64 array) as a UTC DatetimeIndex."""
    if x is None or len(x) == 0:
        return pd.DatetimeIndex([], tz="UTC")
    return pd.DatetimeIndex(pd.to_datetime(x, utc=True))


def event_drop_masks(t_ref, t=None) -> dict:
    """§10.4 single events as drop masks over fill times t (default t_ref): {"without_2025-10-10",
    "without_2021-05-19", "without_top_block"} -> bool arrays, True = the fill is dropped. The top month-block is the
    month-block of t_ref (the estimate's own fills) with the most fills (ties: the earliest; coding choice 2); its
    calendar months are dropped from t."""
    tr = _dti(t_ref)
    tt = tr if t is None else _dti(t)
    day = sbs.fill_days(tt) if len(tt) else np.zeros(0, "datetime64[D]")
    out = {f"without_{dd}": (day == np.datetime64(dd)) for dd in EVENT_DAYS}
    out["without_top_block"] = np.zeros(len(tt), bool)
    if len(tr) and len(tt):
        _, tab = sbs.month_blocks(tr)
        top = tab.sort_values(["n_fills", "block"], ascending=[False, True]).iloc[0]
        mm = tt.tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("datetime64[M]").astype(np.int64)
        out["without_top_block"] = np.isin(mm, np.asarray(list(top["periods"]), np.int64))
    return out


def event_coefs(d: pd.DataFrame, X, j: int, value: str = "y") -> dict:
    """§10.4 single events for a regression coefficient (an exploratory difference or slope): coefficient j of an
    OLS of `value` on X re-fitted without 2025-10-10, without 2021-05-19 and without the top month-block (the one with
    the most fills; coding choice 2). NaN where not identified."""
    out = {k: NAN for k in EVENT_NAMES}
    if not len(d) or "day" not in d or X is None:
        return out
    y = d[value].to_numpy(float)
    X = np.asarray(X, float)
    day = d["day"].to_numpy()
    tb = _top_block(d["mb"].to_numpy())
    masks = {f"without_{dd}": day != np.datetime64(dd) for dd in EVENT_DAYS}
    masks["without_top_block"] = d["mb"].to_numpy() != tb
    for k, m in masks.items():
        m = m & np.isfinite(y)
        if m.sum() < X.shape[1] + 1:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = sbs.ols_fe(y[m], X[m])
        if r["coef"] is not None and r["ident"]:
            out[k] = _f(r["coef"][j])
    return out


def mean_row(d: pd.DataFrame, value: str = "y", cl: str = "mb", unit: str = "month-block", w=None,
             B: int = B_DEFAULT, events: bool = True) -> dict:
    """stat_row of a per-fill (weighted) mean with the single-event columns (events=True)."""
    if not len(d):
        r = stat_row([], [], unit)
        return dict(r, **event_cols(d)) if events else r
    r = stat_row(d[value].to_numpy(float), d[cl].to_numpy(), unit, w=w, B=B)
    if events:
        r.update(event_cols(d, value, w))
    return r


def p_one(y, clusters, X=None, j: int = 0, fe=None, B: int = B_DEFAULT, seed=SEED) -> tuple:
    """(one-sided p for > 0 by the §10.2 max rule, the test row). NaN when not identified."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = sbs.test_coef(y, X, j, clusters, fe, None, None, 0.0, B, seed)
    return _f(r.get("p_decide")), r


def p_two(y, clusters, X=None, j: int = 0, fe=None, B: int = B_DEFAULT, seed=SEED) -> tuple:
    """Two-sided exploratory p: twice the smaller one-sided p (each by the max rule), capped at 1 (choice 15)."""
    y = np.asarray(y, float)
    pu, r = p_one(y, clusters, X, j, fe, B, seed)
    pd_, _ = p_one(-y, clusters, X, j, fe, B, seed)
    if not (np.isfinite(pu) and np.isfinite(pd_)):
        return NAN, r
    return float(min(1.0, 2 * min(pu, pd_))), r


# ============================================================================ concentration and single events
def _top_block(labels) -> object:
    u, c = np.unique(np.asarray(labels), return_counts=True)
    if not len(u):
        return None
    o = np.lexsort((u, -c))
    return u[o[0]]


def _episode_names(d: pd.DataFrame, groups) -> list:
    if not len(d):
        return []
    _, tab = sbs.episodes(d["time"])
    out = []
    for g in groups:
        r = tab[tab.episode == g]
        if len(r):
            a, b = str(r.start.iloc[0])[:10], str(r.end.iloc[0])[:10]
            out.append(a if a == b else f"{a}..{b}")
    return out


def robust(d: pd.DataFrame, value: str = "y") -> dict:
    """S16 and §10.4 for a per-fill mean: the share of the total from the three largest episodes, the mean without
    them, their dates, and the mean without 2025-10-10, without 2021-05-19 and without the top month-block."""
    out = dict(estimate=NAN, top3_share=NAN, top3_basis="sum", top3_without=NAN, top3_names=[],
               top3_above_half=False, top_block=None, without_top_block=NAN)
    for day in EVENT_DAYS:
        out[f"without_{day}"] = NAN
        out[f"n_{day}"] = 0
    if not len(d):
        return out
    y = d[value].to_numpy(float)
    out["estimate"] = float(np.mean(y))
    top = sbs.top_k_share(y, d["ep"].to_numpy(), 3)
    out.update(top3_share=_f(top["share"]), top3_without=_f(top["mean_without"]),
               top3_names=_episode_names(d, top["groups"]), top3_above_half=bool(top["above_half"]))
    for day in EVENT_DAYS:
        m = d["day"].to_numpy() != np.datetime64(day)
        out[f"without_{day}"] = float(np.mean(y[m])) if m.any() else NAN
        out[f"n_{day}"] = int((~m).sum())
    tb = _top_block(d["mb"].to_numpy())
    m = d["mb"].to_numpy() != tb
    out["top_block"] = None if tb is None else int(tb)
    out["without_top_block"] = float(np.mean(y[m])) if m.any() else NAN
    return out


def robust_fit(d: pd.DataFrame, fit) -> dict:
    """The same for a regression coefficient: fit(mask) -> estimate on the masked rows (coding choice 2: the top
    three episodes' share of fills, and the coefficient re-fitted without them)."""
    n = len(d)
    out = dict(estimate=NAN, top3_share=NAN, top3_basis="fills", top3_without=NAN, top3_names=[],
               top3_above_half=False, top_block=None, without_top_block=NAN)
    for day in EVENT_DAYS:
        out[f"without_{day}"] = NAN
        out[f"n_{day}"] = 0
    if not n:
        return out
    allm = np.ones(n, bool)
    out["estimate"] = _f(fit(allm))
    ep = d["ep"].to_numpy()
    u, c = np.unique(ep, return_counts=True)
    o = np.lexsort((u, -c))
    top = u[o[:3]]
    sel = np.isin(ep, top)
    out.update(top3_share=float(sel.mean()), top3_without=_f(fit(~sel)) if (~sel).any() else NAN,
               top3_names=_episode_names(d, top), top3_above_half=bool(sel.mean() > 0.5))
    for day in EVENT_DAYS:
        m = d["day"].to_numpy() != np.datetime64(day)
        out[f"without_{day}"] = _f(fit(m)) if m.any() else NAN
        out[f"n_{day}"] = int((~m).sum())
    tb = _top_block(d["mb"].to_numpy())
    m = d["mb"].to_numpy() != tb
    out["top_block"] = None if tb is None else int(tb)
    out["without_top_block"] = _f(fit(m)) if m.any() else NAN
    return out


def concentration_sentence(rb: dict, passed: bool) -> str:
    """S16: above 50%, the sentence names the three largest episodes."""
    if not rb.get("top3_above_half"):
        return ""
    names = ", ".join(rb.get("top3_names") or [])
    if passed:
        return f"Most of it came from three crashes ({names}); it pays only if crashes like those recur."
    what = "of the total" if rb.get("top3_basis") == "sum" else "of the fills"
    return f"More than half {what} came from three crash episodes ({names})."


# ============================================================================ bid-level clusters (D5, D9, D10)
def bid_clusters(t0_min, fill_min) -> np.ndarray:
    """Placement weeks linked when one episode of fills spans them (coding choice 11): labels per bid."""
    t0 = np.asarray(t0_min, np.int64)
    fm = np.asarray(fill_min, float)
    wk = sbs.week_key(ts_min(t0))
    if not len(wk):
        return np.zeros(0, np.int64)
    parent = {int(w): int(w) for w in np.unique(wk)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    filled = np.isfinite(fm) & (fm >= 0)
    if filled.any():
        ep, _ = sbs.episodes(ts_min(fm[filled].astype(np.int64)))
        wf = wk[filled]
        for e in np.unique(ep):
            ws = np.unique(wf[ep == e])
            for a, b in zip(ws[:-1], ws[1:]):
                ra, rb = find(int(a)), find(int(b))
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(int(w)) for w in wk], np.int64)


def bid_fill_table(res: dict, rules=("F1",)) -> pd.DataFrame:
    """Bids with their fill minute per rule (-1 = no fill): bid_id, coin, rung, variant, method, real, shift, cw,
    t0, live_from, life_end, delta, month, ml_d0 and t_<rule>."""
    B, F = res.get("bids"), res.get("fills")
    if B is None or not len(B):
        return pd.DataFrame()
    b = B.copy()
    for r in rules:
        tcol = "t_" + r
        if F is not None and len(F) and tcol in F:
            m = F[["bid_id", tcol]]
            b = b.merge(m, on="bid_id", how="left")
            b[tcol] = b[tcol].fillna(-1).astype(np.int64)
        else:
            b[tcol] = -1
    return b


# ============================================================================ D-H2, D-H3 (§10.4)
def dh2(res: dict, B: int = B_DEFAULT, k1c=None) -> dict:
    """D-H2 OWN: per fill Delta90 against B-TWIN (+-182 d) and against B-POST, X-HOLD-90, quarter-block clusters, with
    the regime caveat (S10) and, when given, K1c's Delta90 ("what regime timing alone produces")."""
    d = per_fill(res, "F1", "HOLD90", "C-RH", "delta")
    twin = mean_row(d, "y", "qb", "quarter-block", B=B)
    twin["robust"] = robust(d)
    dp = per_fill(res, "F1", "HOLD90", "C-RH", "r")
    pb = per_bench(res, "F1", "post_mean_C-RH")[["fill_id", "y"]].rename(columns={"y": "post"})
    dp = dp.merge(pb, on="fill_id", how="inner")
    dp["y"] = dp["y"] - dp["post"]
    dp = add_clusters(dp[np.isfinite(dp["y"].to_numpy(float))].reset_index(drop=True))
    post = mean_row(dp, "y", "qb", "quarter-block", B=B)
    d3 = per_fill(res, "F3_1", "HOLD90", "RH", "delta")
    f3 = mean_row(d3, "y", "qb", "quarter-block", B=B)
    return dict(twin=twin, post=post, f3=f3, caveat=REGIME_CAVEAT, k1c=k1c)


def _rung_dummies(r: np.ndarray) -> np.ndarray:
    lev = sorted(pd.unique(r))
    if len(lev) <= 1:
        return np.zeros((len(r), 0))
    return np.column_stack([(r == v).astype(float) for v in lev[1:]])


def dh3(res: dict, B: int = B_DEFAULT) -> dict:
    """D-H3 SPEED: fast (s >= 0.75) against slow (s < 0.5) fills at the same rung, X-FLIP; primary with episode fixed
    effects, the drafted version (no fixed effects) beside it, and the s6 and s1 versions (coding choice 4)."""
    d = per_fill(res, "F1", "FLIP", "C-RH", "delta")
    out = {}
    for sp in ("s24", "s6", "s1"):
        if not len(d) or sp not in d:
            out[sp] = dict(primary=stat_row([], [], "month-block"), drafted=stat_row([], [], "month-block"),
                           n_fast=0, n_slow=0)
            continue
        s = d[sp].to_numpy(float)
        sel = (s >= FAST) | (s < SLOW)
        g = d[sel].reset_index(drop=True)
        fast = (g[sp].to_numpy(float) >= FAST).astype(float)
        R = _rung_dummies(g["rung"].to_numpy(float))
        y = g["y"].to_numpy(float)
        Xp = np.column_stack([fast, R]) if R.shape[1] else fast[:, None]
        prim = stat_row(y, g["mb"].to_numpy(), "month-block", X=Xp, j=0, fe=g["ep"].to_numpy(), B=B)
        Xd = np.column_stack([np.ones(len(g)), fast, R])
        draft = stat_row(y, g["mb"].to_numpy(), "month-block", X=Xd, j=1, B=B)
        rec = dict(primary=prim, drafted=draft, n_fast=int(fast.sum()), n_slow=int((1 - fast).sum()))
        if sp == "s24" and len(g):
            def fit(mask, g=g, y=y, Xp=Xp):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    r = sbs.ols_fe(y[mask], Xp[mask], g["ep"].to_numpy()[mask], g["mb"].to_numpy()[mask])
                return NAN if r["coef"] is None else _f(r["coef"][0])
            rec["robust"] = robust_fit(g, fit)
        out[sp] = rec
    # beside it, the primary version on the F3 (s = 1%) rows (speeds are the F1 fill's; F3-only fills have none)
    d3 = per_fill(res, "F3_1", "FLIP", "RH", "delta")
    if len(d3) and "s24" in d3:
        s = d3["s24"].to_numpy(float)
        g = d3[(s >= FAST) | (s < SLOW)].reset_index(drop=True)
        if len(g):
            fast = (g["s24"].to_numpy(float) >= FAST).astype(float)
            R = _rung_dummies(g["rung"].to_numpy(float))
            Xp = np.column_stack([fast, R]) if R.shape[1] else fast[:, None]
            out["F3_1"] = dict(primary=stat_row(g["y"].to_numpy(float), g["mb"].to_numpy(), "month-block", X=Xp, j=0,
                                                fe=g["ep"].to_numpy(), B=B), label=LABEL_RH,
                               n_fast=int(fast.sum()), n_slow=int((1 - fast).sum()))
    return out


# ============================================================================ D-H5, T1
def dh5_rows(res_ub: dict, group_col: str = "in_U_Q1", B: int = B_DEFAULT) -> dict:
    """D-H5 KNIFE (§10.4) for one population split: notQ = 1 - group membership; the model knife = a + b notQ +
    rung dummies + gamma p0 with two-way coin x quarter clusters; the sigma30-decile and Ibragimov-Müller
    sensitivities, the coin whose removal lowers b most, and the 0% / 100% delisting haircuts."""
    d = per_bench(res_ub, "F1", "knife")
    out = dict(group=group_col, n=int(len(d)))
    if not len(d) or group_col not in d:
        out.update(primary=None, note="no fills with a 365-day knife flag" if not len(d) else f"no {group_col}")
        return out
    notq = 1.0 - d[group_col].astype(bool).to_numpy().astype(float)
    args = (d["y"].to_numpy(float), notq, d["rung"].to_numpy(float), d["sigma30"].to_numpy(float),
            d["coin"].astype(str).to_numpy(), d["qu"].to_numpy())

    def safe(fn, *a, **k):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return fn(*a, **k)
        except Exception as e:                               # a degenerate design (e.g. one group) is reported
            return dict(error=repr(e))
    out["primary"] = safe(sbs.dh5_fit, *args)
    out["deciles"] = safe(sbs.dh5_fit, *args, vol_control="decile")
    out["im_years"] = safe(sbs.dh5_im, args[0], notq, args[2], args[3], d["yr"].to_numpy())
    wc = safe(sbs.dh5_drop_worst_coin, *args)
    out["drop_worst_coin"] = dict(b=wc[0], coin=wc[1]) if isinstance(wc, tuple) else wc
    for k in ("knife_dl0", "knife_dl100"):
        if k in d:
            kk = pd.to_numeric(d[k], errors="coerce").to_numpy(float)
            ok = np.isfinite(kk)
            out[k] = safe(sbs.dh5_fit, kk[ok], notq[ok], args[2][ok], args[3][ok], args[4][ok], args[5][ok])
    out["n_q"] = int((notq == 0).sum())
    out["n_rest"] = int((notq == 1).sum())
    # §10.4 single events: b re-fitted without 2025-10-10, without 2021-05-19 and without the top month-block
    def b_of(mask):
        r = safe(sbs.dh5_fit, *[a[mask] for a in args])
        return _f(r.get("b")) if isinstance(r, dict) else NAN
    ev = {}
    day = d["day"].to_numpy()
    for dd in EVENT_DAYS:
        mk = day != np.datetime64(dd)
        ev[f"without_{dd}"] = b_of(mk) if (~mk).any() else _f((out.get("primary") or {}).get("b"))
    tb = _top_block(d["mb"].to_numpy())
    ev["without_top_block"] = b_of(d["mb"].to_numpy() != tb)
    out["single_events"] = ev
    return out


def dh5(res_ub: dict, B: int = B_DEFAULT) -> dict:
    """D-H5's two rows: U-Q1 against the rest of U-B, and U-Q1-12 against its rest (the U-B run's fills)."""
    return {"U_Q1": dh5_rows(res_ub, "in_U_Q1", B), "U_Q1_12": dh5_rows(res_ub, "in_U_Q1_12", B)}


def t1(runs: dict, B: int = B_DEFAULT) -> tuple:
    """T1 tail table (§10.4) for fills and twins on U-Q1, U-Q1-12 and U-B: knife share, median / 10th percentile of
    the lowest price within 30 / 90 / 365 days relative to L, share delisted, the per-episode share of filled dollars
    50% or more under water within 365 days, and the excess knife rate with an episode-cluster interval. Each
    universe also has rows without 2025-10-10, without 2021-05-19 and without its top month-block (§10.4 single
    events; the month-block of the run's F1 fills with the most fills). Returns (summary table, per-episode table
    of the "all" rows)."""
    rows, eps = [], []
    for name, res in runs.items():
        if res is None:
            continue
        d = per_bench(res, "F1", "knife")
        F = res.get("fills")
        Bn = res.get("bench")
        fb = pd.DataFrame()
        if F is not None and Bn is not None and len(Bn) and "low30" in Bn and len(F) and "t_F1" in F:
            b = Bn[Bn["rule"] == "F1"].drop(columns=["coin"], errors="ignore")
            fb = F[F["t_F1"].to_numpy() >= 0][[c for c in ("fill_id", "t_F1", "share_10k_1") if c in F]].merge(
                b, on="fill_id", how="inner")
        ref = ts_min(F.loc[F["t_F1"] >= 0, "t_F1"].to_numpy(np.int64)) if F is not None and len(F) and "t_F1" in F \
            else ts_min([])
        for sub, k in [("all", None)] + [(EVENT_LABELS[k], k) for k in EVENT_NAMES]:
            dk, fk = d, fb
            if k is not None:
                dk = d[~event_drop_masks(ref, d["time"])[k]] if len(d) else d
                fk = fb[~event_drop_masks(ref, ts_min(fb["t_F1"].to_numpy(np.int64)))[k]] if len(fb) else fb
            base, ep_rows = _t1_row(name, sub, dk, fk, B)
            rows.append(base)
            if k is None:
                eps += ep_rows
    tab = pd.DataFrame(rows)
    return tab, pd.DataFrame(eps)


def _t1_row(name: str, subset: str, d: pd.DataFrame, fb: pd.DataFrame, B: int) -> tuple:
    """One T1 row: d = the 365-day knife sample (per_bench 'knife'), fb = F1 fills merged with their bench row."""
    base = dict(universe=name, subset=subset, n=int(len(d)))
    if len(d):
        tk = pd.to_numeric(d["twin_knife"], errors="coerce").to_numpy(float) if "twin_knife" in d \
            else np.full(len(d), NAN)
        base.update(knife_fills=float(d["y"].mean()),
                    knife_twins=float(np.nanmean(tk)) if np.isfinite(tk).any() else NAN)
        exc = d["y"].to_numpy(float) - tk
        ok = np.isfinite(exc)
        if ok.any():
            bt = sbs.ratio_cluster_bootstrap(exc[ok], np.ones(ok.sum()), d["ep"].to_numpy()[ok], B=B)
            base.update(excess_knife=bt["estimate"], excess_lo=bt["ci"][0], excess_hi=bt["ci"][1],
                        excess_G=bt["G"], excess_unit="episode")
    eps = []
    # lowest prices and delistings use every fill whose window is observed (not only 365-day knife fills)
    if len(fb):
        for h in (30, 90, 365):
            v = pd.to_numeric(fb.get(f"low{h}"), errors="coerce").to_numpy(float)
            tw = pd.to_numeric(fb.get(f"twin_low{h}"), errors="coerce").to_numpy(float)
            v, tw = v[np.isfinite(v)], tw[np.isfinite(tw)]
            base[f"low{h}_median"] = float(np.median(v)) if len(v) else NAN
            base[f"low{h}_p10"] = float(np.quantile(v, 0.10)) if len(v) else NAN
            base[f"low{h}_twins_median"] = float(np.median(tw)) if len(tw) else NAN
            base[f"low{h}_twins_p10"] = float(np.quantile(tw, 0.10)) if len(tw) else NAN
            dl = pd.to_numeric(fb.get(f"delisted{h}"), errors="coerce").to_numpy(float)
            tdl = pd.to_numeric(fb.get(f"twin_delisted{h}"), errors="coerce").to_numpy(float)
            base[f"delisted{h}_fills"] = float(np.nanmean(dl)) if np.isfinite(dl).any() else NAN
            base[f"delisted{h}_twins"] = float(np.nanmean(tdl)) if np.isfinite(tdl).any() else NAN
        # item 4: per episode, the share of filled dollars 50% or more under water within 365 days
        g = fb[np.isfinite(pd.to_numeric(fb["low365"], errors="coerce").to_numpy(float))]
        if len(g):
            g = add_clusters(g.assign(time=ts_min(g["t_F1"].to_numpy(np.int64))))
            dollars = (pd.to_numeric(g.get("share_10k_1"), errors="coerce").fillna(1.0).to_numpy(float) * 10_000.0
                       if "share_10k_1" in g else np.full(len(g), 10_000.0))
            under = pd.to_numeric(g["low365"], errors="coerce").to_numpy(float) <= KNIFE
            _, etab = sbs.episodes(g["time"])
            for e in np.unique(g["ep"].to_numpy()):
                m = g["ep"].to_numpy() == e
                r = etab[etab.episode == e]
                eps.append(dict(universe=name, episode=int(e), start=str(r.start.iloc[0])[:10],
                                end=str(r.end.iloc[0])[:10], fills=int(m.sum()), dollars=float(dollars[m].sum()),
                                share_underwater_50=float(dollars[m & under].sum() / dollars[m].sum())
                                if dollars[m].sum() > 0 else NAN))
            base["worst_episode_underwater_50"] = float(np.nanmax([x["share_underwater_50"] for x in eps])) \
                if any(np.isfinite(x["share_underwater_50"]) for x in eps) else NAN
    base["twins_note"] = "twin quantiles over per-fill twin means (spread understated)"
    base["f3_note"] = "no F3 version: the engine computes the 365-day and lowest-price fields on F1 fills only"
    return base, eps


# ============================================================================ D12 recovery curve
REC_LABELS = ("15m", "1h", "4h", "24h", "72h", "7d", "30d")


def d12(res: dict) -> pd.DataFrame:
    """D12 (§10.4, reported before H1's table): for fills and twins, the share trading at or above R1/2 and at or
    above P0 within 15 min .. 30 d, and the share first trading a further 10% below L; split by rung, market-wide
    against coin-specific, fast against slow; on F1 and F3 (s = 1%)."""
    rows = []
    for rule in ("F1", "F3_1"):
        d = per_bench(res, rule, "rec_R_15m") if res is not None else pd.DataFrame()
        if not len(d):
            continue
        splits = [("all", np.ones(len(d), bool))]
        mk = event_drop_masks(d["time"])                     # §10.4 single events
        splits += [(f"all, {EVENT_LABELS[k]}", ~mk[k]) for k in EVENT_NAMES]
        for rg in sorted(pd.unique(d["rung"])):
            splits.append((f"rung {rg:g}", d["rung"].to_numpy() == rg))
        if "mw" in d:
            mw = pd.to_numeric(d["mw"], errors="coerce").to_numpy(float)
            splits += [("market-wide", mw == 1), ("coin-specific", mw == 0)]
        if "s24" in d:
            s = pd.to_numeric(d["s24"], errors="coerce").to_numpy(float)
            splits += [("fast (s24 >= 0.75)", s >= FAST), ("slow (s24 < 0.5)", s < SLOW)]
        for name, m in splits:
            g = d[m]
            for who, pre in (("fills", "rec_"), ("twins", "twin_rec_")):
                row = dict(rule=rule, label=rule_label(rule), split=name, who=who, n=int(len(g)))
                for lv in ("R", "P0", "dn10"):
                    for h in REC_LABELS:
                        c = f"{pre}{lv}_{h}"
                        v = pd.to_numeric(g[c], errors="coerce").to_numpy(float) if c in g else np.full(len(g), NAN)
                        row[f"{lv}_{h}"] = float(np.nanmean(v)) if np.isfinite(v).any() else NAN
                c = f"{pre}dn10_first"
                v = pd.to_numeric(g[c], errors="coerce").to_numpy(float) if c in g else np.full(len(g), NAN)
                row["dn10_first"] = float(np.nanmean(v)) if np.isfinite(v).any() else NAN
                rows.append(row)
    return pd.DataFrame(rows)


# ============================================================================ D6 break-even and waits
def km_waits(bids: pd.DataFrame, fill_col: str = "t_F1", end_min: int | None = None) -> pd.DataFrame:
    """Waits to a first fill under weekly re-placement (coding choice 8): one row per bid (start), with the wait in
    days and the event flag. A chain of a (coin, rung) continues while each bid is placed when the previous life
    ended; the first fill at or after the start ends the wait; a break censors at the chain's last life end."""
    rows = []
    if bids is None or not len(bids):
        return pd.DataFrame(columns=["coin", "rung", "t0", "wait_d", "event"])
    for (c, rg), g in bids.groupby(["coin", "rung"], sort=False):
        g = g.sort_values("t0")
        t0 = g["t0"].to_numpy(np.int64)
        le = g["life_end"].to_numpy(np.int64)
        fm = g[fill_col].to_numpy(np.int64) if fill_col in g else np.full(len(g), -1)
        n = len(g)
        nxt_fill = np.full(n, -1, np.int64)
        chain_end = le.copy()
        for i in range(n - 1, -1, -1):
            cont = i + 1 < n and t0[i + 1] == le[i]
            if fm[i] >= 0:
                nxt_fill[i] = fm[i]
            elif cont:
                nxt_fill[i] = nxt_fill[i + 1]
            chain_end[i] = chain_end[i + 1] if cont else le[i]
        ev = nxt_fill >= 0
        wait = np.where(ev, nxt_fill - t0, chain_end - t0) / DAY_M
        rows.append(pd.DataFrame({"coin": c, "rung": rg, "t0": t0, "wait_d": wait, "event": ev}))
    return pd.concat(rows, ignore_index=True)


def worst_day(bids: pd.DataFrame, fill_col: str = "t_F1") -> dict:
    """§11 sentence 2: the largest share of the live bids that filled on one UTC day, with the day and the counts.
    A bid is live on day d when its life overlaps d and it had not filled before d's start (a bid that filled earlier
    in its week no longer rests); each (coin, rung, variant) order slot counts once per day (on a Monday the outgoing
    and the incoming bid of a slot are one live order), and a slot filled on d when one of its bids filled on d."""
    if bids is None or not len(bids) or fill_col not in bids:
        return dict(share=NAN, day=None, filled=0, live=0)
    a = bids["live_from"].to_numpy(np.int64) // DAY_M
    e = (bids["life_end"].to_numpy(np.int64) - 1) // DAY_M
    fm = bids[fill_col].to_numpy(np.int64)
    fd = np.where(fm >= 0, fm // DAY_M, -1)
    keys = [c for c in ("coin", "rung", "variant") if c in bids]
    slot = bids.groupby(keys, sort=False, dropna=False).ngroup().to_numpy() if keys else np.arange(len(bids))
    days = np.unique(fd[fd >= 0])
    best = dict(share=NAN, day=None, filled=0, live=0)
    for dd in days:
        resting = (a <= dd) & (e >= dd) & ((fm < 0) | (fm >= dd * DAY_M))
        live = int(len(np.unique(slot[resting])))
        filled = int(len(np.unique(slot[fd == dd])))
        if live and (not np.isfinite(best["share"]) or filled / live > best["share"]):
            best = dict(share=filled / live, day=str(ts_min([dd * DAY_M])[0].date()), filled=filled, live=live)
    return best


CL_COLS = ["mb", "ep", "qb", "hf", "wk", "mo", "qu", "yr", "day"]


def d6(res: dict, tbill_at=None, B: int = B_DEFAULT) -> pd.DataFrame:
    """D6 break-even per rung k (§10.4): W_k, F_k, theta_k, mu*_k = F_k theta_k / W_k on F1 (theta at C-0) and on
    F3 (s = 1%; theta on the route's own spread, when the run has a TH72 exit on F3_1: stinkbid_run's full plan),
    B-MKT per placement labelled "the sample's drift" (F1 rows), and every estimate without 2025-10-10, without
    2021-05-19 and without the rung's top month-block (those fills treated as not having happened; coding choice
    8)."""
    bids = bid_fill_table(res, ("F1", "F3_1"))
    rows = []
    if not len(bids):
        return pd.DataFrame()
    for rule, cost in (("F1", "C-0"), ("F3_1", "RH")):
        tcol = "t_" + rule
        if rule != "F1" and not (bids[tcol] >= 0).any():
            continue
        W = km_waits(bids, tcol)
        th = per_fill(res, rule, "TH72", cost, "delta")
        for rg in sorted(pd.unique(bids["rung"])):
            br = bids[bids["rung"] == rg]
            w = W[W["rung"] == rg]
            ws = sbs.waiting_summary(w["wait_d"].to_numpy(float), w["event"].to_numpy(bool), 365.0)
            tk = th[th["rung"] == rg] if len(th) else th
            tk = add_clusters(tk.drop(columns=CL_COLS, errors="ignore")) if len(tk) else tk
            trow = mean_row(tk, "y", "mb", "month-block", B=B, events=False) if len(tk) else \
                stat_row([], [], "month-block")
            ms = sbs.mu_star(ws["F"], trow["estimate"], ws["W"], (trow["ci_lo"], trow["ci_hi"]))
            row = dict(rule=rule, label=rule_label(rule) or "Binance spot", rung=float(rg), starts=ws["n"],
                       events=ws["events"], W=ws["W"], W_se=ws["W_se"], F=ws["F"], p_no_fill=ws["p_no_fill"],
                       median_wait_d=ws["median"], theta=trow["estimate"], theta_lo=trow["ci_lo"],
                       theta_hi=trow["ci_hi"], theta_n=trow["n"], theta_G=trow["G"], theta_gstar=trow["gstar"],
                       theta_unit=trow["unit"], mu_star=_f(ms["mu_star"]),
                       mu_star_lo=_f(ms["ci"][0]) if ms["ci"] else NAN,
                       mu_star_hi=_f(ms["ci"][1]) if ms["ci"] else NAN)
            if not len(tk):
                row["theta_note"] = f"no TH72 outcome on {rule} in this run: theta_k and mu*_k not computed"
            # §10.4 single events: the rung's fills on the day (or in its top month-block) treated as not happened
            ft = br[tcol].to_numpy(np.int64)
            filled = np.flatnonzero(ft >= 0)
            if len(filled):
                tref = ts_min(ft[filled])
                mf = event_drop_masks(tref)
                mt = event_drop_masks(tref, tk["time"]) if len(tk) else {}
                for k in EVENT_NAMES:
                    ft2 = ft.copy()
                    ft2[filled[mf[k]]] = -1
                    w2 = km_waits(br.assign(**{tcol: ft2}), tcol)
                    ws2 = sbs.waiting_summary(w2["wait_d"].to_numpy(float), w2["event"].to_numpy(bool), 365.0)
                    yk = tk["y"].to_numpy(float)[~mt[k]] if len(tk) else np.zeros(0)
                    th2 = float(np.mean(yk)) if len(yk) else NAN
                    row.update({f"W_{k}": ws2["W"], f"F_{k}": ws2["F"], f"theta_{k}": th2,
                                f"mu_star_{k}": ws2["F"] * th2 / ws2["W"] if ws2["W"] > 0 else NAN})
            if rule != "F1":
                row["bmkt_note"] = "B-MKT is per placement on Binance spot: see the F1 rows"
                rows.append(row)
                continue
            # B-MKT per placement ("the sample's drift"; S12: by placement month, 12-month stationary blocks)
            b = br
            if "mkt_r365" in b and "r365_complete" in b:
                b = b[b["r365_complete"].astype(bool)]
                mkt = pd.to_numeric(b["mkt_r365"], errors="coerce").to_numpy(float)
                bid = pd.to_numeric(b.get("bid_r365"), errors="coerce").to_numpy(float)
                filled = b["t_F1"].to_numpy() >= 0
                tb = (tbill_at(b["t0"].to_numpy(np.int64)) if tbill_at is not None else np.zeros(len(b)))
                v = np.where(filled, bid, tb) - mkt
                ok = np.isfinite(v)
                if ok.any():
                    mo = sbs.month_key(ts_min(b["t0"].to_numpy(np.int64)[ok]))
                    s = pd.Series(v[ok]).groupby(mo).mean().sort_index()
                    bt = sbs.stationary_bootstrap(s.to_numpy(), stat="mean", mean_block=D6_BLOCK, B=B)
                    row.update(bmkt_diff=bt["estimate"], bmkt_lo=bt["ci"][0], bmkt_hi=bt["ci"][1],
                               bmkt_months=bt["T"], bmkt_label="the sample's drift")
            rows.append(row)
    return pd.DataFrame(rows)


# ============================================================================ D7 accounts
D7_PAIRS = {"D7": ("B-MIX", "B-TBILL", "B-DCA", "B-ALERT", "B-ML", "B-HOLD"),
            "D7-OWN": ("B-MIX-OWN", "B-TBILL-OWN", "B-DCA-OWN", "B-ALERT-DCA", "B-ML-DCA", "B-HOLD-OWN"),
            "D7-OWN-ML": ("B-MIX-OWN", "B-TBILL-OWN", "B-DCA-OWN", "B-ALERT-DCA", "B-ML-DCA", "B-HOLD-OWN")}


LABEL_NO_XML = "X-ML not computed on this route (the engine computes X-ML exits on F1 only)"


def xml_available(res: dict, route: str) -> bool:
    """Whether the run has X-ML exits (finite xml_px) on the route's bench rows: D7-OWN-ML sells at X-ML, so without
    them it would silently equal D7-OWN."""
    Bn = res.get("bench") if res is not None else None
    if Bn is None or not len(Bn) or "xml_px" not in Bn or "rule" not in Bn:
        return False
    return bool(np.isfinite(pd.to_numeric(Bn.loc[Bn["rule"] == route, "xml_px"], errors="coerce")).any())


def d7(res: dict, data=None, B: int = B_DEFAULT, routes=("F1", "F3_1"), r_res=R_RES) -> dict:
    """D7 accounts (§10.4; coding choice 9): stinkbid_engine.accounts per route and r_res; summaries; the CAGR
    difference against each benchmark (B-MIX first) with stationary block bootstraps (6 and 12 months). On a route
    without X-ML exits (F3: the engine computes them on F1 only) the D7-OWN-ML row is reported as not computed, with
    no comparison (it would repeat D7-OWN)."""
    from analysis_2026 import stinkbid_engine as sbe
    summ, comp, monthly = [], [], {}
    for route in routes:
        xml_ok = xml_available(res, route)
        for rr in r_res:
            try:
                A = sbe.accounts(res, data=data, route=route, r_res=rr)
            except Exception as e:
                summ.append(dict(route=route, r_res=rr, account="(error)", error=repr(e)))
                continue
            S = A["summary"].copy()
            S["account"] = S.index
            S["route"] = route
            S["r_res"] = rr
            S["note"] = ""
            if not xml_ok and "D7-OWN-ML" in S.index:
                S = S.astype({c: object for c in S.columns if c not in ("account", "route", "r_res", "note")})
                S.loc["D7-OWN-ML", [c for c in S.columns if c not in ("account", "route", "r_res", "note")]] = NAN
                S.loc["D7-OWN-ML", "note"] = LABEL_NO_XML
            summ.append(S.reset_index(drop=True))
            M = A["monthly"]
            if not xml_ok and "D7-OWN-ML" in M:
                M = M.drop(columns=["D7-OWN-ML"])
            monthly[(route, rr)] = M
            for acc, bens in D7_PAIRS.items():
                if acc not in M:
                    continue
                if acc == "D7-OWN-ML" and not xml_ok:
                    comp.append(dict(route=route, r_res=rr, account=acc, benchmark="(none)", label=LABEL_NO_XML))
                    continue
                for ben in bens:
                    if ben not in M:
                        continue
                    row = dict(route=route, r_res=rr, account=acc, benchmark=ben)
                    for blk in D7_BLOCKS:
                        bt = sbs.stationary_bootstrap(M[acc].to_numpy(float), M[ben].to_numpy(float), stat="cagr",
                                                      mean_block=blk, B=B)
                        row.update({f"cagr_diff": bt["estimate"], f"lo_{int(blk)}m": bt["ci"][0],
                                    f"hi_{int(blk)}m": bt["ci"][1], "months": bt["T"]})
                    if ben.startswith("B-MIX"):
                        row["label"] = "" if (np.isfinite(_f(row.get("lo_6m"))) and row["lo_6m"] > 0) \
                            else LABEL_EXTRA_STEPS
                    comp.append(row)
    S = pd.concat([s if isinstance(s, pd.DataFrame) else pd.DataFrame([s]) for s in summ], ignore_index=True) \
        if summ else pd.DataFrame()
    return dict(summary=S, compare=pd.DataFrame(comp), monthly=monthly)


def d7_robinhood(d7res: dict) -> dict:
    """§11 "You could run it on Robinhood", account part: the D7 flip account on F3 (r_res = 0) against B-MIX, with
    the 12-month block-bootstrap 95% interval above zero."""
    c = d7res.get("compare")
    if c is None or not len(c):
        return dict(ok=False, why="no D7 comparison")
    r = c[(c["route"] == "F3_1") & (c["r_res"] == 0.0) & (c["account"] == "D7") & (c["benchmark"] == "B-MIX")]
    if not len(r):
        return dict(ok=False, why="no D7 F3 against B-MIX row")
    r = r.iloc[0]
    ok = bool(np.isfinite(_f(r["lo_12m"])) and r["lo_12m"] > 0)
    return dict(ok=ok, cagr_diff=_f(r["cagr_diff"]), lo_12m=_f(r["lo_12m"]), hi_12m=_f(r["hi_12m"]),
                why="12-month block-bootstrap 95% interval above zero" if ok else "interval not above zero")


# ============================================================================ D-ML, D8
def ml_split(fills: pd.DataFrame) -> dict:
    """The F1 fills split by the coin's replicated MoneyLine state at placement (ml_d0: 1 green, 0 red, -1
    undefined), with the red share of the fills whose state is defined (§11 sentence 3, D-ML)."""
    f = fills[fills["t_F1"].to_numpy() >= 0] if "t_F1" in fills else fills.iloc[:0]
    st = f["ml_d0"].to_numpy() if "ml_d0" in f else np.full(len(f), -1)
    n_def = int(np.isin(st, (0, 1)).sum())
    return dict(n=int(len(f)), green=int((st == 1).sum()), red=int((st == 0).sum()), undefined=int((st == -1).sum()),
                red_share_of_defined=float((st == 0).sum() / n_def) if n_def else NAN)


def dml(res: dict, res_g: dict | None = None, B: int = B_DEFAULT) -> pd.DataFrame:
    """D-ML (§10.4): B-ML's coin-count advantage by rung and by MoneyLine state at placement ("no re-entry" share),
    the fill split by state, the share of fills followed by a red close within 1 and 7 days, X-ML's return, and P1-G's
    Delta (the green-only program)."""
    rows = []
    F = res.get("fills") if res is not None else None
    if F is not None and len(F) and "t_F1" in F:
        st = ml_split(F)
        rows.append(dict(table="fill split by state at placement", split="all", **st))
    allf = per_bench(res, "F1", "alert_M") if res is not None else pd.DataFrame()
    for c in ("red_close_1d", "red_close_7d"):
        if len(allf) and c in allf:
            v = pd.to_numeric(allf[c], errors="coerce").to_numpy(float)
            rows.append(dict(table="red close after the fill", split=c, n=int(np.isfinite(v).sum()),
                             share=float(np.nanmean(v)) if np.isfinite(v).any() else NAN))
    bm = per_bench(res, "F1", "ml_a") if res is not None else pd.DataFrame()
    nb = per_bench(res, "F1", "knife") if res is not None else pd.DataFrame()     # fills with 365 days observed
    if len(nb) and "ml_a" in nb:
        no_re = ~np.isfinite(pd.to_numeric(nb["ml_a"], errors="coerce").to_numpy(float))
        rows.append(dict(table="B-ML", split="no re-entry within 365 days (fills with 365 days observed)",
                         n=int(len(nb)), share=float(no_re.mean())))
    if len(bm):
        r = mean_row(bm, B=B)
        rows.append(dict(table="B-ML", split="all", **r))
        for rg in sorted(pd.unique(bm["rung"])):
            g = add_clusters(bm[bm["rung"] == rg].drop(columns=["mb", "ep", "qb", "hf", "wk", "mo", "qu", "yr",
                                                                 "day"]))
            rows.append(dict(table="B-ML", split=f"rung {rg:g}", **mean_row(g, B=B)))
        if "ml_d0" in bm:
            for stv, nm in ((1, "green at placement"), (0, "red at placement"), (-1, "undefined at placement")):
                g = bm[bm["ml_d0"].to_numpy() == stv]
                if len(g):
                    g = add_clusters(g.drop(columns=["mb", "ep", "qb", "hf", "wk", "mo", "qu", "yr", "day"]))
                    rows.append(dict(table="B-ML", split=nm, **mean_row(g, B=B)))
    b3 = per_bench(res, "F3_1", "ml_a") if res is not None else pd.DataFrame()
    if len(b3):
        rows.append(dict(table="B-ML", split="all, F3 (s = 1%)", label=LABEL_RH, **mean_row(b3, B=B)))
    xm = per_bench(res, "F1", "xml_r_C-RH") if res is not None else pd.DataFrame()
    if len(xm):
        rows.append(dict(table="X-ML (hold until the first red close after a green one), C-RH", split="all",
                         **mean_row(xm, B=B)))
    if res_g is not None:
        g = per_fill(res_g, "F1", "FLIP", "C-RH", "delta")
        rows.append(dict(table="P1-G (bids only when green at d0): Delta, X-FLIP, C-RH", split="all",
                         **mean_row(g, B=B)))
    return pd.DataFrame(rows)


def d8(res: dict, tbill_at=None, B: int = B_DEFAULT) -> dict:
    """D8 flip vs own (§10.4, R15; coding choice 10): the shared premium (H2R's a_f at 72 h) and the hold-period
    return after 72 h against T-bills."""
    p1 = per_bench(res, "F1", "alert_72h")
    part1 = mean_row(p1, B=B)
    part2 = _after72(res, "F1", "C-0", tbill_at, B)
    p3 = per_bench(res, "F3_1", "alert_72h")
    part2_f3 = _after72(res, "F3_1", "RH", tbill_at, B)
    out = dict(premium_72h=part1, premium_72h_F3=dict(mean_row(p3, B=B), label=LABEL_RH),
               after_72h_vs_tbill=part2, after_72h_vs_tbill_F3=dict(part2_f3, label=LABEL_RH))
    if not part2_f3.get("n"):
        out["note"] = "part 2 on F3 needs the TH72 and HOLD90 exits on the F3 rows (stinkbid_run's full plan)"
    return out


def _after72(res: dict, rule: str, cost: str, tbill_at=None, B: int = B_DEFAULT) -> dict:
    """D8 part 2 on one route: the X-HOLD-90 exit price over the TH72 price, minus the T-bill yield at the fill pro
    rata over the days between, quarter-block clusters (coding choice 10). On F3 both exits are market sells at the
    index less the route's spread, so the spread cancels in the ratio."""
    h90 = per_fill(res, rule, "HOLD90", cost, "r")
    t72 = per_fill(res, rule, "TH72", cost, "r")
    part2 = stat_row([], [], "quarter-block")
    if len(h90) and len(t72):
        m = h90[["fill_id", "exit_px", "exit_t", "time", "t_fill"]].merge(
            t72[["fill_id", "exit_px", "exit_t"]].rename(columns={"exit_px": "px72", "exit_t": "t72"}), on="fill_id")
        m = m[(m["exit_px"] > 0) & (m["px72"] > 0)]
        if len(m):
            days = (m["exit_t"].to_numpy(np.int64) - m["t72"].to_numpy(np.int64)) / DAY_M
            tb = tbill_at(m["t_fill"].to_numpy(np.int64)) if tbill_at is not None else np.zeros(len(m))
            m = m.assign(y=m["exit_px"] / m["px72"] - 1 - tb * days / 365.0)
            m = add_clusters(m.drop(columns=CL_COLS, errors="ignore"))
            part2 = mean_row(m, "y", "qb", "quarter-block", B=B)
    return part2


# ============================================================================ D1-D5
def _speed_class(s):
    s = np.asarray(s, float)
    return np.where(s >= FAST, "fast", np.where(s < SLOW, "slow", np.where(np.isfinite(s), "middle", "n/a")))


def d1(res_by_univ: dict) -> pd.DataFrame:
    """D1 wick frequency and clustering: per universe, rung and year, the fill rate per bid (F1), the share on
    market-wide days, distinct fill days, episodes, months, the effective number of months (1/sum w^2) and G*, and
    the median depth of filled bids in sigma and in %."""
    rows = []
    for un, res in res_by_univ.items():
        if res is None:
            continue
        b = bid_fill_table(res, ("F1",))
        if not len(b):
            continue
        b["year"] = ts_min(b["t0"].to_numpy(np.int64)).year
        for (rg, yr), g in list(b.groupby(["rung", "year"])) + [((rg, "all"), b[b["rung"] == rg])
                                                                  for rg in sorted(pd.unique(b["rung"]))]:
            fl = g[g["t_F1"] >= 0]
            row = dict(universe=un, rung=float(rg), year=str(yr), bids=int(len(g)), fills=int(len(fl)),
                       fill_rate=float(len(fl) / len(g)) if len(g) else NAN)
            if len(fl):
                t = ts_min(fl["t_F1"].to_numpy(np.int64))
                mo = sbs.month_key(t)
                _, cnt = np.unique(mo, return_counts=True)
                mb, _ = sbs.month_blocks(t)
                row.update(fill_days=int(len(np.unique(sbs.fill_days(t)))), episodes=int(len(np.unique(
                    sbs.episodes(t)[0]))), months=int(len(cnt)), eff_months=sbs.eff_clusters(cnt),
                    gstar_month_blocks=sbs.gstar(np.bincount(mb)),
                    depth_sigma_median=float(np.nanmedian(fl["delta"].to_numpy(float))),
                    depth_pct_median=float(np.nanmedian(1 - fl["L"].to_numpy(float) / fl["P0"].to_numpy(float))))
                F = res["fills"]
                if "mw" in F:
                    mw = F.set_index("bid_id").reindex(fl["bid_id"])["mw"].to_numpy(float)
                    row["mw_share"] = float(np.nanmean(mw)) if np.isfinite(mw).any() else NAN
            rows.append(row)
    return pd.DataFrame(rows)


def d2(res_by_life: dict) -> pd.DataFrame:
    """D2 fill mix by life (1 / 7 / 30 / 90 days): per rung, fills, fill rate and the fast / middle / slow shares."""
    rows = []
    for life, res in res_by_life.items():
        if res is None:
            continue
        b = bid_fill_table(res, ("F1",))
        F = res.get("fills")
        if not len(b):
            continue
        for rg in sorted(pd.unique(b["rung"])):
            g = b[b["rung"] == rg]
            fl = F[(F["rung"] == rg) & (F["t_F1"] >= 0)] if F is not None and len(F) else pd.DataFrame()
            cls = _speed_class(fl["s24"].to_numpy(float)) if len(fl) and "s24" in fl else np.array([])
            n = len(cls)
            rows.append(dict(life=life, rung=float(rg), bids=int(len(g)), fills=int(n),
                             fill_rate=float(n / len(g)) if len(g) else NAN,
                             fast=float((cls == "fast").mean()) if n else NAN,
                             middle=float((cls == "middle").mean()) if n else NAN,
                             slow=float((cls == "slow").mean()) if n else NAN))
    return pd.DataFrame(rows)


VENUE_RULES = ("F2", "F3_1", "F3_2", "F3_3", "F3_5", "F3d_1", "F3d_2", "F3d_3", "F3d_5", "F4", "F5")


def d3(res: dict, top_events: int = 10) -> pd.DataFrame:
    """D3 venue gap: for the F1 fills, the share each other rule also fills (and F3-unverifiable: no index minute),
    by rung, Robinhood-listed coins (U-C, hindsight) and event (the largest episodes); F6 is not built."""
    F = res.get("fills") if res is not None else None
    if F is None or not len(F) or "t_F1" not in F:
        return pd.DataFrame()
    f = F[F["t_F1"] >= 0].copy()
    f = add_clusters(f.assign(time=ts_min(f["t_F1"].to_numpy(np.int64))))
    _, etab = sbs.episodes(f["time"])
    big = etab.sort_values(["n_fills", "episode"], ascending=[False, True]).head(top_events)
    splits = [("all", np.ones(len(f), bool))]
    splits += [(f"rung {rg:g}", f["rung"].to_numpy() == rg) for rg in sorted(pd.unique(f["rung"]))]
    if "in_U_C" in f:
        splits += [("U-C coins (hindsight)", f["in_U_C"].astype(bool).to_numpy()),
                   ("other coins", ~f["in_U_C"].astype(bool).to_numpy())]
    for r in big.itertuples():
        splits.append((f"episode {str(r.start)[:10]} ({r.n_fills} fills)", f["ep"].to_numpy() == r.episode))
    rows = []
    for name, m in splits:
        g = f[m]
        row = dict(split=name, f1_fills=int(len(g)))
        for r in VENUE_RULES:
            c = "t_" + r
            row[f"also_{r}"] = float((g[c] >= 0).mean()) if c in g and len(g) else NAN
        if "idx_missing" in g:
            row["f3_unverifiable"] = float(g["idx_missing"].astype(bool).mean()) if len(g) else NAN
        row["also_F6"] = NAN
        row["F6_note"] = LABEL_NOT_BUILT
        row["F5_note"] = LABEL_F5
        rows.append(row)
    # fills under another rule without an F1 fill (e.g. index-only dips)
    for r in VENUE_RULES:
        c = "t_" + r
        if c in F:
            rows.append(dict(split=f"{r} fills without an F1 fill", f1_fills=0,
                             **{f"only_{r}": int(((F[c] >= 0) & (F["t_F1"] < 0)).sum())}))
    return pd.DataFrame(rows)


def _num(f: pd.DataFrame, col: str) -> np.ndarray:
    """A numeric column as floats (NaN where missing or not numeric; all NaN when the column is absent)."""
    return pd.to_numeric(f[col], errors="coerce").to_numpy(float) if col in f else np.full(len(f), NAN)


def fill_capacity(f: pd.DataFrame) -> np.ndarray:
    """C(L) of F1 fills over the order's life: aggTrades where streamed (cap_src 'agg'), else C1."""
    src = f["cap_src"].astype(str).to_numpy() if "cap_src" in f else np.full(len(f), "c1")
    return np.where(src == "agg", _num(f, "agg_life"), _num(f, "c1_life"))


def d4(res: dict) -> pd.DataFrame:
    """D4 capacity ("Binance spot book"; context only on the market-maker route): per rung and coin group, the mean
    share of Q filled and the share of orders filled in full at Q = $1k / $10k / $100k, theta = 1 / 0.25, and the
    distribution of C(L) (aggTrades where streamed, else C1)."""
    F = res.get("fills") if res is not None else None
    if F is None or not len(F) or "t_F1" not in F:
        return pd.DataFrame()
    f = F[F["t_F1"] >= 0]
    cap = fill_capacity(f)
    rows = []
    groups = [("all", np.ones(len(f), bool))]
    if "in_U_C" in f:
        groups += [("U-C coins (hindsight)", f["in_U_C"].astype(bool).to_numpy())]
    for rg in sorted(pd.unique(f["rung"])):
        for gname, gm in groups:
            m = (f["rung"].to_numpy() == rg) & gm
            g = f[m]
            c = cap[m]
            row = dict(rung=float(rg), group=gname, fills=int(m.sum()), label="Binance spot book")
            for q, _ in Q_SIZES:
                for th in THETAS:
                    col = f"share_{q}_{th:g}"
                    v = pd.to_numeric(g.get(col), errors="coerce").to_numpy(float) if col in g else np.array([])
                    row[f"mean_{col}"] = float(np.nanmean(v)) if np.isfinite(v).any() else NAN
                    row[f"full_{col}"] = float(np.nanmean(v >= 1)) if np.isfinite(v).any() else NAN
            cc = c[np.isfinite(c)]
            for p in (0.10, 0.25, 0.50, 0.75, 0.90):
                row[f"C_p{int(p * 100)}"] = float(np.quantile(cc, p)) if len(cc) else NAN
            row["Q_max"] = 0.25 * row["C_p10"] if np.isfinite(row["C_p10"]) else NAN
            rows.append(row)
    return pd.DataFrame(rows)


def capacity_cap(res: dict) -> pd.DataFrame:
    """The size cap of §11 sentence 4 / §13 column 5: per rung, the median and 10th percentile of past seller dollars
    below the level and Q_max = 0.25 x the 10th percentile."""
    t = d4(res)
    if not len(t):
        return t
    t = t[t["group"] == "all"]
    return t[["rung", "fills", "C_p50", "C_p10", "Q_max"]].reset_index(drop=True)


def d5(res_p1: dict, res_m3: dict | None, B: int = B_DEFAULT) -> pd.DataFrame:
    """D5 fill-odds calibration (§10.4; coding choice 11): M3's target p against realized and the sheet's shrunken
    walk-forward estimate against realized, per half, episode-bootstrap 90% intervals; calibrated if both halves'
    intervals overlap [0.67, 1.5]."""
    rows = []

    def one(label, realized, predicted, t0, fill_t, half):
        cl = bid_clusters(t0, fill_t)
        r = sbs.d5_calibration(realized, predicted, cl, half, B=B, level=D5_LEVEL)
        row = dict(estimand=label, n_bids=int(len(realized)), realized=float(np.sum(realized)),
                   predicted=float(np.sum(predicted)), calibrated=bool(r.get("calibrated", False)))
        for h in ("0", "1"):
            hh = r.get(h, {})
            row[f"half{h}_ratio"] = _f(hh.get("ratio"))
            ci = hh.get("ci", (NAN, NAN))
            row[f"half{h}_lo"], row[f"half{h}_hi"] = _f(ci[0]), _f(ci[1])
            row[f"half{h}_G"] = int(hh.get("G", 0) or 0)
        rows.append(row)
    if res_m3 is not None:
        for rule in ("F1", "F3_1"):
            b = bid_fill_table(res_m3, (rule,))
            if len(b) and "params" in b:
                p = b["rung"].to_numpy(float)                          # M3's rung is its p
                for pv in sorted(pd.unique(p)):
                    m = p == pv
                    g = b[m]
                    ft = g["t_" + rule].to_numpy(np.int64)
                    one(f"M3 p={pv:g} ({rule})", (ft >= 0).astype(float), np.full(int(m.sum()), pv),
                        g["t0"].to_numpy(np.int64), np.where(ft >= 0, ft, -1),
                        sbs.half_key(ts_min(g["t0"].to_numpy(np.int64))))
    for rule in ("F1", "F3_1"):
        b = bid_fill_table(res_p1, (rule,))
        if not len(b):
            continue
        b = b.assign(year=ts_min(b["t0"].to_numpy(np.int64)).year, filled=(b["t_" + rule] >= 0).astype(float))
        pred = np.full(len(b), NAN)
        for rg in sorted(pd.unique(b["rung"])):
            br = b[b["rung"] == rg]
            for yr in sorted(pd.unique(br["year"])):
                prev = br[br["year"] < yr]
                cur = br["year"] == yr
                p_pool = prev["filled"].mean() if len(prev) else NAN
                if not np.isfinite(p_pool):
                    continue
                cnt = prev.groupby("coin")["filled"].agg(["sum", "count"])
                idx = br.index[cur]
                cc = b.loc[idx, "coin"]
                nf = cc.map(cnt["sum"]).fillna(0.0).to_numpy(float)
                nb = cc.map(cnt["count"]).fillna(0.0).to_numpy(float)
                pred[b.index.get_indexer(idx)] = (nf + 52 * p_pool) / (nb + 52)
        ok = np.isfinite(pred)
        if ok.any():
            g = b[ok]
            ft = g["t_" + rule].to_numpy(np.int64)
            one(f"sheet walk-forward ({rule})", g["filled"].to_numpy(float), pred[ok], g["t0"].to_numpy(np.int64),
                np.where(ft >= 0, ft, -1), sbs.half_key(ts_min(g["t0"].to_numpy(np.int64))))
    return pd.DataFrame(rows)


def sheet_stats(res: dict) -> pd.DataFrame:
    """Per coin and rung of P1 on U-Q1 (and pooled per rung, coin = "ALL"), the counts the level sheet (§13) shows:
    bids, F1 and F3 (s = 1%) fills and their episodes, the weekly fill rate and its shrunken estimate
    (n_fill + 52 p_pool) / (n_bids + 52) with p_pool the U-Q1 rate at the rung, a Wilson 95% interval widened by
    sqrt(phi) (phi = the Pearson dispersion of the rung's yearly fill counts, S14), the Kaplan-Meier median wait and
    the chance of no fill within a year under weekly re-placement (each on its own rule: §7 "The sheet's numbers
    come from F3", the F1 row labelled "upper bound"), and the capacity quantiles with Q_max = 0.25 x the 10th
    percentile (the Binance spot book of the F1 fills; context only on the market-maker route). Counts and capacity
    only (no post-fill outcome)."""
    b = bid_fill_table(res, ("F1", "F3_1"))
    F = res.get("fills")
    if not len(b):
        return pd.DataFrame()
    b = b.assign(year=ts_min(b["t0"].to_numpy(np.int64)).year)
    W = {r: km_waits(b, "t_" + r) for r in ("F1", "F3_1")}
    cap = pd.DataFrame()
    if F is not None and len(F) and "t_F1" in F:
        f = F[F["t_F1"] >= 0]
        cv = fill_capacity(f)
        cap = pd.DataFrame({"coin": f["coin"].astype(str).to_numpy(), "rung": f["rung"].to_numpy(float), "C": cv})
    rows = []
    for rg in sorted(pd.unique(b["rung"])):
        br = b[b["rung"] == rg]
        for rule in ("F1", "F3_1"):
            yc = br.groupby("year").apply(lambda g: pd.Series({"x": float((g["t_" + rule] >= 0).sum()),
                                                                "n": float(len(g))}), include_groups=False)
            ph = sbs.overdispersion_phi(yc["x"].to_numpy(), yc["n"].to_numpy())["phi"] if len(yc) > 1 else NAN
            p_pool = float((br["t_" + rule] >= 0).mean())
            for coin, g in [("ALL", br)] + list(br.groupby(br["coin"].astype(str))):
                x = int((g["t_" + rule] >= 0).sum())
                n = int(len(g))
                ft = g.loc[g["t_" + rule] >= 0, "t_" + rule].to_numpy(np.int64)
                eps = int(len(np.unique(sbs.episodes(ts_min(ft))[0]))) if len(ft) else 0
                lo, hi, _ = sbs.wilson(x, n, phi=ph if np.isfinite(ph) else 1.0)
                row = dict(coin=coin, rung=float(rg), rule=rule, label=rule_label(rule) or "Binance spot (upper bound)",
                           bids=n, fills=x, episodes=eps, rate=x / n if n else NAN,
                           rate_shrunk=(x + 52 * p_pool) / (n + 52) if coin != "ALL" else p_pool,
                           wilson_lo=lo, wilson_hi=hi, phi=ph, p_pool=p_pool)
                Wr = W[rule]
                w = Wr[(Wr["rung"] == rg) & ((Wr["coin"].astype(str) == coin) if coin != "ALL" else True)]
                if len(w):
                    ws = sbs.waiting_summary(w["wait_d"].to_numpy(float), w["event"].to_numpy(bool), 365.0)
                    row.update(median_wait_weeks=ws["median"] / 7 if np.isfinite(ws["median"]) else NAN,
                               p_no_fill_year=ws["p_no_fill"], km_starts=ws["n"])
                c = cap[(cap["rung"] == rg) & ((cap["coin"] == coin) if coin != "ALL" else True)]["C"] \
                    if len(cap) else pd.Series(dtype=float)
                c = c[np.isfinite(c)]
                row.update(C_p50=float(np.median(c)) if len(c) else NAN,
                           C_p10=float(np.quantile(c, 0.10)) if len(c) else NAN)
                row["Q_max"] = 0.25 * row["C_p10"] if np.isfinite(row["C_p10"]) else NAN
                row["cap_note"] = "Binance spot book" + ("" if rule == "F1" else "; context only on the market-maker "
                                                                                   "route")
                rows.append(row)
    return pd.DataFrame(rows)


# ============================================================================ D9, D10 (the sheet's fill-odds family)
def _logit(x, y, iters: int = 60):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(y) == 0 or y.sum() == 0 or y.sum() == len(y):
        p = float(y.mean()) if len(y) else NAN
        return None, p
    X = np.column_stack([np.ones(len(x)), x])
    b = np.array([math.log(y.mean() / (1 - y.mean())), 0.0])
    for _ in range(iters):
        z = np.clip(X @ b, -30, 30)
        p = 1 / (1 + np.exp(-z))
        Wt = p * (1 - p)
        H = X.T @ (X * Wt[:, None]) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, X.T @ (y - p))
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b, None


def _logit_predict(b, const, x):
    x = np.asarray(x, float)
    if b is None:
        return np.full(len(x), const)
    return 1 / (1 + np.exp(-np.clip(b[0] + b[1] * x, -30, 30)))


def d10(res_h4: dict, rule: str = "F1", B: int = B_DEFAULT) -> pd.DataFrame:
    """D10 (§10.4; coding choice 12): per H4 method, real bids' fills against a logit on delta fitted to the method's
    four placebos; statistic = mean(fill - expected) over real bids, one-sided p (test_mean, bid-week clusters)."""
    from analysis_2026 import stinkbid_engine as sbe
    b = bid_fill_table(res_h4, (rule,))
    rows = []
    if not len(b):
        return pd.DataFrame()
    names = sbe.H4_NAMES
    for var, g in b.groupby("variant"):
        m = names.get(var)
        if m is None:
            continue
        pl = g[~g["real"].astype(bool)]
        rl = g[g["real"].astype(bool)]
        fpl = (pl["t_" + rule] >= 0).astype(float).to_numpy()
        coef, const = _logit(pl["delta"].to_numpy(float), fpl)
        exp_ = _logit_predict(coef, const, rl["delta"].to_numpy(float))
        frl = (rl["t_" + rule] >= 0).astype(float).to_numpy()
        e = frl - exp_
        cl = bid_clusters(rl["t0"].to_numpy(np.int64), np.where(frl > 0, rl["t_" + rule], -1))
        ok = np.isfinite(e)
        p, r = p_one(e[ok], cl[ok], B=B) if ok.sum() > 1 else (NAN, {})
        rows.append(dict(test=m, variant=var, rule=rule, real_bids=int(len(rl)), real_fills=int(frl.sum()),
                         expected_fills=float(np.nansum(exp_)), placebo_bids=int(len(pl)),
                         placebo_fills=int(fpl.sum()), estimate=_f(r.get("estimate")), se=_f(r.get("se")),
                         G=int(r.get("G", 0) or 0), gstar=_f(r.get("gstar")), unit="bid-week (episode-linked)",
                         p=p))
    return pd.DataFrame(rows)


def d9(res_h4all: dict, rule: str = "F4", B: int = B_DEFAULT) -> dict:
    """D9 round-number queue test (exchange route, F4; coding choice 12): per coin-week, (fill M5f - fill M5a) of the
    real levels minus the mean of the same difference over the placebo shifts both have; one-sided p."""
    b = bid_fill_table(res_h4all, (rule,))
    if not len(b) or "method" not in b:
        return dict(test="D9", rule=rule, n=0, estimate=NAN, p=NAN)
    b = b[b["method"].isin(["M5f", "M5a"])]
    if not len(b):
        return dict(test="D9", rule=rule, n=0, estimate=NAN, p=NAN)
    b = b.assign(f=(b["t_" + rule] >= 0).astype(float), sh=b["shift"].fillna(0.0).round(6))
    piv = b.pivot_table(index=["cw", "sh"], columns="method", values="f", aggfunc="first")
    t0 = b.groupby("cw")["t0"].first()
    ft = b[b["f"] > 0].groupby("cw")["t_" + rule].min()
    z, cws = [], []
    for cw, g in piv.groupby(level=0):
        g = g.droplevel(0)
        if "M5f" not in g or "M5a" not in g or 0.0 not in g.index:
            continue
        real = g.loc[0.0]
        if not (np.isfinite(real["M5f"]) and np.isfinite(real["M5a"])):
            continue
        pl = g.drop(index=0.0)
        pl = pl[np.isfinite(pl["M5f"]) & np.isfinite(pl["M5a"])]
        if not len(pl):
            continue
        z.append((real["M5f"] - real["M5a"]) - float((pl["M5f"] - pl["M5a"]).mean()))
        cws.append(cw)
    if len(z) < 2:
        return dict(test="D9", rule=rule, n=len(z), estimate=float(np.mean(z)) if z else NAN, p=NAN)
    cl = bid_clusters(t0.reindex(cws).to_numpy(np.int64), ft.reindex(cws).fillna(-1).to_numpy())
    p, r = p_one(np.array(z), cl, B=B)
    return dict(test="D9", rule=rule, n=len(z), estimate=_f(r.get("estimate")), se=_f(r.get("se")),
                G=int(r.get("G", 0) or 0), gstar=_f(r.get("gstar")), unit="bid-week (episode-linked)", p=p)


def d10_family(d10_tab: pd.DataFrame, d9_row: dict) -> pd.DataFrame:
    """D10's own Holm family (§10.4): the four H4 methods plus D9, Holm at 5% (used only for the sheet; a method that
    passes it is labelled "better fill odds at this depth, not a better price")."""
    rows = []
    for m in sbs.H4_METHODS:
        r = d10_tab[d10_tab["test"] == m] if len(d10_tab) else d10_tab
        rows.append(dict(test=m, estimate=_f(r["estimate"].iloc[0]) if len(r) else NAN,
                         p=_f(r["p"].iloc[0]) if len(r) else NAN))
    rows.append(dict(test="D9", estimate=_f(d9_row.get("estimate")), p=_f(d9_row.get("p"))))
    t = pd.DataFrame(rows)
    p = t["p"].to_numpy(float)
    t["p_holm"] = sbs.holm(p)
    lv, rj = sbs.holm_levels(p)
    t["holm_level"], t["rejected"] = lv, rj
    t["label"] = np.where(t["rejected"] & (t["test"] != "D9"), "better fill odds at this depth, not a better price",
                          np.where(t["rejected"], "round-number advice earned (exchange route)", ""))
    return t


def d11(total_obs: float, twin_total: float, calib: dict | None) -> dict:
    """D11 luck (§10.4; coding choice 13): P1's total Delta against K3's null totals; random-time programs only as a
    level."""
    out = dict(total_delta=_f(total_obs), random_time_level=_f(twin_total),
               random_time_note="what buying at random times with this exit earned (a level, no percentile)")
    if calib and calib.get("null", {}).get("H1"):
        out["null"] = sbs.d11_percentile(total_obs, calib)
    else:
        out["null"] = {}
        out["note"] = "K3's null totals not available"
    return out


# ============================================================================ sensitivity rows (§10.4)
def _srow(section, row, stat, d, program, universe, rule, label="", w=None, cl="mb", unit="month-block",
          B=B_DEFAULT, extra=None) -> dict:
    r = mean_row(d, "y", cl, unit, w=w, B=B) if len(d) else stat_row([], [], unit)
    out = dict(section=section, row=row, stat=stat, program=program, universe=universe, rule=rule,
               label=label or rule_label(rule), **r)
    if extra:
        out.update(extra)
    return out


def _h1(res, rule="F1", exit="FLIP", cost=None, value="delta"):
    return per_fill(res, rule, exit, cost or route_cost(rule), value)


def _h2(res, rule="F1", col="alert_M"):
    return per_bench(res, rule, col)


def bad_print_mask(d: pd.DataFrame) -> np.ndarray:
    """§4.1 sensitivity: True for fills to KEEP (fill minute with >= $1k of seller-initiated notional below L, by
    aggTrades where streamed else C1, and an index low at or below L in that minute where the index exists)."""
    if not len(d):
        return np.zeros(0, bool)
    agg = pd.to_numeric(d.get("agg_m0"), errors="coerce").to_numpy(float) if "agg_m0" in d else np.full(len(d), NAN)
    c1 = pd.to_numeric(d.get("c1_m0"), errors="coerce").to_numpy(float) if "c1_m0" in d else np.full(len(d), NAN)
    v = np.where(np.isfinite(agg), agg, c1)
    keep = ~(np.isfinite(v) & (v < BAD_PRINT_USD))
    if "idx_low_rel" in d:
        il = pd.to_numeric(d["idx_low_rel"], errors="coerce").to_numpy(float)
        keep &= ~(np.isfinite(il) & (il > 1.0))
    return keep


def sensitivity(runs: dict, B: int = B_DEFAULT) -> pd.DataFrame:
    """Every sensitivity row of §10.4 that the runs allow (each changes P1 one way), with H1's and H2R's statistics on
    F1 and on F3 (s = 1%) side by side; rows whose data are not built say so."""
    P = runs.get("P1/U_Q1")
    rows = []

    def pair(section, row, res, program, universe, label="", h1=True, h2=True, extra=None):
        if res is None:
            rows.append(dict(section=section, row=row, stat="H1 delta", program=program, universe=universe,
                             rule="F1", label=label or "not run", n=0))
            return
        f3lab = (label + "; " if label else "") + LABEL_RH
        F = res.get("fills")
        if F is None or "t_F3_1" not in F:                  # F3 not in this run's plan (U-B by default)
            f3lab += "; F3 not computed for this run (coding choice 13 of stinkbid_run)"
        if h1:
            rows.append(_srow(section, row, "H1 delta", _h1(res), program, universe, "F1", label, B=B, extra=extra))
            rows.append(_srow(section, row, "H1 delta", _h1(res, "F3_1"), program, universe, "F3_1", f3lab, B=B,
                              extra=extra))
        if h2:
            rows.append(_srow(section, row, "H2R a_f", _h2(res), program, universe, "F1", label, B=B, extra=extra))
            rows.append(_srow(section, row, "H2R a_f", _h2(res, "F3_1"), program, universe, "F3_1", f3lab, B=B,
                              extra=extra))
    # the primary row first (P1 as tested)
    pair("primary", "P1 (U-Q1, M2 k = 6/8/10, 7-day life, X-FLIP rule M, C-RH)", P, "P1", "U_Q1")
    # lives, refresh and filters
    for key, nm in (("P1-1/U_Q1", "life 1 day (re-placed daily; exploratory)"), ("P1-30/U_Q1", "life 30 days"),
                    ("P1-90/U_Q1", "life 90 days (Robinhood GTC, set and forget)"), ("P1-lazy/U_Q1", "P1-lazy"),
                    ("P1-G/U_Q1", "P1-G (green MoneyLine at d0)"), ("P1-1330/U_Q1", "placement at 13:30 UTC")):
        pair("program", nm, runs.get(key), key.split("/")[0], "U_Q1")
    # rungs k = 5 and 12
    K = runs.get("P1-k5-12/U_Q1")
    for k in (5.0, 12.0):
        if K is None:
            pair("rungs", f"rung k = {k:g}", None, "P1-k5-12", "U_Q1")
            continue
        for stat, rule in (("H1 delta", "F1"), ("H1 delta", "F3_1"), ("H2R a_f", "F1"), ("H2R a_f", "F3_1")):
            d = _h1(K, rule) if stat.startswith("H1") else _h2(K, rule)
            d = d[d["rung"] == k] if len(d) else d
            d = add_clusters(d.drop(columns=["mb", "ep", "qb", "hf", "wk", "mo", "qu", "yr", "day"])) if len(d) else d
            rows.append(_srow("rungs", f"rung k = {k:g}", stat, d, "P1-k5-12", "U_Q1", rule, B=B))
    # other level methods, pooled and by parameter
    for key, nm in (("M1/U_Q1", "M1 fixed %"), ("M2a/U_Q1", "M2a ATR-scaled"), ("M3/U_Q1", "M3 quantile-calibrated")):
        res = runs.get(key)
        pair("levels", f"{nm} (pooled)", res, key.split("/")[0], "U_Q1")
        if res is not None and len(res.get("fills", [])):
            d1_, d3_ = _h1(res), _h1(res, "F3_1")
            vars_ = sorted(set(pd.unique(d1_["variant"])) | set(pd.unique(d3_["variant"]))) \
                if (len(d1_) or len(d3_)) else []
            for var in vars_:
                for rule, d in (("F1", d1_), ("F3_1", d3_)):
                    g = d[d["variant"] == var] if len(d) else d
                    g = add_clusters(g.drop(columns=CL_COLS)) if len(g) else g
                    rows.append(_srow("levels", f"{nm}: {var}", "H1 delta", g, key.split("/")[0], "U_Q1", rule, B=B))
    # fill rules (F2 illusion, F3 crash spreads and dwell, F4, F5 deeper wick, F6 not built)
    for rule in ("F2", "F3_2", "F3_3", "F3_5", "F3d_1", "F3d_2", "F3d_3", "F3d_5", "F4", "F5"):
        if P is None:
            continue
        rows.append(_srow("fill rule", rule, "H1 delta", _h1(P, rule), "P1", "U_Q1", rule, B=B))
        rows.append(_srow("fill rule", rule, "H2R a_f", _h2(P, rule), "P1", "U_Q1", rule, B=B))
    rows.append(dict(section="fill rule", row="F6 (Coinbase 1m)", stat="H1 delta", program="P1", universe="U_Q1",
                     rule="F6", label=LABEL_NOT_BUILT, n=0))
    # exits: the bot latency and the flip grid
    if P is not None:
        exits = sorted(P["outcomes"].loc[P["outcomes"]["rule"] == "F1", "exit"].unique()) if len(P["outcomes"]) else []
        for ex in ["FLIP_bot"] + [e for e in exits if e.startswith("G_")]:
            lab = "bot latency (sell live 1 minute after the fill)" if ex == "FLIP_bot" else ""
            rows.append(_srow("exit", ex, "H1 delta", _h1(P, "F1", ex), "P1", "U_Q1", "F1", lab, B=B,
                              extra=None if ex == "FLIP_bot" else dict(f3_note=F3_NOTE["grid"])))
            if ex == "FLIP_bot":
                rows.append(_srow("exit", ex, "H1 delta", _h1(P, "F3_1", ex), "P1", "U_Q1", "F3_1",
                                  lab + "; " + LABEL_RH, B=B))
        # costs (H1 only, coding choice 14)
        for c in ("C-0", "C-EX", "C-BUS"):
            rows.append(_srow("cost", c, "H1 delta", _h1(P, "F1", "FLIP", c), "P1", "U_Q1", "F1", B=B,
                              extra=dict(f3_note=F3_NOTE["cost"])))
        # capacity and size: fills weighted by filled dollars
        for q, qv in Q_SIZES:
            for th in THETAS:
                if (q, th) not in (("10k", 1.0), ("10k", 0.25), ("1k", 1.0), ("100k", 1.0)):
                    continue
                col = f"share_{q}_{th:g}"
                for stat, d in (("H1 delta", _h1(P)), ("H2R a_f", _h2(P))):
                    w = pd.to_numeric(d.get(col), errors="coerce").to_numpy(float) * qv if col in d else None
                    rows.append(_srow("size", f"weighted by filled dollars at Q = ${q}, theta = {th:g}", stat, d,
                                      "P1", "U_Q1", "F1", "Binance spot book capacity", w=w, B=B,
                                      extra=dict(f3_note=F3_NOTE["size"])))
        # twins: leave-out drift, +-30-day twins, pooled twins
        for v, nm in (("delta_drift", "leave-out drift in place of twins"), ("delta_x30", "+-30-day twins"),
                      ("delta_pool", "pooled twins")):
            rows.append(_srow("benchmark", nm, "H1 delta", _h1(P, "F1", "FLIP", "C-RH", v), "P1", "U_Q1", "F1", B=B,
                              extra=dict(f3_note=F3_NOTE["benchmark"])))
        # cluster variants, on F1 and beside them on F3 (s = 1%)
        for rule in ("F1", "F3_1"):
            lab = rule_label(rule)
            for stat, d in (("H1 delta", _h1(P, rule)), ("H2R a_f", _h2(P, rule))):
                rows.append(_srow("clusters", "episode clusters", stat, d, "P1", "U_Q1", rule, lab, cl="ep",
                                  unit="episode", B=B))
                rows.append(_srow("clusters", "week clusters", stat, d, "P1", "U_Q1", rule, lab, cl="wk",
                                  unit="bid week", B=B))
                if len(d) > 2:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        tw = sbs.mean_cluster2(d["y"].to_numpy(float), d["coin"].astype(str).to_numpy(),
                                               d["mo"].to_numpy())
                    rows.append(dict(section="clusters", row="two-way coin x month", stat=stat, program="P1",
                                     universe="U_Q1", rule=rule, label=lab, n=int(len(d)),
                                     G=int(min(tw["G1"], tw["G2"])), gstar=NAN, unit="coin x month (two-way)",
                                     estimate=tw["mean"], ci_lo=tw["ci95"][0], ci_hi=tw["ci95"][1], se=tw["se"],
                                     mde=NAN, **event_cols(d)))
                else:
                    rows.append(dict(section="clusters", row="two-way coin x month", stat=stat, program="P1",
                                     universe="U_Q1", rule=rule, label=lab, n=int(len(d))))
        # delisting valuations (§4.1): the fills' mean r_f under each valuation. The engine values twins at the
        # primary rule only (no twin mean per delisting rule), so a Delta under another valuation would compare fills
        # and twins under different rules: fill valuation only (coding choice 14), on F1 and on F3 (s = 1%)
        for rule in ("F1", "F3_1"):
            cost = route_cost(rule)
            base = _h1(P, rule, "FLIP", cost, "r")
            nd = int((base["exit_kind"] == "delist").sum()) if len(base) and "exit_kind" in base else 0
            for v, nm in (("r", "delisting at the VWAP of the last full day x 0.70 (primary valuation)"),
                          ("r_dl_last", "delisting at the last trade x 0.70"), ("r_dl0", "delisting haircut 0%"),
                          ("r_dl100", "delisting haircut 100%")):
                d = _h1(P, rule, "FLIP", cost, v)
                ch = _h1(P, rule, "FLIP", cost, v[2:]) if v != "r" else d.assign(y=0.0)
                lab = "fill valuation only (twins unchanged): " + LABEL_DL + ("; " + LABEL_RH if rule != "F1" else "")
                rows.append(_srow("delisting", nm, "H1 mean r_f (fill valuation only)", d, "P1", "U_Q1", rule, lab,
                                  B=B, extra=dict(n_delisted=nd, change_vs_primary=float(ch["y"].mean())
                                                  if len(ch) else NAN)))
        # the bad-print filter
        for stat, d in (("H1 delta", _h1(P)), ("H2R a_f", _h2(P))):
            k = bad_print_mask(d)
            g = add_clusters(d[k].drop(columns=CL_COLS)) if len(d) else d
            rows.append(_srow("bad prints", "fills with < $1k seller notional below L in the fill minute, or an index "
                              "low above L, dropped", stat, g, "P1", "U_Q1", "F1", B=B,
                              extra=dict(dropped=int((~k).sum()), f3_note=F3_NOTE["bad prints"])))
    # universes
    for key, nm, lab in (("P1/U_B", "U-B (top 100, dead coins included)", ""),
                         ("P1/U_Q1_12", "U-Q1-12 (12-month listing rule)", ""),
                         ("P1/U_Q1_xm", "U-Q1-xm (no memecoins)", ""),
                         ("P1/U_A", "U-A (user-style coins)", LABEL_HINDSIGHT),
                         ("P1/U_C", "U-C (Robinhood-listed 2026-11-18)", LABEL_HINDSIGHT)):
        pair("universe", nm, runs.get(key), "P1", key.split("/")[1], lab)
    rows.append(dict(section="universe", row="U-Q2 (real revenue, DefiLlama)", stat="H1 delta", program="P1",
                     universe="U_Q2", rule="F1", label=LABEL_NOT_BUILT, n=0))
    return pd.DataFrame(rows)


# ============================================================================ exploratory splits (§10.4)
RULES_BESIDE = ("F1", "F3_1")                       # §12: every Binance number beside its F3 (s = 1%) number


def _bh_table(t: pd.DataFrame, pcol: str = "p") -> pd.DataFrame:
    """BH within the table (§10.4), separately for its F1 rows and its F3 rows (the F3 rows restate the F1 rows on
    the Robinhood-route proxy; they are not further hypotheses of the table; coding choice 15)."""
    if len(t) and pcol in t:
        t = t.copy()
        t["q_bh"] = NAN
        if "rule" in t:
            for _, idx in t.groupby("rule", sort=False).groups.items():
                t.loc[idx, "q_bh"] = sbs.bh(t.loc[idx, pcol].to_numpy(float))
            t["p_note"] = "exploratory; BH within this table, F1 and F3 rows separately"
        else:
            t["q_bh"] = sbs.bh(t[pcol].to_numpy(float))
            t["p_note"] = "exploratory; BH within this table"
    return t


def _xrow(table, row, d, B, two_sided=False, X=None, j=0, extra=None, rule="F1"):
    """One exploratory row: the estimate (a mean, or coefficient j of X), its 95% interval, G, G*, the §10.2 p, and
    the §10.4 single events (the mean, or the coefficient re-fitted, without 2025-10-10, without 2021-05-19 and
    without the top month-block)."""
    base = dict(table=table, row=row, rule=rule, label=rule_label(rule))
    y = d["y"].to_numpy(float) if len(d) else np.zeros(0)
    cl = d["mb"].to_numpy() if len(d) else np.zeros(0)
    ev = event_cols(d) if X is None else event_coefs(d, X, j)
    if len(y) < 2:
        out = dict(base, n=int(len(y)), estimate=float(np.mean(y)) if len(y) and X is None else NAN, p=NAN, **ev)
        out.update(extra or {})
        return out
    fn = p_two if two_sided else p_one
    p, r = fn(y, cl, X, j, None, B)
    ci = r.get("ci95", (NAN, NAN))
    out = dict(base, n=int(r.get("n", len(y))), G=int(r.get("G", 0) or 0), gstar=_f(r.get("gstar")),
               unit="month-block", estimate=_f(r.get("estimate")), ci_lo=_f(ci[0]), ci_hi=_f(ci[1]), p=p,
               sided="two-sided" if two_sided else "one-sided (> 0)", **ev)
    out.update(extra or {})
    return out


def _diff(table, row, d, mask, B, extra=None, rule="F1"):
    if not len(d):
        return dict(table=table, row=row, rule=rule, label=rule_label(rule), n=0, estimate=NAN, p=NAN,
                    **{k: NAN for k in EVENT_NAMES})
    X = np.column_stack([np.ones(len(d)), np.asarray(mask, float)])
    return _xrow(table, row, d, B, two_sided=True, X=X, j=1, extra=extra, rule=rule)


def _sub(d: pd.DataFrame, mask) -> pd.DataFrame:
    """Rows of a per-fill sample with its clusters rebuilt on the subset (coding choice 1)."""
    return add_clusters(d[np.asarray(mask, bool)].drop(columns=CL_COLS, errors="ignore"))


def explore_tables(runs: dict, metrics_fn=None, B: int = B_DEFAULT, hype: dict | None = None) -> dict:
    """The exploratory splits of §10.4 (BH within each table): the depth gradient over k = 5..12, market-wide against
    coin-specific fills, flow from 2021-12 (open-interest drop, aggressor-sell bursts), weekday against weekend, M3 and
    M8 by parameter, and the user's coins individually (fill by fill; HYPE on its perpetual index, no verdict). Every
    row is computed on F1 and, beside it, on F3 (s = 1%, the Robinhood-route proxy; §12), and carries the §10.4
    single events. On the F3 rows the market-wide flag and the fill-minute seller burst are those of the bid's F1 fill
    (the engine computes them for F1 fills), the open-interest change and the weekday are taken at the F3 fill."""
    P = runs.get("P1/U_Q1")
    out = {}
    # depth gradient (the F1 slope row is the one the sheet's "best rung" reads)
    rows = []
    for rule in RULES_BESIDE:
        parts = []
        for key in ("P1/U_Q1", "P1-k5-12/U_Q1"):
            res = runs.get(key)
            if res is not None:
                d = _h1(res, rule)
                if len(d):
                    parts.append(d)
        if parts:
            D = add_clusters(pd.concat(parts, ignore_index=True).drop(columns=CL_COLS))
            for k in sorted(pd.unique(D["rung"])):
                rows.append(_xrow("depth gradient", f"rung k = {k:g}: mean Delta", _sub(D, D["rung"] == k), B,
                                  rule=rule))
            X = np.column_stack([np.ones(len(D)), D["rung"].to_numpy(float)])
            rows.append(_xrow("depth gradient", "slope of Delta on k (per sigma of depth)", D, B, two_sided=True, X=X,
                              j=1, extra=dict(is_gradient=bool(rule == "F1")), rule=rule))
    out["depth_gradient"] = _bh_table(pd.DataFrame(rows))
    # breadth
    rows = []
    if P is not None:
        for rule in RULES_BESIDE:
            for stat, d in (("H1 delta", _h1(P, rule)), ("H2R a_f", _h2(P, rule))):
                if len(d) and "mw" in d:
                    mw = pd.to_numeric(d["mw"], errors="coerce").to_numpy(float)
                    for v, nm in ((1, "market-wide"), (0, "coin-specific")):
                        rows.append(_xrow("breadth", f"{stat}: {nm}", _sub(d, mw == v), B, rule=rule))
                    ok = np.isfinite(mw)
                    rows.append(_diff("breadth", f"{stat}: market-wide minus coin-specific", _sub(d, ok), mw[ok] == 1,
                                      B, rule=rule))
    out["breadth"] = _bh_table(pd.DataFrame(rows))
    # weekday vs weekend
    rows = []
    if P is not None:
        for rule in RULES_BESIDE:
            for stat, d in (("H1 delta", _h1(P, rule)), ("H2R a_f", _h2(P, rule))):
                if len(d):
                    we = d["time"].dt.dayofweek.to_numpy() >= 5
                    for v, nm in ((False, "weekday"), (True, "weekend")):
                        rows.append(_xrow("weekday", f"{stat}: {nm}", _sub(d, we == v), B, rule=rule))
                    rows.append(_diff("weekday", f"{stat}: weekend minus weekday", d, we, B, rule=rule))
    out["weekday"] = _bh_table(pd.DataFrame(rows))
    # flow from 2021-12: open-interest drop in the hour before the fill, aggressor-sell burst in the fill minute
    rows = []
    if P is not None:
        for rule in RULES_BESIDE:
            d = _h1(P, rule)
            d = _sub(d, d["time"] >= pd.Timestamp("2021-12-01", tz="UTC")) if len(d) else d
            if not len(d):
                continue
            burst = pd.to_numeric(d["agg_m0"], errors="coerce").to_numpy(float) if "agg_m0" in d \
                else np.full(len(d), NAN)
            c1 = pd.to_numeric(d["c1_m0"], errors="coerce").to_numpy(float) if "c1_m0" in d \
                else np.full(len(d), NAN)
            burst = np.where(np.isfinite(burst), burst, c1)
            ok = np.isfinite(burst)
            if ok.sum() > 3:
                hi = burst >= np.nanmedian(burst[ok])
                rows.append(_diff("flow", "H1 delta: seller-notional burst in the fill minute above vs below median",
                                  _sub(d, ok), hi[ok], B, rule=rule))
            if metrics_fn is not None:
                oi = np.array([metrics_fn(c, int(t)) for c, t in zip(d["coin"].astype(str), d["t_fill"])], float)
                ok = np.isfinite(oi)
                if ok.sum() > 3:
                    drop = oi <= np.nanmedian(oi[ok])
                    rows.append(_diff("flow", "H1 delta: open-interest change in the hour before the fill, larger "
                                      "drop vs smaller", _sub(d, ok), drop[ok], B, rule=rule))
            else:
                rows.append(dict(table="flow", row="open-interest drop", rule=rule, label=rule_label(rule), n=0,
                                 estimate=NAN, p=NAN, note="futures metrics not available"))
    out["flow"] = _bh_table(pd.DataFrame(rows))
    # M3 and M8 by parameter
    rows = []
    for key, nm in (("M3/U_Q1", "M3"), ("M8/U_Q1", "M8")):
        res = runs.get(key)
        for rule in RULES_BESIDE:
            if res is None:
                rows.append(dict(table="M3 and M8", row=f"{nm}: not run", rule=rule, n=0, estimate=NAN, p=NAN))
                continue
            d = _h1(res, rule)
            if not len(d):
                rows.append(dict(table="M3 and M8", row=f"{nm}: no fills", rule=rule, label=rule_label(rule), n=0,
                                 estimate=NAN, p=NAN))
                continue
            for var in sorted(pd.unique(d["variant"])):
                rows.append(_xrow("M3 and M8", f"{var}: mean Delta", _sub(d, d["variant"] == var), B, rule=rule))
    out["m3_m8"] = _bh_table(pd.DataFrame(rows))
    # the user's coins individually (U-A, hindsight), fill by fill
    rows, fills = [], []
    A = runs.get("P1/U_A")
    if A is not None:
        for rule in RULES_BESIDE:
            d = _h1(A, rule)
            lab = LABEL_HINDSIGHT + ("; " + LABEL_RH if rule != "F1" else "")
            for c in sorted(pd.unique(d["coin"].astype(str))) if len(d) else []:
                rows.append(_xrow("user coins", f"{c}: mean Delta", _sub(d, d["coin"].astype(str) == c), B,
                                  extra=dict(coin=c, label=lab), rule=rule))
        d = _h1(A)
        a2 = _h2(A)
        a = a2[["fill_id", "y"]].rename(columns={"y": "a_f"}) if len(a2) else pd.DataFrame(columns=["fill_id", "a_f"])
        d3 = _h1(A, "F3_1")
        f3 = d3[["fill_id", "y"]].rename(columns={"y": "delta_flip_F3"}) if len(d3) else \
            pd.DataFrame(columns=["fill_id", "delta_flip_F3"])
        if len(d):
            f = d.merge(a, on="fill_id", how="left").merge(f3, on="fill_id", how="left")
            fills = f[["coin", "time", "rung", "P0", "L", "depth", "y", "r", "a_f", "delta_flip_F3"]].rename(
                columns={"y": "delta_flip", "depth": "depth_sigma"})
    out["user_coins"] = _bh_table(pd.DataFrame(rows))
    out["user_fills"] = pd.DataFrame(fills) if len(fills) else pd.DataFrame()
    # HYPE on its perpetual's index price (short history, no verdict; it trades on the index itself, so it has no
    # separate F3 row)
    hlab = (hype or {}).get("label") or "short history, perpetual-index proxy, no verdict"
    if hype is not None and hype.get("res") is not None:
        d = _h1(hype["res"])
        out["hype"] = pd.DataFrame([dict(row="HYPE (perpetual-index proxy)", n=int(len(d)),
                                         mean_delta=float(d["y"].mean()) if len(d) else NAN, label=hlab,
                                         note=HYPE_NOTE, **event_cols(d))])
        if len(d):
            out["hype_fills"] = d[["time", "rung", "P0", "L", "depth", "y", "r"]].rename(
                columns={"y": "delta_flip", "depth": "depth_sigma"})
    else:
        out["hype"] = pd.DataFrame([dict(row="HYPE (perpetual-index proxy)", n=0, mean_delta=NAN, label=hlab,
                                         note=(hype or {}).get("note", "not run") + ". " + HYPE_NOTE)])
    return out


# ============================================================================ the descriptive sentences (§11)
def _bw(x) -> str:
    return "better" if _f(x) >= 0 else "worse"


def sentence_dh2(r: dict) -> str:
    x = _f(r.get("estimate"))
    return (f"Descriptive only. Over 90 days, coins bought through stink bids did {fmt_pct(abs(x))} "
            f"({fmt_ci(r.get('ci_lo'), r.get('ci_hi'))} for the difference) {_bw(x)} than the same coins bought at "
            "random times outside the six months around each fill. An edge under about 20-40% could not be detected, "
            "and the comparison also reflects whether the crashes fell in bear or bull stretches. "
            f"[{unc(r)}; MDE computed here {fmt_pct(r.get('mde'))}]")


def sentence_dh3(r: dict) -> str:
    x = _f(r.get("estimate"))
    return (f"Descriptive only. Fast wicks were {fmt_pct(abs(x))} per fill ({fmt_ci(r.get('ci_lo'), r.get('ci_hi'))} "
            f"for the difference) {_bw(x)} than slow slides to the same depth. A difference under about 6-10% per fill "
            f"could not be detected. [{unc(r)}; episode fixed effects; MDE computed here {fmt_pct(r.get('mde'))}]")


def sentence_dh5(rows: dict, u_q2_built: bool = False) -> str:
    p = (rows.get("U_Q1") or {}).get("primary") or {}
    p12 = (rows.get("U_Q1_12") or {}).get("primary") or {}
    if not p or "error" in p:
        return "Descriptive only. D-H5 could not be estimated (no fills with a 365-day horizon in both groups)."
    s = (f"Descriptive only. A year after a fill, {fmt_pct(p.get('rate_q1'))} of fills on large, long-listed coins "
         f"and {fmt_pct(p.get('rate_rest'))} on other top-100 coins were 50% or more below the fill price; at the "
         f"same volatility the gap was {fmt_pts(p.get('b'))} points (95% CI {fmt_pts(p.get('ci95', (NAN, NAN))[0])} to "
         f"{fmt_pts(p.get('ci95', (NAN, NAN))[1])}). Neither LUNA (kept out by listing age) nor FTT (kept out by "
         "Binance volume rank) was in the large, long-listed group, so this says nothing about fraud collapses of "
         "large coins. In the 12-month row, where LUNA is included, the gap was "
         f"{fmt_pts(p12.get('b')) if p12 and 'error' not in p12 else 'n/a'} points.")
    if not u_q2_built:
        s += " The study did not test a real-revenue filter."
    s += (f" [{int(p.get('n', 0))} fills; two-way coin x quarter clusters, G_coin = {p.get('G_coin')}, "
          f"G_quarter = {p.get('G_quarter')}, t at {p.get('df')} df]")
    return s


def sentence_d8(r: dict) -> str:
    a, b = r.get("premium_72h", {}), r.get("after_72h_vs_tbill", {})
    return ("Flip or own is a choice about whether you want to hold the coin, not about stink-bid skill. The study's "
            f"evidence on the bid is the same for both. [shared premium (the alert buyer's price 72 h later): "
            f"{fmt_pct(a.get('estimate'), sign=True)} ({fmt_ci(a.get('ci_lo'), a.get('ci_hi'))}; {unc(a)}); "
            f"return from 72 h to 90 days against T-bills: {fmt_pct(b.get('estimate'), sign=True)} "
            f"({fmt_ci(b.get('ci_lo'), b.get('ci_hi'))}; {unc(b)})]")


# ============================================================================ stage-level compute and write
def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, pd.DataFrame):
        return json.loads(x.to_json(orient="records", date_format="iso", default_handler=str))
    if isinstance(x, pd.Series):
        return _jsonable(x.to_dict())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.ndarray,)):
        return [_jsonable(v) for v in x.tolist()]
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(x)
    return x


def compute_desc(runs: dict, data=None, calib: dict | None = None, tbill_at=None, B: int = B_DEFAULT,
                 controls: dict | None = None, log=print) -> dict:
    """Every pre-registered descriptive estimand, table and sensitivity row of §10.4 from the engine runs (keys
    'PROGRAM/UNIVERSE'). Returns {name: DataFrame or dict}."""
    T = {}
    P = runs.get("P1/U_Q1")
    t0 = time.time()

    def step(name, fn):
        t = time.time()
        try:
            T[name] = fn()
        except Exception as e:                              # a failed table is reported, never silently dropped
            T[name] = dict(error=repr(e))
        log(f"  desc {name}: {time.time() - t:.1f}s")
    k1c = (controls or {}).get("K1c", {}) if isinstance(controls, dict) else {}
    step("d12", lambda: d12(P))
    step("dh2", lambda: dh2(P, B, k1c=k1c.get("delta90") if isinstance(k1c, dict) else None))
    step("dh3", lambda: dh3(P, B))
    step("dh5", lambda: dh5(runs.get("P1/U_B"), B) if runs.get("P1/U_B") is not None else dict(note="no U-B run"))
    step("t1", lambda: dict(zip(("summary", "episodes"), t1({"U-Q1": P, "U-Q1-12": runs.get("P1/U_Q1_12"),
                                                             "U-B": runs.get("P1/U_B")}, B))))
    step("d6", lambda: d6(P, tbill_at, B))
    step("d7", lambda: d7(P, data, B))
    step("dml", lambda: dml(P, runs.get("P1-G/U_Q1"), B))
    step("d8", lambda: d8(P, tbill_at, B))
    step("d1", lambda: d1({"U-Q1": P, "U-B": runs.get("P1/U_B"), "U-A (hindsight)": runs.get("P1/U_A"),
                           "U-C (hindsight)": runs.get("P1/U_C")}))
    step("d2", lambda: d2({"1 day": runs.get("P1-1/U_Q1"), "7 days": P, "30 days": runs.get("P1-30/U_Q1"),
                           "90 days": runs.get("P1-90/U_Q1")}))
    step("d3", lambda: d3(P))
    step("d4", lambda: d4(P))
    step("d5", lambda: d5(P, runs.get("M3/U_Q1"), B))
    step("sheet_coin_rung", lambda: sheet_stats(P))
    H = runs.get("H4-all/U_Q1") or runs.get("H4/U_Q1")
    step("d10", lambda: pd.concat([d10(H, "F1", B), d10(H, "F3_1", B)], ignore_index=True)
         if H is not None else pd.DataFrame())
    step("d9", lambda: d9(runs.get("H4-all/U_Q1"), "F4", B) if runs.get("H4-all/U_Q1") is not None
         else dict(test="D9", note="H4-all not run"))
    if isinstance(T.get("d10"), pd.DataFrame) and isinstance(T.get("d9"), dict):
        dd = T["d10"]
        T["d10_family"] = d10_family(dd[dd["rule"] == "F1"] if len(dd) else dd, T["d9"])
    h1 = _h1(P) if P is not None else pd.DataFrame()
    tw = float(h1["twin_mean"].sum()) if len(h1) and "twin_mean" in h1 else NAN
    step("d11", lambda: d11(float(h1["y"].sum()) if len(h1) else NAN, tw, calib))
    step("sensitivity", lambda: sensitivity(runs, B))
    log(f"  desc total {time.time() - t0:.0f}s")
    return T


def _safe_name(x) -> str:
    s = "_".join(str(v) for v in x) if isinstance(x, tuple) else str(x)
    return "".join(ch if (ch.isalnum() or ch in "-.") else "_" for ch in s)


def write_tables(dirpath: Path, T: dict, title: str, sentences: list | None = None) -> list:
    """Write every DataFrame as CSV, the whole set as JSON and a readable text file. Returns the paths written."""
    dirpath = Path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    written = []
    js = {}
    lines = [title, "=" * len(title), ""]
    if sentences:
        lines += ["Sentences", "---------"] + [f"- {s}" for s in sentences] + [""]
    for name, v in T.items():
        if isinstance(v, pd.DataFrame):
            f = dirpath / f"{name}.csv"
            v.to_csv(f, index=False)
            written.append(str(f))
            js[name] = _jsonable(v)
            lines += [f"[{name}] ({len(v)} rows) -> {f.name}"]
            if len(v):
                with pd.option_context("display.max_columns", 40, "display.width", 200,
                                       "display.max_colwidth", 60):
                    lines += [v.head(60).to_string(index=False), ""]
        elif isinstance(v, dict):
            flat = {}
            for k, x in v.items():
                if isinstance(x, pd.DataFrame):
                    f = dirpath / f"{name}_{k}.csv"
                    x.to_csv(f, index=False)
                    written.append(str(f))
                    flat[k] = _jsonable(x)
                elif isinstance(x, dict) and any(isinstance(z, pd.DataFrame) for z in x.values()):
                    sub = {}
                    for kk, z in x.items():
                        if isinstance(z, pd.DataFrame):
                            nm = f"{name}_{k}_{_safe_name(kk)}.csv"
                            z.to_csv(dirpath / nm)
                            written.append(str(dirpath / nm))
                            sub[str(kk)] = f"see {nm}"
                        else:
                            sub[str(kk)] = _jsonable(z)
                    flat[k] = sub
                else:
                    flat[k] = _jsonable(x)
            js[name] = flat
            lines += [f"[{name}]", json.dumps(_jsonable({k: x for k, x in flat.items()}), indent=1, default=str)[:6000],
                      ""]
    jf = dirpath / (dirpath.name + ".json")
    jf.write_text(json.dumps(_jsonable(js), indent=1, default=str))
    tf = dirpath / (dirpath.name + ".txt")
    tf.write_text("\n".join(lines) + "\n")
    written += [str(jf), str(tf)]
    return written


def desc_sentences(T: dict, u_q2_built: bool = False) -> list:
    """The §11 descriptive sentences (D-H2, D-H3, D-H5, D8) with their estimates, plus the D-H2 regime caveat."""
    out = []
    if isinstance(T.get("dh2"), dict) and "twin" in T["dh2"]:
        out.append(sentence_dh2(T["dh2"]["twin"]))
        k = T["dh2"].get("k1c")
        out.append(REGIME_CAVEAT + (f" (K1c, regime timing alone: {fmt_pct(k, sign=True)} per 90 days)"
                                    if k is not None and np.isfinite(_f(k)) else ""))
    if isinstance(T.get("dh3"), dict) and "s24" in T["dh3"]:
        out.append(sentence_dh3(T["dh3"]["s24"]["primary"]))
    if isinstance(T.get("dh5"), dict) and "U_Q1" in T["dh5"]:
        out.append(sentence_dh5(T["dh5"], u_q2_built))
    if isinstance(T.get("d8"), dict) and "premium_72h" in T["d8"]:
        out.append(sentence_d8(T["d8"]))
    return out


# ============================================================================ selftest (synthetic known answers)
def _fake_res(n_fill: int = 40, seed: int = 0) -> dict:
    """A hand-made engine result: one coin, weekly bids at three rungs, fills on known minutes and known outcomes."""
    rng = np.random.default_rng(seed)
    t_first = int(pd.Timestamp("2022-06-06 03:30", tz="UTC").value // MIN_NS)
    rows, fills, outs, bench = [], [], [], []
    bid = 0
    for w in range(60):
        t0 = t_first + w * 7 * DAY_M
        for k in RUNGS_P1:
            rows.append(dict(bid_id=bid, coin="AAA", rung=k, variant=f"M2 k={k:g}", method="M2", real=True,
                             shift=np.nan, cw=f"AAA|{w}", t0=t0, live_from=t0 + 1, life_end=t0 + 7 * DAY_M,
                             delta=k, month=0, ml_d0=int(w % 3 == 0), P0=10.0, L=10 * math.exp(-0.04 * k),
                             sigma30=0.04, mkt_r365=0.0, bid_r365=np.nan, r365_complete=True))
            bid += 1
    b = pd.DataFrame(rows)
    pick = rng.choice(len(b), n_fill, replace=False)
    for i in pick:
        r = b.iloc[i]
        tf = int(r.live_from) + int(rng.integers(0, 6 * DAY_M))
        fills.append(dict(bid_id=int(r.bid_id), coin="AAA", rung=r.rung, variant=r.variant, t_F1=tf,
                          t_F3_1=tf if rng.random() < 0.8 else -1, s24=float(rng.uniform(0, 1.2)),
                          mw=float(rng.random() < 0.7), delta=r.delta, L=r.L, P0=10.0, sigma30=0.04,
                          ml_d0=r.ml_d0, in_U_Q1=True, in_U_C=bool(rng.random() < 0.5), share_10k_1=1.0,
                          c1_life=1e6, cap_src="c1", agg_m0=np.nan, c1_m0=float(rng.uniform(0, 5000)),
                          idx_low_rel=0.99))
    F = pd.DataFrame(fills).sort_values("t_F1").reset_index(drop=True)
    F["fill_id"] = np.arange(len(F))
    for f in F.itertuples():
        for rule in ("F1", "F3_1"):
            if getattr(f, "t_" + rule) < 0:
                continue
            y = float(rng.normal(0.01, 0.05))
            outs.append(dict(fill_id=f.fill_id, coin="AAA", rule=rule, exit="FLIP", lat="M", cost=route_cost(rule),
                             r=y - 0.02, twin_mean=-0.02, delta=y, complete=True, exit_px=11.0, exit_t=f.t_F1 + 99))
        bench.append(dict(fill_id=f.fill_id, rule="F1", coin="AAA", alert_M=float(rng.normal(0.02, 0.03)),
                          knife=float(rng.random() < 0.2), twin_knife=0.1, low365=float(rng.uniform(0.3, 1.0))))
    return dict(bids=b, fills=F, outcomes=pd.DataFrame(outs), bench=pd.DataFrame(bench))


def selftest() -> bool:
    t0 = time.time()
    say = lambda m: print(m, flush=True)
    res = _fake_res()
    # 1. samples: merge, complete filter, F3 rows, clusters rebuilt on the sample
    d = per_fill(res, "F1", "FLIP")
    assert len(d) == len(res["fills"]), (len(d), len(res["fills"]))
    O = res["outcomes"]
    ref = O[(O.rule == "F1") & (O.exit == "FLIP")].set_index("fill_id")["delta"]
    assert np.allclose(d.set_index("fill_id")["y"].sort_index(), ref.sort_index())
    res2 = dict(res, outcomes=O.assign(complete=np.where(O.fill_id % 5 == 0, False, True)))
    d2_ = per_fill(res2, "F1", "FLIP")
    assert len(d2_) == int((ref.index % 5 != 0).sum())
    d3_ = per_fill(res, "F3_1", "FLIP")
    assert len(d3_) == int((res["fills"].t_F3_1 >= 0).sum())
    assert "depth" in d and np.allclose(d["y"], d["delta"])           # Delta_f, not the bid's depth
    mb_ref = sbs.month_blocks(ts_min(d.t_F1.to_numpy()))[0]
    assert np.array_equal(d["mb"].to_numpy(), mb_ref)
    say(f"  samples: {len(d)} F1 fills, {len(d2_)} complete, {len(d3_)} F3 fills; clusters rebuilt on each sample")
    # 2. concentration and single events against direct computation
    rb = robust(d)
    ep = d["ep"].to_numpy()
    u, c = np.unique(ep, return_counts=True)
    top = u[np.lexsort((u, -c))][:3]
    sel = np.isin(ep, top)
    assert math.isclose(rb["top3_share"], d["y"][sel].sum() / d["y"].sum(), rel_tol=1e-12)
    assert math.isclose(rb["top3_without"], d["y"][~sel].mean(), rel_tol=1e-12)
    tb = _top_block(d["mb"].to_numpy())
    assert math.isclose(rb["without_top_block"], d["y"][d["mb"] != tb].mean(), rel_tol=1e-12)
    say(f"  concentration: top-3 share {rb['top3_share']:.3f}, without them {rb['top3_without']:+.4f} (oracle equal)")
    # 3. worst day and KM waits on hand-made bids
    t = int(pd.Timestamp("2023-01-02 03:30", tz="UTC").value // MIN_NS)
    hb = pd.DataFrame(dict(coin=["A", "A", "A", "B", "B", "C", "D"], rung=[6.0] * 7,
                           t0=[t, t + 7 * DAY_M, t + 14 * DAY_M, t, t + 7 * DAY_M, t, t + 7 * DAY_M],
                           live_from=[t + 1, t + 7 * DAY_M + 1, t + 14 * DAY_M + 1, t + 1, t + 7 * DAY_M + 1, t + 1,
                                      t + 7 * DAY_M + 1],
                           life_end=[t + 7 * DAY_M, t + 14 * DAY_M, t + 21 * DAY_M, t + 7 * DAY_M, t + 14 * DAY_M,
                                     t + 7 * DAY_M, t + 14 * DAY_M],
                           t_F1=[-1, t + 10 * DAY_M, -1, -1, t + 10 * DAY_M + 5, t + 3 * DAY_M, -1]))
    # day t+3: A1, B1, C and nothing else live, C fills (1/3); day t+10: A2, B2, D live, A2 and B2 fill (2/3)
    wd = worst_day(hb)
    assert wd["filled"] == 2 and wd["live"] == 3 and math.isclose(wd["share"], 2 / 3), wd
    W = km_waits(hb)
    wa = W[(W.coin == "A")].sort_values("t0")["wait_d"].to_numpy()
    assert np.allclose(wa, [10.0, 3.0, 7.0]) and list(W[W.coin == "A"].sort_values("t0")["event"]) == [True, True,
                                                                                                         False]
    say(f"  worst day {wd['share']:.3f} ({wd['filled']}/{wd['live']}); KM waits A = {wa.tolist()} (chain, censored)")
    # 4. bid clusters: weeks linked by one episode
    fm = np.array([t + 6 * DAY_M, t + 8 * DAY_M, -1, -1], float)
    t0s = np.array([t, t + 7 * DAY_M, t + 14 * DAY_M, t + 28 * DAY_M])
    cl = bid_clusters(t0s, fm)
    assert cl[0] == cl[1] and len(np.unique(cl)) == 3, cl
    say(f"  bid-week clusters: weeks 0 and 1 linked by an episode, {len(np.unique(cl))} clusters")
    # 5. logit expected rate: a real level filling like its placebos has mean(fill - expected) near 0
    rng = np.random.default_rng(1)
    x = rng.uniform(4, 14, 4000)
    pr = 1 / (1 + np.exp(-(1.0 - 0.45 * x)))
    y = (rng.random(4000) < pr).astype(float)
    b_, c_ = _logit(x, y)
    assert b_ is not None and abs(b_[1] + 0.45) < 0.1, b_
    e = y - _logit_predict(b_, c_, x)
    assert abs(e.mean()) < 1e-6, e.mean()
    say(f"  logit: slope {b_[1]:.3f} (true -0.45); mean(fill - expected) {e.mean():.2e}")
    # 6. D9 difference in differences on hand-made fills: the real M5f always fills, the real M5a never, and the
    #    placebos of both fill together (even weeks) or not at all, so every coin-week's z is 1
    bids, fls = [], []
    bid = 0
    for w in range(12):
        tt = t + w * 7 * DAY_M
        for meth in ("M5f", "M5a"):
            for sh in (0.0, -0.5, 0.5):
                fill = (meth == "M5f" and sh == 0.0) or (w % 2 == 0 and sh != 0.0)
                bids.append(dict(bid_id=bid, coin="A", method=meth, variant=meth, shift=sh, real=sh == 0.0,
                                 cw=f"A|{w}", t0=tt, delta=8.0, rung=0.0))
                if fill:
                    fls.append(dict(bid_id=bid, t_F4=tt + 100 + w))
                bid += 1
    rr = dict(bids=pd.DataFrame(bids), fills=pd.DataFrame(fls))
    r9 = d9(rr, "F4", B=999)
    assert math.isclose(r9["estimate"], 1.0, rel_tol=1e-12), r9
    say(f"  D9: difference in differences {r9['estimate']:.3f} (hand-made answer 1.000), p {r9['p']:.4f}")
    # 7. BH within a table equals stinkbid_stats.bh; wording rule
    tb_ = _bh_table(pd.DataFrame(dict(p=[0.01, 0.04, 0.03, np.nan])))
    assert np.allclose(tb_["q_bh"].to_numpy()[:3], sbs.bh([0.01, 0.04, 0.03, np.nan])[:3])
    s1 = sentence_dh2(dict(estimate=-0.05, ci_lo=-0.2, ci_hi=0.1, n=10, G=5, gstar=3.0, unit="quarter-block",
                           mde=0.3))
    s2 = sentence_dh3(dict(estimate=0.02, ci_lo=-0.05, ci_hi=0.09, n=10, G=5, gstar=3.0, unit="month-block",
                           mde=0.08))
    assert "worse" in s1 and "better" in s2 and not check_wording([s1, s2])
    assert check_wording(["Stink bids works"]) and check_wording(["It made no difference"])
    say("  BH within a table; descriptive sentences pass the wording rule (better / worse by sign)")
    # 8. per-fill means with month-block clusters through stat_row = stinkbid_stats.describe
    r = mean_row(d, B=999)
    ref = sbs.describe(d["y"].to_numpy(), d["mb"].to_numpy(), B=999)
    assert math.isclose(r["estimate"], ref["estimate"]) and math.isclose(r["ci_lo"], ref["ci95"][0])
    say(f"  stat_row = describe: {r['estimate']:+.4f} [{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}] G {r['G']} "
        f"G* {r['gstar']:.1f}")
    # 9. bad-print mask
    m = bad_print_mask(d)
    ref_m = ~(d["c1_m0"].to_numpy() < BAD_PRINT_USD)
    assert np.array_equal(m, ref_m)
    say(f"  bad-print filter drops {int((~m).sum())} of {len(m)} fills (C1 < $1k in the fill minute)")
    _t_review_regressions(say, res)
    say(f"stinkbid_desc selftest: all passed ({time.time() - t0:.0f}s)")
    return True


def _t_review_regressions(say, res: dict):
    """Regression checks for the runner review's findings (known answers written here, not with the code under test):
    worst_day's live definition (11), the delisting rows (7), the sheet's waits on F3 (4), D6 on F3 with single
    events (4, 8), T1's single-event rows, the exploratory F3 rows, BH per route and single events (8), event_coefs."""
    t = int(pd.Timestamp("2025-10-06 03:30", tz="UTC").value // MIN_NS)           # a Monday placement
    # (11) worst day: 10 weekly bids, 5 fill on Wednesday, 5 on Friday: on Friday only the 5 still resting are live
    wb = pd.DataFrame(dict(coin=[f"C{i}" for i in range(10)], rung=6.0, variant="M2 k=6", t0=t, live_from=t + 1,
                           life_end=t + 7 * DAY_M, t_F1=[t + 2 * DAY_M + 60] * 5 + [t + 4 * DAY_M + 60] * 5))
    wd = worst_day(wb)
    assert wd["day"] == "2025-10-10" and wd["filled"] == 5 and wd["live"] == 5 and wd["share"] == 1.0, wd
    # a Monday: the outgoing bid (week 1, unfilled) and the incoming bid (week 2) of a slot are one live order; slot C
    # fills on Monday at 01:00, before its replacement is placed (the only fill day): live A, B, C (not 5 bids)
    t2 = t + 7 * DAY_M
    mb_ = pd.DataFrame(dict(coin=["A", "A", "B", "B", "C"], rung=6.0, variant="M2 k=6",
                            t0=[t, t2, t, t2, t], live_from=[t + 1, t2 + 1, t + 1, t2 + 1, t + 1],
                            life_end=[t2, t2 + 7 * DAY_M, t2, t2 + 7 * DAY_M, t2],
                            t_F1=[-1, -1, -1, -1, t2 - 150]))
    wm = worst_day(mb_)
    assert wm["day"] == "2025-10-13" and wm["live"] == 3 and wm["filled"] == 1, wm
    say(f"  worst day: {wd['filled']}/{wd['live']} on {wd['day']} (bids filled earlier in the week are not live); a "
        f"Monday counts each slot once ({wm['filled']}/{wm['live']})")
    # (7) delisting rows: fills and twins delisted at V = 0.5 L; under every valuation the fills' r_f is known
    n = 24
    t0 = int(pd.Timestamp("2022-03-07 03:30", tz="UTC").value // MIN_NS)
    tf = t0 + np.arange(n) * 7 * DAY_M + 600
    cb = cs = 0.0095

    def r_of(h):
        return 0.5 * (1 - h) * (1 - cs) / (1 + cb) - 1
    Fd = pd.DataFrame(dict(fill_id=np.arange(n), bid_id=np.arange(n), coin="AAA", rung=6.0, variant="M2 k=6",
                           t_F1=tf, t_F3_1=tf, delta=6.0))
    od = []
    for rule, cost in (("F1", "C-RH"), ("F3_1", "RH")):
        od.append(pd.DataFrame(dict(fill_id=Fd.fill_id, coin="AAA", rule=rule, exit="FLIP", lat="M", cost=cost,
                                    complete=True, exit_kind="delist", r=r_of(0.30), r_dl_last=r_of(0.30),
                                    r_dl0=r_of(0.0), r_dl100=r_of(1.0), twin_mean=r_of(0.30), delta=0.0)))
    rd = dict(fills=Fd, outcomes=pd.concat(od, ignore_index=True), bids=Fd.assign(t0=t0), bench=pd.DataFrame())
    S = sensitivity({"P1/U_Q1": rd}, B=99)
    dl = S[S["section"] == "delisting"]
    assert len(dl) == 8 and set(dl["rule"]) == {"F1", "F3_1"} and (dl["stat"] == "H1 mean r_f (fill valuation only)"
                                                                   ).all(), dl[["row", "rule", "stat"]]
    for h, key in ((0.30, "delisting at the VWAP of the last full day x 0.70 (primary valuation)"),
                   (0.30, "delisting at the last trade x 0.70"), (0.0, "delisting haircut 0%"),
                   (1.0, "delisting haircut 100%")):
        rr = dl[dl["row"] == key]
        assert len(rr) == 2 and np.allclose(rr["estimate"], r_of(h)), (key, rr["estimate"].tolist(), r_of(h))
        assert np.allclose(rr["change_vs_primary"], r_of(h) - r_of(0.30)) and (rr["n_delisted"] == n).all()
    assert np.allclose(per_fill(rd, "F1", "FLIP", "C-RH", "dl0")["y"], r_of(0.0) - r_of(0.30))   # never vs twins
    assert not ((S["stat"] == "H1 delta") & (S["section"] == "delisting")).any()
    say(f"  delisting rows: fill valuation only on F1 and F3 (r_f {r_of(0.0):+.3f} / {r_of(1.0):+.3f} at 0% / 100%, "
        "known answers); no Delta mixes fills and twins under different valuations")
    # (4) the sheet's waits on each row's own rule
    sc = sheet_stats(res)
    b = bid_fill_table(res, ("F1", "F3_1"))
    for rule in ("F1", "F3_1"):
        w = km_waits(b, "t_" + rule)
        for rg in RUNGS_P1:
            ww = w[w["rung"] == rg]
            ws = sbs.waiting_summary(ww["wait_d"].to_numpy(float), ww["event"].to_numpy(bool), 365.0)
            row = sc[(sc["coin"] == "ALL") & (sc["rung"] == rg) & (sc["rule"] == rule)].iloc[0]
            assert math.isclose(row["p_no_fill_year"], ws["p_no_fill"], abs_tol=1e-12), (rule, rg)
            assert (np.isnan(ws["median"]) and np.isnan(row["median_wait_weeks"])) or \
                math.isclose(row["median_wait_weeks"], ws["median"] / 7, rel_tol=1e-12), (rule, rg)
    f3w = sc[(sc["rule"] == "F3_1") & (sc["coin"] == "ALL")]["median_wait_weeks"]
    assert np.isfinite(f3w).all() and (sc.loc[sc["rule"] == "F1", "label"] == "Binance spot (upper bound)").all()
    say(f"  sheet: Kaplan-Meier waits on F3 rows from F3 fills (median {f3w.round(2).tolist()} weeks), F1 rows "
        "labelled upper bound")
    # (4, 8) D6 on F1 and F3 with single events; theta on F3 from TH72 rows at RH
    O = res["outcomes"]
    th = O[O["exit"] == "FLIP"].assign(exit="TH72")
    th.loc[th["rule"] == "F1", "cost"] = "C-0"
    r6 = dict(res, outcomes=pd.concat([O, th], ignore_index=True))
    D6 = d6(r6, None, B=99)
    assert set(D6["rule"]) == {"F1", "F3_1"}, D6["rule"].unique()
    for rule in ("F1", "F3_1"):
        w = km_waits(b, "t_" + rule)
        for rg in RUNGS_P1:
            ww = w[w["rung"] == rg]
            ws = sbs.waiting_summary(ww["wait_d"].to_numpy(float), ww["event"].to_numpy(bool), 365.0)
            row = D6[(D6["rule"] == rule) & (D6["rung"] == rg)].iloc[0]
            assert math.isclose(row["W"], ws["W"]) and math.isclose(row["F"], ws["F"]), (rule, rg)
            tt = th[(th["rule"] == rule)].merge(res["fills"][["fill_id", "rung"]], on="fill_id")
            assert math.isclose(row["theta"], tt.loc[tt["rung"] == rg, "delta"].mean(), rel_tol=1e-12), (rule, rg)
            for k in EVENT_NAMES:
                assert f"mu_star_{k}" in row and f"W_{k}" in row
    # without the top month-block of rung 6 on F1: those fills treated as no fill -> W from km_waits by hand
    br = b[b["rung"] == 6.0]
    ft = br["t_F1"].to_numpy(np.int64)
    fl = ft >= 0
    _, tab = sbs.month_blocks(ts_min(ft[fl]))
    top = tab.sort_values(["n_fills", "block"], ascending=[False, True]).iloc[0]
    mm = ts_min(np.where(fl, ft, 0)).tz_localize(None).to_numpy().astype("datetime64[M]").astype(np.int64)
    drop = fl & np.isin(mm, list(top["periods"]))
    w2 = km_waits(br.assign(t_F1=np.where(drop, -1, ft)), "t_F1")
    ws2 = sbs.waiting_summary(w2["wait_d"].to_numpy(float), w2["event"].to_numpy(bool), 365.0)
    row = D6[(D6["rule"] == "F1") & (D6["rung"] == 6.0)].iloc[0]
    assert drop.any() and math.isclose(row["W_without_top_block"], ws2["W"]), (row["W_without_top_block"], ws2["W"])
    say(f"  D6: W, F, theta on F1 and F3 equal the hand computation; without the top month-block W "
        f"{row['W']:.3f} -> {row['W_without_top_block']:.3f}")
    # (8) T1 rows without each single event
    T1, _ = t1({"U-Q1": res}, B=99)
    assert list(T1["subset"]) == ["all"] + [EVENT_LABELS[k] for k in EVENT_NAMES], T1["subset"].tolist()
    kn = per_bench(res, "F1", "knife")
    mt = event_drop_masks(ts_min(res["fills"]["t_F1"].to_numpy(np.int64)), kn["time"])["without_top_block"]
    assert mt.any() and math.isclose(T1.iloc[3]["knife_fills"], kn["y"][~mt].mean(), rel_tol=1e-12)
    # (8) exploratory tables: F3 rows beside F1, BH within table per route, single events on every row
    X = explore_tables({"P1/U_Q1": res}, B=99)
    for nm in ("breadth", "weekday"):
        tb = X[nm]
        assert {"F1", "F3_1"} <= set(tb["rule"]) and (tb.loc[tb["rule"] == "F3_1", "label"] == LABEL_RH).all(), nm
        assert all(k in tb for k in EVENT_NAMES), nm
        for rule in ("F1", "F3_1"):
            g = tb[tb["rule"] == rule]
            assert np.allclose(g["q_bh"].to_numpy(float), sbs.bh(g["p"].to_numpy(float)), equal_nan=True), (nm, rule)
    wk = X["weekday"]
    d1_ = per_fill(res, "F1", "FLIP")
    r_ = wk[(wk["rule"] == "F1") & (wk["row"] == "H1 delta: weekday")].iloc[0]
    g = d1_[d1_["time"].dt.dayofweek < 5]
    g = add_clusters(g.drop(columns=CL_COLS))
    assert math.isclose(r_["without_top_block"], g.loc[g["mb"] != _top_block(g["mb"].to_numpy()), "y"].mean(),
                        rel_tol=1e-12)
    # event_coefs: the weekend-minus-weekday coefficient re-fitted without the top block = a separate lstsq
    dw = wk[(wk["rule"] == "F1") & (wk["row"] == "H1 delta: weekend minus weekday")].iloc[0]
    we = (d1_["time"].dt.dayofweek >= 5).to_numpy()
    keep = d1_["mb"].to_numpy() != _top_block(d1_["mb"].to_numpy())
    A_ = np.column_stack([np.ones(keep.sum()), we[keep].astype(float)])
    coef = np.linalg.lstsq(A_, d1_["y"].to_numpy(float)[keep], rcond=None)[0][1]
    assert math.isclose(dw["without_top_block"], coef, rel_tol=1e-9, abs_tol=1e-12), (dw["without_top_block"], coef)
    say("  T1 rows without each single event; exploratory tables with F3 rows beside F1 (BH per route) and single "
        "events on means and coefficients (lstsq oracle)")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "selftest":
        return 0 if selftest() else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
