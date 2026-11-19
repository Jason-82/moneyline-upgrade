"""
Controls of the stink-bid study (analysis_2026/STINKBID_PREREG.md, FROZEN 2026-11-18, commit 72ac2a4), §10.5
"Controls (run before any outcome is read; a failed control stops the study)": K1 known answer (K1a, K1b and the two
engine variants that must fail it, K1c, K1d), K2 positive control, K3 inference (with the power re-run of S18 and
D11's null distribution), K4 / K4b look-ahead, K5 fill audit, K6 capacity check, K7 ticks and sizes, K8 venue proxy;
with the fidelity critique's V1, V2, V5, V13, V15 and the statistics critique's S6, S7, S13, S18 that §10.5 adopts.
Contract: research_notes/Stink bids/build_spec.md, "stinkbid_controls.py". The simulations are run by the study's
modules (stinkbid_engine: fills, exits, twins, alerts, capacity and its K5 audit; stinkbid_levels: levels;
stinkbid_data: universes, ticks, capacity, venues, the Robinhood catalog; stinkbid_stats: every p-value, bound and
the K3 calibration); this module feeds them synthetic or perturbed inputs, holds the separately coded oracle,
compares, and writes the verdicts. None of those modules is edited. On real data it computes only counts, fill
calendars, coverage, capacity, venue flags, levels, timings and fill-audit status: no post-fill price, return, P&L,
a_f, Delta or knife rate is computed on real data (K3's outcomes are synthetic paths on the real fill CALENDAR; K4
compares exits only on synthetic worlds).

    python3 -m analysis_2026.stinkbid_controls run [--jobs 4] [--only K1,K3] [--quick]   # writes the outputs below
    python3 -m analysis_2026.stinkbid_controls selftest [--jobs 4]                      # small sizes, synthetic
    python3 -m analysis_2026.stinkbid_controls status                                   # summary.json's verdicts
  run exits 0 when all_passed is true, else 2. --quick (small sizes) and --only (a subset) never open the gate:
  summary.json then has quick / partial true, valid_gate false and all_passed false.

Outputs (analysis_2026/results_stinkbid/controls/)
  summary.json        {K1..K8: {passed, headline numbers, lines}, all_passed, controls_passed, quick, partial,
                      valid_gate, real_p1_rates, calendars (with their key), calendar_key, code, timings};
                      K1 -> K1c -> delta90 (= K1 -> K1c -> HOLD90 -> engine_delta_RH) is K1c's Delta90 regime
                      component ("what regime timing alone produces", printed with D-H2; coding choice 5)
  summary.txt         the same in words
  k1.json, k2.json    the known-answer and positive-control detail (engine, oracle, SE, wrong engines, exact
                      fill-by-fill diagnostics, K1b's fill-count match and tuning, K1c's report, K1d's haircut rates)
  k3_calibration.json stinkbid_stats.inference_calibration's dict (null statistics of every replication included):
                      the input of stinkbid_stats.calibrated_p / calibrated_bound / apply_calibration
  power.json          the power re-run (S18): MDEs by test and scenario, power curves (constant and concentrated
                      effects), NO EDGE reachability under the null
  d11_null.parquet    D11's null distribution: scenario, rep, total (H1's total Delta), mean, se, t, n
  k4.json, k4_comparisons.csv, k4_real_cuts.csv;  k5.json;  k6.json, k6_fills.csv;  k7.json,
  k7_reference_orders.csv;  k8.json, k8_events.csv
Working data (gitignored): data/stinkbid/controls/ (the real fill calendars of the counts-only runs with their key,
the K3 setup and its replication cache, and the stage caches a re-run reuses only under the same compiled code and
inputs: the K1 / K2 worlds and their reduction, K3, K4's perturbed runs and comparisons, K6).

Public API
  run(out=None, jobs=4, quick=False, only=None, n_reps=None, rebuild_calendars=False) -> summary dict   (the runner's
                                                                               controls stage)
  SynthSpec, SynthMarket (a picklable coin -> frames callable for the engine's injected World), K4Market, Pert
  oracle_market(market, exits, n_twins), OracleCoin, rule_m_oracle(t)          the separately coded oracle
  run_k1(...), run_k1_world(...), compare_k1(res, oracle), k1d_haircut(...), k1_specs(), tune_k1b(...),
  k1c_report(spec, K1c table, K1c0 table)                                      K1c's paired regime component
  real_calendars(jobs, force), calendar_key(), real_p1_rates(), prefetch_venues(bids)   counts-only real runs
  k3_setup(), k3_sim(scenario, rep, rng), run_k3(...), k3_power(calib)         K3 (sim_fn of inference_calibration)
  k4_synthetic(...), k4_compare(base, pert, cut, mode), draw_cuts(...), k4_real_universes / levels / fills
  k5_audit(records), k6_capacity(n), k7_ticks(), k7_levels(sources), k7_sheet_orders(levels, catalog),
  rh_orders(coin, L, Q, catalog_row), k7_check_orders(orders, catalog), k8_venue()

Coding choices the pre-registration leaves open (most literal reading; listed in the build report)
 1. The K1 market (§10.5: >= 40 coins over 6.9 years, Student-t(4) market and idiosyncratic shocks, volatility
    regimes): 40 coins on 1m bars 2019-11-01..2026-11-17 (placements 2020-01-06..2026-11-09 as the real program);
    minute shocks beta x market + idiosyncratic unit-variance t(4) (market sigma 3% a day, beta 0.8-1.3,
    idiosyncratic 2.5-4%), a shared daily log-AR(1) volatility regime (phi 0.99, innovation SD 0.05); prices are
    martingales (log drift -var/2 plus the jumps' compensator lambda E[1 - e^-J]); 0.15% zero-trade placeholder
    minutes (OHLC = the previous close), 0.02% missing minutes; prices on a fixed decimal tick of 1e-7 .. 1e-6 of the
    first price (so a long decline never reaches the tick floor); every coin a member of U-Q1 and U-B in every month.
 2. K1b's jumps: market-wide events (Poisson, 6 a year) at a minute's open (a gap), never in the first or last 10
    minutes of a UTC day (no artificial daily-open segment boundary); each event hits each coin with probability 0.35
    (crashes hit coins unevenly), with a log size of the coin's regime daily volatility x U(9.5, 12.5) x a lognormal
    factor (SD 0.1). "Tuned so P1's synthetic fill counts match §6.3's real counts within +-25%" is read as P1's F1
    fill rates per bid-week, per rung k = 6, 8, 10 (the synthetic world has 40 coins, the real one 92), against the
    real counts-only rates of the current engine (F1, U-Q1: 793 / 425 / 276 of 10,823 bid-weeks per rung); checked
    on the engine's own synthetic counts in run() and re-tuned over the event rate when outside. The design was chosen
    (counts and synthetic outcomes only) so that the jumps supply most deep fills, as in the real calendar (72-93%
    market-wide), and so that K2's planted effect is detectable: an earlier design with every coin hitting every
    event gave the same counts but only about 12 month-blocks of fills, and K2's t was 2.9-3.2 (a coin flip for a
    correct engine); with 35% participation K2's t is about 6.8 (oracle, 40 coins).
 3. The oracle (V1) is separate code: M2 levels from its own daily closes (sigma30 over 30 returns, ddof 1; floor
    to the tick in exact decimals, a level below P0 and above 0), F1 fills (first live minute of the life with low
    <= L - tau, in integer ticks), X-FLIP (R1/2 = ceil((L + P0) / 2) on the tick, sell live at M(fill) by its own
    rule M on pandas time zones, marketable at the go-live open, else high >= R1/2 + tau before the stop
    M(fill + 72 h), else the open of the first live minute at or after it), X-FLIP-bot (live from fill + 1, the same
    stop), X-HOLD-90, the delisting value (VWAP of the last full trading day x 0.70), B-ALERT under rule M, and 100
    twins per fill drawn with its own generator from its own eligible minutes. Pass rule (§10.5): the engine's mean
    r_f and mean Delta before costs (C-0) each within 2 SE of the oracle's, SE = the oracle's SD / sqrt(n) over the
    fills with a complete horizon and own (not pooled) twins (the iid SE: stricter than a clustered one), required for
    every K1 exit (X-FLIP, X-FLIP-bot, X-HOLD-90) in K1a and K1b. Fill-by-fill identity (bids, tick counts, fill
    minutes, exit kinds, minutes and returns, a_f, and every engine twin re-derived) is reported as a diagnostic.
 4. The two engine variants that must fail K1b are the engine's own cfg fill_price='close' / 'low' (F1 entries
    rebooked); "fail" = outside 2 SE of the oracle on mean r_f or mean Delta (X-FLIP).
 5. K1c: market regime drift +-0.2% a day (S13's example) in bull / bear regimes of geometric length (mean 182 days),
    crash intensity 3x higher in bear regimes at K1b's average intensity, the compensator at the average intensity
    (so bear stretches also carry their extra crashes as a negative drift). S13, which §10.5 adopts, asks for "no
    timing effect at the minute level", but K1c's crashes are K1b's non-reverting gaps, whose gap-through cost inside
    the fill minute is most of K1c's own Delta (review finding 1). So what is reported as "what regime timing alone
    produces" is K1c's regime component: per fill, K1c's Delta minus the Delta of the same bid's fill in K1c0, its
    paired null (the same seed, regime states, crash schedule and shocks, with no regime drift and each regime's
    crashes compensated at its own intensity, so every regime is a martingale and K1c - K1c0 is the deterministic
    regime drift alone), over the fills both worlds share (complete horizon, own twins), with a month-block CR1 SE
    (k1c_report). K1 -> K1c -> delta90 = HOLD90 -> engine_delta_RH (X-HOLD-90, C-RH) is the number printed with D-H2;
    the oracle's paired value is beside each; K1c's total Delta (clustered SE), K1c0's Delta (the minute-level cost
    alone) and the fill minutes' gap-through shares are labelled diagnostics. No pass rule in the prereg, so K1c does
    not gate.
 6. K1d: 24 of 48 coins stop trading at uniform random minutes between 40% of the span (2022-08) and 50 days before
    the end (each keeps >= 182 eligible twin days). "Fills and twins must take the haircut at equal rates": (a) every
    position, fill or engine twin, whose X-HOLD-90 horizon lies after its coin's last trade is closed at the §4.1 value
    and no other is; (b) the engine's twins are closed there at the rate their eligibility implies: their count of
    delisted twins against the oracle's independent draws for the same fills within 2 SE (binomial per fill); the raw
    shares of fills and twins closed at the value are reported (the +-182-day exclusion makes them differ by design).
 7. K2: K1b's market (same seed) with each jump split into a permanent half and a transient half reverting with a
    30-minute half-life (a deterministic recovery after the jump minute). Pass: H1's statistic (P1, F1, X-FLIP, C-RH,
    mean Delta, month-block CR1 t from stinkbid_stats.test_mean) > 0 with t >= 3 under rule M and under X-FLIP-bot,
    and the engine within 2 SE of the oracle for both.
 8. K3 (hourly paths, build spec): the real calendars are P1's F1 fills on U-Q1 (H1, H2R) and the H4 program's F1
    fills (real chart levels and their placebos, counts only). Path model: the draft's power model (critique S7):
    market sigma 3%, beta 1.1, idiosyncratic 3% (high: 4.5%), log-AR(1) volatility (phi 0.98, SD 0.09), a
    crash-time multiplier (base 2x for 3 days, high 3x for 7 days) after "crash days" = UTC days with P1 fills in >= 3
    distinct U-Q1 coins (the draft's U-B-based crash days need U-B 1m data); hetero = base plus a mean-zero t(3)
    effect of SD 3% per episode on the tested contrast (H1 Delta, H2R a_f, H4 the real level's Delta). A fill enters
    at its fill hour's close, a twin at an hour's open (100 twins per fill, the coin's eligible hours: U-Q1 member
    months, outside +-182 days, a complete window; pooled over all coins below 182 days); sells go live at the first
    hour boundary at or after rule M; C-RH on both sides. K3 "passes" when every scenario has >= 2,000 replications
    of every test; a test whose rates fail the 1.5x rule switches to the simulation-calibrated p and bound
    (stinkbid_stats.apply_calibration; the rule per test is in summary.json). Power: effects added to the cached null
    values of the first 300 replications per scenario (constant effects; H1 / H2R edges in the 10 and 3 largest
    episodes; H4 on M4 alone and on every method), rejection at 0.05/3 (Holm's first step) and 0.05, each test under
    the rule K3 assigns it: a calibrated test's rejections use its simulation-calibrated p, its NO EDGE rates the
    widened bound, and its MDE the calibrated critical statistic at 0.05/3 (the largest over the scenarios of the
    null statistic that calibrated_p must exceed); the nominal rates and MDE are kept beside it (review finding 4).
 9. K4: cut minutes are never on an hour boundary (minute != 0); "within 24 h of a placement" = within 24 h after a
    Monday 03:30 placement; "fill-day crash hours" = the hour holding a P1 F1 fill. Synthetic (every program, life,
    level method, rule F1-F5, exits, alerts, twins, capacity): the K4 world (3 coins, 2021-03..2022-10, index and
    perpetual minutes, M7's 5-minute open interest and 1h bars, M3 / M8's pooled panel with 10 daily-only pairs),
    all series derived from the perturbed minutes; 50 cuts x (scale, delete, 3-day gap). Real data, no outcome:
    universes (stinkbid_data's _ranks / _universes on the perturbed daily panel), every per-coin level variant
    (M3 / M8's pooled tables only on the synthetic panel), and P1, P1-90, P1-1, P1-lazy bids, F1 / F2 fills and
    capacity on the real 1m bars of 24 cuts, 6 of each kind (placement, crash hour, weekend, uniform; _pick_cuts,
    review finding 7). Compared: bids placed before the cut (and placements without a bid),
    fill minutes and fill attributes stamped before it, min(life end, cut), the capacity accumulated through each
    minute before it, exits and B-ALERT buys stamped before it, and twins with the same entry in both runs. Not
    decisions stamped before the cut: the market-wide flag (it reads the whole fill day), the capacity summaries over
    a life, and, under K4b, a delisting value from the cut on. Each perturbation must also change some later decision.
10. K5: every audit record of the engine runs made here (synthetic K1 / K2 worlds, K4's base and perturbed worlds,
    and K4's real-data fill runs) and of the real counts-only calendars (P1 under F1-F5, H4), plus an independent
    re-audit of every real P1 F1 fill from the raw 1m bars (live minute inside the life, low <= L - tau, the first
    such minute; gap-through fills listed).
11. K6: 200 random real P1 F1 fills (seeded); C1 and aggTrades on the same causal windows (engine.capacity with
    mode 'agg'); the prereg sets no threshold, so K6 passes when >= 90% of the sample is compared (archive gaps are
    recorded) and reports the ratios.
12. K7: (a) every level is n x tau in decimals with L - tau = (n - 1) tau, on the real calendars (P1, H4 with its
    placebos), the real level rows of K4's cut coins (every per-coin method), the synthetic K1 / K2 worlds and K4's
    synthetic runs of every program; every level method of the engine's programs must be checked by some source
    (M3 and M8, pooled, only on synthetic levels; review finding 5); (b) reference sheet orders: the M2 rungs of
    every U-C coin at the last Monday placement of the data (2026-11-16 03:30) floored to Robinhood's tick
    (stinkbid_levels.rh_round, delta recomputed), Q = $1k, $10k, $100k, ordered by the sheet's own rule
    (stinkbid_sheet.rh_orders: quantity Q / L floored to the increment, no order below the minimum size, above the
    maximum n = ceil(q / max) near-equal orders) and checked by k7_check_orders; rh_orders is this module's coding of
    the same rule, compared with it (review finding 3: a greedy split could leave a piece below the minimum).
13. K8: per real P1 F1 fill, also filled under F3 (s = 1%, 3%), F3d (1%), F5 and F3 with the index in USD
    (F3usd), F3-unverifiable and index-outage flags; the share removed overall, by rung and by episode.
14. The real calendars (P1 and H4, counts only) are stored with calendar_key: the sources of the code that builds
    them (the engine and the modules it imports), this module's calendar functions and configurations, and the
    stamps (path, size, modification time) of every data input under data/stinkbid/; run() rebuilds them when the
    key changed (or with rebuild_calendars / --rebuild-calendars), and the K3 and K6 caches are keyed by it (review
    finding 2).
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as _dt
import hashlib
import json
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, replace
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
from zoneinfo import ZoneInfo

import numba as nb
import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import stinkbid_data as sbd  # noqa: E402
from analysis_2026 import stinkbid_engine as sbe  # noqa: E402
from analysis_2026 import stinkbid_levels as sbl  # noqa: E402
from analysis_2026 import stinkbid_stats as sbs  # noqa: E402

# ============================================================================ constants (prereg section in brackets)
OUT_DIR = ROOT / "analysis_2026" / "results_stinkbid" / "controls"
WORK = sbd.OUT / "controls"                       # gitignored working data (calendars, K3 cache)
NY = ZoneInfo("America/New_York")
UTC = _dt.timezone.utc
MIN_NS = 60_000_000_000
DAY_M = 1440
SEED = 20261118
END_DAY = "2026-11-17"                            # §4: the data end
SYN_START = "2019-11-01"                          # synthetic 1m paths: warm-up before the first placement
K1_COINS = 40                                     # §10.5 K1: at least 40 coins over 6.9 years
C_RH = 0.0095                                     # §9
E_TESTS = dict(sbs.E)                             # H1 3.75%, H2R 2%, H4 1% (§10.3)
K1_SE_MULT = 2.0                                  # §10.5 K1, K2: within 2 SE of the oracle
K1B_TOL = 0.25                                    # §10.5 K1b: fill counts within +-25% of the real counts
K2_T = 3.0                                        # §10.5 K2: t >= 3
K3_REPS = 5000                                    # §10.5 K3: >= 2,000 null replications per scenario; 5,000 by prereg Addendum 1 (A1.5)
K3_SCENARIOS = ("base", "high", "hetero")
K4_CUTS = 50                                      # §10.5 K4
K6_FILLS = 200                                    # §10.5 K6
PLACE_HM = (3, 30)                                # §6.1


def _say(msg: str) -> None:
    print(msg, flush=True)


def _js(x):
    """JSON-ready conversion (numpy scalars and arrays, NaN -> None, timestamps -> ISO strings)."""
    if isinstance(x, dict):
        return {str(k): _js(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_js(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_js(v) for v in x.tolist()]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, (pd.Timestamp, _dt.datetime)):
        return str(x)
    if isinstance(x, pd.DataFrame):
        return _js(x.to_dict(orient="records"))
    return x


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(_js(obj), indent=1))
    os.replace(tmp, path)


def _tmin(x) -> int | np.ndarray:
    """Minutes since 1970-01-01 UTC (naive input = UTC)."""
    if isinstance(x, (str, pd.Timestamp, _dt.datetime, np.datetime64)):
        t = pd.Timestamp(x)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        return int(t.value // MIN_NS)
    idx = pd.DatetimeIndex(x)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return idx.tz_localize(None).as_unit("ns").asi8 // MIN_NS


def _ts(m) -> pd.Timestamp:
    return pd.Timestamp(int(m) * MIN_NS, tz="UTC")


# ============================================================================ rule M, coded separately (§8)
def rule_m_oracle(t) -> np.ndarray:
    """Manual-action rule M (§8), written for the oracle without the engine: an event at UTC minute t is acted on at
    t + 60 if t's New York wall-clock time is 07:00-22:59, else at the next 07:00 New York time. Vectorised with
    pandas time zones (America/New_York from zoneinfo)."""
    t = np.atleast_1d(np.asarray(t, np.int64))
    if not len(t):
        return t.copy()
    ut = pd.DatetimeIndex(t * MIN_NS, tz="UTC")
    loc = ut.tz_convert(NY)
    mins = (loc.hour * 60 + loc.minute).to_numpy()
    day = loc.tz_localize(None).normalize()
    in_day = (mins >= 420) & (mins <= 1379)
    nxt = np.where(mins < 420, day, day + pd.Timedelta(days=1))
    nxt = pd.DatetimeIndex(nxt) + pd.Timedelta(hours=7)
    nxt_utc = nxt.tz_localize(NY, ambiguous="raise", nonexistent="raise").tz_convert("UTC")
    nxt_m = nxt_utc.tz_localize(None).as_unit("ns").asi8 // MIN_NS
    return np.where(in_day, t + 60, nxt_m).astype(np.int64)


def _rule_m_py(tm: int) -> int:
    """Rule M one minute at a time with plain datetime (a third coding; used to check rule_m_oracle)."""
    d = _dt.datetime.fromtimestamp(int(tm) * 60, tz=UTC).astimezone(NY)
    if 7 * 60 <= d.hour * 60 + d.minute <= 22 * 60 + 59:
        return int(tm) + 60
    day = d.date() if d.hour < 7 else d.date() + _dt.timedelta(days=1)
    loc = _dt.datetime(day.year, day.month, day.day, 7, 0, tzinfo=NY)
    return int(loc.astimezone(UTC).timestamp()) // 60


# ============================================================================ the synthetic 1m market (K1, K2, K4)
@dataclass(frozen=True)
class SynthSpec:
    """A synthetic 1-minute market (§10.5 K1: >= 40 coins over 6.9 years, Student-t(4) market and idiosyncratic
    shocks, volatility regimes). Prices are martingales: the log drift is -var/2 per minute plus a compensator for the
    jumps (lambda E[1 - e^J] at the average intensity), except K1c's regime drift and K2's reverting halves, which
    are the effects those controls inject (with K1c's 3x bear intensity, the average compensator also leaves bear
    regimes with a negative and bull regimes with a positive drift; comp_regime, K1c's paired null K1c0, compensates
    each regime at its own intensity instead). Every coin is a member of U_Q1 and U_B in every month it trades."""
    name: str = "K1b"
    n_coins: int = K1_COINS
    start: str = SYN_START
    end: str = END_DAY                     # the last day (inclusive): the data end of the injected world
    seed: int = SEED
    sigma_m: float = 0.030                 # market daily volatility (critique power model)
    beta_lo: float = 0.8
    beta_hi: float = 1.3
    sig_e_lo: float = 0.025                # idiosyncratic daily volatility range
    sig_e_hi: float = 0.040
    vol_phi: float = 0.99                  # log-AR(1) volatility regime, daily (stationary SD of log vol 0.35)
    vol_sd: float = 0.05
    vol_iid: float = 0.0                   # iid daily log-volatility shock (a scale mixture: fat-tailed days)
    jump_rate: float = 0.0                 # market-wide jump events per year (K1b, K2; K1a: 0)
    jump_kind: str = "sig"                 # "sig": log size = the coin's regime daily vol x U(jump_lo, jump_hi)
    jump_lo: float = 9.5                   #   x a lognormal factor (each coin draws its own uniform per event);
    jump_hi: float = 12.5                  # "exp": exponential log size of mean jump_mean x beta x lognormal
    jump_mean: float = 0.0
    jump_part: float = 0.35                # share of coins a market-wide jump hits (each coin drawn per event)
    jump_mix: float = 0.0                  # "sig": share of jumps drawn from U(jump_lo_s, jump_hi_s) instead
    jump_lo_s: float = 5.0
    jump_hi_s: float = 9.0
    jump_disp: float = 0.10                # lognormal dispersion of each coin's jump around the event's size
    jump_cap: float = 2.5                  # cap on a coin's log jump
    transient: float = 0.0                 # K2: share of each jump that reverts
    half_life_m: float = 30.0              # K2: 30-minute half-life
    regime_drift: float = 0.0              # K1c: +- log drift a day in bull / bear regimes
    regime_mean_days: float = 182.0        # K1c: 6-month regimes (geometric durations)
    bear_mult: float = 1.0                 # K1c: crash intensity in bear regimes / bull regimes (3)
    comp_regime: bool = False              # K1c0 (K1c's paired null): the jumps' compensator follows each regime's own
    #                                        crash intensity, so every regime is a martingale (default: the average)
    delist_n: int = 0                      # K1d: coins that stop trading at a random minute
    delist_from: str = "2022-07-01"
    delist_to: str = "2026-09-30"
    zero_frac: float = 0.0015              # zero-trade placeholder minutes (OHLC = previous close)
    missing_frac: float = 0.0002           # missing minutes
    with_seg: bool = True                  # give `seg` (no boundaries by construction); K4: derived by the engine
    index: bool = False                    # index_m1 / perp_m1 series (K4)
    m7: bool = False                       # metrics, mark1h, perp1h (K4; M7 from 2021-12)
    panel_extra: int = 0                   # extra daily-only pairs for M3 / M8's pooled tables (K4)

    def key(self) -> str:
        return hashlib.sha1(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]


_GLOBAL: dict = {}


def _t4(rng, n) -> np.ndarray:
    """Unit-variance Student-t(4) draws."""
    return rng.standard_t(4, size=n) / math.sqrt(2.0)


def _market_globals(spec: SynthSpec) -> dict:
    """Shared components of a synthetic market (cached per process): minute grid, daily volatility regime, regime
    states (K1c), market shocks, jump events and their market sizes."""
    k = spec.key()
    if k in _GLOBAL:
        return _GLOBAL[k]
    rng = np.random.default_rng([spec.seed, 1])
    t0 = _tmin(spec.start)
    t1 = _tmin(pd.Timestamp(spec.end) + pd.Timedelta(days=1))
    N = t1 - t0
    D = N // DAY_M
    # log-AR(1) volatility regime (critique power model): E[v^2] = 1
    x = np.empty(D)
    e = rng.normal(0.0, spec.vol_sd, D)
    sd = spec.vol_sd / math.sqrt(1 - spec.vol_phi ** 2)
    x[0] = rng.normal(0.0, sd)
    for i in range(1, D):
        x[i] = spec.vol_phi * x[i - 1] + e[i]
    eta = rng.normal(0.0, spec.vol_iid, D) if spec.vol_iid > 0 else np.zeros(D)
    v_day = np.exp(x + eta - sd ** 2 - spec.vol_iid ** 2)            # E[v^2] = 1
    v_reg = np.exp(x - sd ** 2)                                      # the regime alone: E[v_day^2 | regime] = v_reg^2
    # K1c regimes: alternating bull (+1) / bear (-1) with geometric durations of mean regime_mean_days
    state = np.ones(D, np.int8)
    if spec.regime_drift != 0.0 or spec.bear_mult != 1.0:
        p = 1.0 / spec.regime_mean_days
        s = 1 if rng.random() < 0.5 else -1
        for i in range(D):
            state[i] = s
            if rng.random() < p:
                s = -s
    bear_share = float(np.mean(state < 0))
    # jump events: Poisson per day at the regime's intensity (average intensity = jump_rate)
    ev_t, ev_m = np.zeros(0, np.int64), np.zeros(0)
    if spec.jump_rate > 0:
        lam_bull = spec.jump_rate / ((1 - bear_share) + spec.bear_mult * bear_share)
        lam = np.where(state < 0, spec.bear_mult * lam_bull, lam_bull) / 365.0
        n_ev = rng.poisson(lam)
        days = np.repeat(np.arange(D), n_ev)
        mins = rng.integers(10, DAY_M - 10, len(days))      # never in the first / last 10 minutes of a UTC day
        ev_t = np.sort(t0 + days * DAY_M + mins).astype(np.int64)          # absolute UTC minutes
        ev_m = (rng.exponential(spec.jump_mean, len(ev_t)) if spec.jump_kind == "exp" else
                rng.uniform(spec.jump_lo, spec.jump_hi, len(ev_t)))
    eps_m = _t4(rng, N)
    g = dict(t0=t0, N=N, D=D, v_day=v_day, v_reg=v_reg, state=state, bear_share=bear_share, ev_t=ev_t, ev_m=ev_m, eps_m=eps_m)
    if len(_GLOBAL) > 2:
        _GLOBAL.clear()
    _GLOBAL[k] = g
    return g


def _coin_params(spec: SynthSpec, i: int) -> dict:
    rng = np.random.default_rng([spec.seed, 2, i])
    beta = rng.uniform(spec.beta_lo, spec.beta_hi)
    sig_e = rng.uniform(spec.sig_e_lo, spec.sig_e_hi)
    p0 = float(np.exp(rng.uniform(np.log(1.0), np.log(200.0))))
    dec = 7 - int(math.floor(math.log10(p0)))               # relative tick 1e-7 .. 1e-6 (room for long declines)
    tick = "1" if dec <= 0 else "0." + "0" * (dec - 1) + "1"
    qv = float(np.exp(rng.uniform(np.log(2e4), np.log(4e5))))
    # jump loadings: coin jump = market size x beta x lognormal(disp), capped
    lz = rng.normal(-0.5 * spec.jump_disp ** 2, spec.jump_disp, 200_000)
    # compensator E[1 - e^{-J}] by Monte Carlo over the market size distribution (exponential, mean jump_mean)
    comp = 0.0
    if spec.jump_rate > 0 and spec.jump_kind == "exp" and spec.jump_mean > 0:
        mc = np.random.default_rng([spec.seed, 3, i])
        mm = mc.exponential(spec.jump_mean, 200_000)
        J = np.minimum(mm * beta * np.exp(lz), spec.jump_cap)
        comp = float(np.mean(1.0 - np.exp(-J)))
    delist = -1
    if i < spec.delist_n:
        a, b = _tmin(spec.delist_from), _tmin(spec.delist_to)
        delist = int(rng.integers(a, b))
    return dict(beta=beta, sig_e=sig_e, p0=p0, tick=tick, qv=qv, comp=comp, delist=delist)


def _round_tick(x: np.ndarray, tick: str) -> np.ndarray:
    """Integer tick counts of prices (round half up), at least 1."""
    tk = float(tick)
    return np.maximum(np.floor(x / tk + 0.5), 1.0).astype(np.int64)


def _tick_float(n: np.ndarray, tick: str) -> np.ndarray:
    """The double nearest the decimal n x tick (as a parsed archive price)."""
    tk = float(tick)
    nd = max(0, -int(round(math.log10(tk))))
    return np.round(n.astype(float) * tk, nd)


class SynthMarket:
    """Picklable coin -> frames generator of a SynthSpec market (the engine's World 'coins' callable). Each coin is
    regenerated deterministically from (seed, coin index); the shared market components are cached per process."""

    def __init__(self, spec: SynthSpec):
        self.spec = spec
        self.coins = [f"S{i:02d}" for i in range(spec.n_coins)]
        self._fcache = {}

    def __getstate__(self):
        d = dict(self.__dict__)
        d["_fcache"] = {}                                            # never pickle generated frames
        return d

    def params(self, coin: str) -> dict:
        return _coin_params(self.spec, self.coins.index(coin))

    # ---- the minute path of one coin
    def path(self, coin: str) -> dict:
        """Arrays of one coin over the whole grid: t (minute), open/high/low/close as tick counts and floats, live,
        quote volume, taker buy quote, plus the jump minutes and the coin's parameters. Missing minutes and a
        delisting are applied by frames()."""
        spec = self.spec
        g = _market_globals(spec)
        i = self.coins.index(coin)
        P = _coin_params(spec, i)
        rng = np.random.default_rng([spec.seed, 4, i])
        N = g["N"]
        day = np.arange(N) // DAY_M
        v = g["v_day"][day]
        s1 = math.sqrt(P["beta"] ** 2 * spec.sigma_m ** 2 + P["sig_e"] ** 2) / math.sqrt(DAY_M)
        var = (s1 * v) ** 2                                          # the minute's diffusion variance
        r = (P["beta"] * spec.sigma_m / math.sqrt(DAY_M)) * v * g["eps_m"]
        r += (P["sig_e"] / math.sqrt(DAY_M)) * v * _t4(rng, N)
        r -= 0.5 * var
        sd_day = s1 * math.sqrt(DAY_M) * g["v_reg"]                  # the coin's regime daily volatility (what
        #                                                              sigma30 tracks; the iid daily shock excluded)
        lam_rel = None
        if spec.comp_regime:
            # K1c0: the compensator at each regime's own crash intensity (relative to the average one), so that every
            # regime is a martingale; by default it is at the average intensity
            lam_rel = np.where(g["state"] < 0, spec.bear_mult, 1.0) / ((1.0 - g["bear_share"]) +
                                                                      spec.bear_mult * g["bear_share"])
        if spec.jump_rate > 0 and spec.jump_kind == "sig":
            # compensator E[1 - e^-J] per day (J = sd_day x U x lognormal), Monte Carlo on a fixed sample
            mc = np.random.default_rng([spec.seed, 3, i])
            uu = mc.uniform(spec.jump_lo, spec.jump_hi, 4000)
            if spec.jump_mix > 0:
                uu = np.where(mc.random(4000) < spec.jump_mix, mc.uniform(spec.jump_lo_s, spec.jump_hi_s, 4000), uu)
            uu = uu * np.exp(mc.normal(-0.5 * spec.jump_disp ** 2, spec.jump_disp, 4000))
            comp_d = spec.jump_part * np.array([np.mean(1.0 - np.exp(-np.minimum(sv * uu, spec.jump_cap)))
                                                for sv in sd_day])
            if lam_rel is not None:
                comp_d = comp_d * lam_rel
            r += (comp_d * spec.jump_rate / (365.0 * DAY_M))[np.arange(N) // DAY_M]
        elif lam_rel is not None:
            r += (P["comp"] * spec.jump_rate / (365.0 * DAY_M)) * lam_rel[day]
        else:
            r += P["comp"] * spec.jump_rate / (365.0 * DAY_M)        # jump compensator (martingale)
        if spec.regime_drift:
            r += np.where(g["state"][day] < 0, -spec.regime_drift, spec.regime_drift) / DAY_M
        del day
        jump = np.zeros(N)
        ev = g["ev_t"] - g["t0"]
        if len(ev):
            lz = rng.normal(-0.5 * spec.jump_disp ** 2, spec.jump_disp, len(ev))
            if spec.jump_kind == "sig":
                # every coin jumps at the event's minute; its size in regime daily sigmas is its own uniform draw
                u = rng.uniform(spec.jump_lo, spec.jump_hi, len(ev))
                if spec.jump_mix > 0:
                    small = rng.random(len(ev)) < spec.jump_mix
                    u = np.where(small, rng.uniform(spec.jump_lo_s, spec.jump_hi_s, len(ev)), u)
                J = np.minimum(u * sd_day[ev // DAY_M] * np.exp(lz), spec.jump_cap)
                if spec.jump_part < 1.0:
                    J = np.where(rng.random(len(ev)) < spec.jump_part, J, 0.0)
            else:
                J = np.minimum(g["ev_m"] * P["beta"] * np.exp(lz), spec.jump_cap)
            np.add.at(jump, ev, -J)
            if spec.transient > 0:                                   # K2: the reverting share, half-life 30 min
                k = np.arange(0, int(spec.half_life_m * 24))
                dec = 2.0 ** (-k / spec.half_life_m) - 2.0 ** (-(k + 1) / spec.half_life_m)
                for e_, j_ in zip(ev, J):
                    a = e_ + k
                    ok = a < N
                    r[a[ok]] += spec.transient * j_ * dec[ok]
        close_log = math.log(P["p0"]) + np.cumsum(jump + r)
        del r
        open_log = np.r_[math.log(P["p0"]), close_log[:-1]] + jump
        tk = P["tick"]
        o = _round_tick(np.exp(open_log), tk)
        c = _round_tick(np.exp(close_log), tk)
        d = open_log - close_log
        d *= d
        s = open_log + close_log
        w = np.sqrt(d - 2.0 * var * np.log(rng.random(N)))
        h = np.maximum(_round_tick(np.exp(0.5 * (s + w)), tk), np.maximum(o, c))
        w = np.sqrt(d - 2.0 * var * np.log(rng.random(N)))
        lo = np.minimum(_round_tick(np.exp(0.5 * (s - w)), tk), np.minimum(o, c))
        del d, s, w, open_log, close_log, var
        live = rng.random(N) >= spec.zero_frac
        live[0] = True
        if not live.all():                                           # placeholders: OHLC = the previous close
            idx = np.where(live, np.arange(N), 0)
            np.maximum.accumulate(idx, out=idx)
            prev = np.r_[0, idx[:-1]]
            z = ~live
            pc = c[prev[z]]
            # the previous close is the close of the minute before (which may itself be a placeholder: its close is
            # the last live close), so every placeholder carries the last live close
            o[z] = h[z] = lo[z] = c[z] = pc
        qv = P["qv"] * v * np.exp(rng.normal(-0.125, 0.5, N))
        tb = qv * rng.uniform(0.3, 0.7, N)
        trades = (1 + np.floor(30 * v * rng.random(N))).astype(np.int32)
        qv[~live] = 0.0
        tb[~live] = 0.0
        trades[~live] = 0
        keep = rng.random(N) >= spec.missing_frac
        keep[0] = True
        t = g["t0"] + np.arange(N, dtype=np.int64)
        if P["delist"] >= 0:
            keep &= t < P["delist"]
        return dict(t=t, o=o, h=h, l=lo, c=c, live=live, qv=qv, tb=tb, trades=trades, keep=keep, tick=tk,
                    jump_min=g["t0"] + ev if len(ev) else np.zeros(0, np.int64), params=P)

    def frames(self, coin: str, perturb=None) -> dict:
        """The engine's injected frames of one coin (World docstring): m1 (and index_m1 / perp_m1 / levels extras when
        the spec asks for them), tick. perturb(coin, frames) -> frames may change them (K4)."""
        A = self.path(coin)
        k = A["keep"]
        tk = A["tick"]
        o, h, lo, c = (_tick_float(A[x][k], tk) for x in ("o", "h", "l", "c"))
        qv = A["qv"][k]
        m1 = pd.DataFrame({"open_time": pd.DatetimeIndex(A["t"][k] * MIN_NS, tz="UTC"), "open": o, "high": h,
                           "low": lo, "close": c, "volume": np.where(c > 0, qv / c, 0.0), "quote_volume": qv,
                           "trades": A["trades"][k], "taker_buy_quote": A["tb"][k]})
        if self.spec.with_seg:
            m1["seg"] = np.zeros(len(m1), np.int32)
        fr = {"m1": m1, "tick": tk}
        if self.spec.index or self.spec.m7:
            rng = np.random.default_rng([self.spec.seed, 5, self.coins.index(coin)])
            n = len(m1)
            if self.spec.index:
                eps = np.exp(rng.normal(0.0, 4e-4, (n, 4)))
                io, ih, il, ic = (m1[x].to_numpy() * eps[:, j] for j, x in enumerate(("open", "high", "low", "close")))
                ih = np.maximum.reduce([ih, io, ic])
                il = np.minimum.reduce([il, io, ic])
                upd = np.where(m1.trades.to_numpy() > 0, 60, 0).astype(np.int64)
                out = rng.random(n) < 0.0005                         # index outage minutes (< 30 updates)
                upd[out] = 12
                fr["index_m1"] = pd.DataFrame({"open_time": m1.open_time, "open": np.round(io, 8),
                                               "high": np.round(ih, 8), "low": np.round(il, 8),
                                               "close": np.round(ic, 8), "updates": upd})
            basis = np.exp(rng.normal(0.0, 6e-4, n))
            perp = m1[["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades",
                       "taker_buy_quote"]].copy()
            for x in ("open", "high", "low", "close"):
                perp[x] = np.round(perp[x].to_numpy() * basis, 8)
            perp["high"] = perp[["open", "high", "close"]].max(axis=1)
            perp["low"] = perp[["open", "low", "close"]].min(axis=1)
            if self.spec.index:
                fr["perp_m1"] = perp
            if self.spec.m7:
                fr["levels"] = _m7_frames(perp, rng, A["jump_min"])
        if perturb is not None:
            fr = perturb(coin, fr)
        return fr

    def __call__(self, coin: str) -> dict:
        """The World's frames callable: generated once per coin and instance (the programs of one world share them;
        the engine reads them without changing them)."""
        if coin not in self.coins:
            raise KeyError(f"no injected frames for {coin}")
        if coin not in self._fcache:
            if len(self._fcache) >= 4:
                self._fcache.pop(next(iter(self._fcache)))
            self._fcache[coin] = self.frames(coin)
        return self._fcache[coin]          # the same dict: the World's derived tables (daily bars, ids) persist

    # ---- universe and world
    def member_months(self, coin: str) -> list:
        P = self.params(coin)
        last = pd.Timestamp(self.spec.end) if P["delist"] < 0 else _ts(P["delist"] - 1).tz_localize(None)
        first = max(pd.Timestamp("2020-01-01"), pd.Timestamp(self.spec.start) + pd.Timedelta(days=40))
        return list(pd.period_range(first, last, freq="M").strftime("%Y-%m"))

    def universe(self) -> pd.DataFrame:
        rows = [dict(month=m, coin=c, U_Q1=True, U_B=True) for c in self.coins for m in self.member_months(c)]
        return pd.DataFrame(rows)

    def world(self) -> dict:
        return {"universe": self.universe(), "coins": self, "end": self.spec.end, "tbill": 0.0}


def _m7_frames(perp: pd.DataFrame, rng, jump_min) -> dict:
    """M7's inputs from a perpetual minute series: 5-minute open interest (oi in coins; drops at jump minutes, as
    liquidations), 1h mark-price lows and 1h perpetual volumes (stinkbid_levels' injected 'metrics', 'mark1h',
    'perp1h')."""
    t = _tmin(perp.open_time)
    h = t // 60
    hu, st = np.unique(h, return_index=True)
    lo = np.minimum.reduceat(perp.low.to_numpy(float), st)
    vol = np.add.reduceat(perp.volume.to_numpy(float), st)
    qv = np.add.reduceat(perp.quote_volume.to_numpy(float), st)
    ot = pd.DatetimeIndex(hu * 60 * MIN_NS, tz="UTC")
    mark = pd.DataFrame({"open_time": ot, "low": lo * np.exp(rng.normal(0, 2e-4, len(lo)))})
    p1h = pd.DataFrame({"open_time": ot, "volume": vol, "quote_volume": qv})
    t5 = np.arange((t[0] // 5 + 1) * 5, t[-1] + 1, 5)
    n5 = len(t5)
    lo_oi = np.cumsum(rng.normal(0.0, 0.004, n5))
    jm = np.asarray(jump_min, np.int64)
    if len(jm):
        k = np.searchsorted(t5, jm)
        drops = np.zeros(n5)
        ok = k < n5
        np.add.at(drops, k[ok], rng.uniform(0.05, 0.25, int(ok.sum())))
        lo_oi -= np.cumsum(drops)
    oi = 1e6 * np.exp(lo_oi)
    met = pd.DataFrame({"create_time": pd.DatetimeIndex(t5 * MIN_NS, tz="UTC"), "oi": oi})
    return {"metrics": met, "mark1h": mark, "perp1h": p1h}


# ============================================================================ the oracle (§10.5 K1, V1): separate code
# Everything below reads only the injected paths (SynthMarket.path) and re-derives levels, fills, exits, alert buys
# and twins with its own code: no engine, levels or data function is called. Prices are integer tick counts, so
# "low <= L - tau", "high >= R + tau" and the half-retrace ceiling are exact integer comparisons.
EK = {0: "target", 1: "marketable", 2: "stop", 3: "delist", 4: "censored"}


@nb.njit(cache=True)
def _o_next_live(live):
    n = live.size
    out = np.empty(n + 1, np.int64)
    out[n] = n
    for i in range(n - 1, -1, -1):
        out[i] = i if live[i] else out[i + 1]
    return out


@nb.njit(cache=True)
def _o_fills(t, lo_n, live, a_min, e_min, thr_n):
    """First bar with a_min <= t < e_min, live, low <= thr (ticks); -1 if none."""
    out = np.full(a_min.size, -1, np.int64)
    for b in range(a_min.size):
        i = np.searchsorted(t, a_min[b])
        while i < t.size and t[i] < e_min[b]:
            if live[i] and lo_n[i] <= thr_n[b]:
                out[b] = i
                break
            i += 1
    return out


@nb.njit(cache=True)
def _o_exits(t, o, h, nxt, g, S, T, up, last_live_t, delisted, end_min):
    """Exit of each position (§8 X-FLIP / X-HOLD): the sell goes live at minute g; at the first live minute at or
    after g, a price at or above the target T sells at that open (marketable; a hold has T = inf); before the stop S,
    the first live minute with high >= up sells at T; else the open of the first live minute at or after S. A
    position still open when trading stops (delisted) is valued later at the delisting value (kind 3); one whose
    horizon passes the data end is censored (kind 4). Returns kind, bar index, price."""
    n = g.size
    kind = np.full(n, 4, np.int64)
    idx = np.full(n, -1, np.int64)
    px = np.full(n, np.nan)
    nb_ = t.size
    for p in range(n):
        if S[p] > end_min and not delisted:
            continue
        i = nxt[np.searchsorted(t, g[p])]
        if i >= nb_:
            if delisted:
                kind[p] = 3
            continue
        if t[i] >= S[p]:
            kind[p], idx[p], px[p] = 2, i, o[i]
            continue
        if o[i] >= T[p]:
            kind[p], idx[p], px[p] = 1, i, o[i]
            continue
        j = i
        hit = -1
        if not np.isfinite(up[p]):
            j = nb_                                          # a hold: no target to search
        while j < nb_ and t[j] < S[p]:
            if h[j] >= up[p] and nxt[j] == j:
                hit = j
                break
            j += 1
        if hit >= 0:
            kind[p], idx[p], px[p] = 0, hit, T[p]
            continue
        k = nxt[np.searchsorted(t, S[p])]
        if k >= nb_:
            if delisted:
                kind[p] = 3
            continue
        kind[p], idx[p], px[p] = 2, k, o[k]
    return kind, idx, px


def _dec_floor_n(x: float, tick: str) -> int:
    """The largest n with n tau <= x in exact decimals, x within a relative 1e-13 below a grid point counting as on it
    (the levels module's stated rule, coded again)."""
    d = Decimal(repr(float(x)))
    tk = Decimal(tick)
    n = int((d / tk).to_integral_value(rounding=ROUND_FLOOR))
    if (Decimal(n + 1) * tk - d) <= d * Decimal("1e-13"):
        n += 1
    return n


def _dec_val(n: int, tick: str) -> float:
    return float(Decimal(int(n)) * Decimal(tick))


class OracleCoin:
    """One coin's paths as the oracle sees them: bars kept (missing minutes removed, trading stopped at a delisting),
    tick counts and floats, live flags, daily closes, the delisting value (VWAP of the last full trading day x 0.70,
    §4.1) and the member months."""

    def __init__(self, market: SynthMarket, coin: str, end_day: str):
        A = market.path(coin)
        k = A["keep"]
        self.coin, self.tick = coin, A["tick"]
        self.tau = float(self.tick)
        self.t = A["t"][k]
        self.on, self.hn, self.ln, self.cn = (A[x][k] for x in ("o", "h", "l", "c"))
        self.o, self.h, self.l, self.c = (_tick_float(x, self.tick) for x in (self.on, self.hn, self.ln, self.cn))
        self.live = A["live"][k]
        self.qv = A["qv"][k]
        self.vol = np.where(self.c > 0, self.qv / self.c, 0.0)
        self.nxt = _o_next_live(self.live)
        self.end_min = _tmin(pd.Timestamp(end_day) + pd.Timedelta(days=1)) - 1
        lt = self.t[self.live]
        self.last_live_t = int(lt[-1])
        self.delisted = bool(A["params"]["delist"] >= 0)
        self.months = {int(np.datetime64(m, "M").astype(np.int64)) for m in market.member_months(coin)}
        # daily closes of traded days (the close of each day's last live minute)
        day = lt // DAY_M
        cl = self.c[self.live]
        last = np.r_[day[1:] != day[:-1], True]
        self.days, self.dclose = day[last], cl[last]
        self.dclose_n = self.cn[self.live][last]
        # delisting value: VWAP of the last UTC day with live bars in hour 00 and hour 23, x 0.70
        self.dl_value = np.nan
        if self.delisted:
            hh = (lt % DAY_M) // 60
            full = [d for d in np.unique(day) if ((day == d) & (hh == 0)).any() and ((day == d) & (hh == 23)).any()]
            fd = full[-1]
            sel = self.live & (self.t // DAY_M == fd)
            self.dl_value = float(self.qv[sel].sum() / self.vol[sel].sum()) * 0.70

    # ---- levels (M2, §6.2) from the oracle's own daily closes
    def bids(self, rungs=(6.0, 8.0, 10.0), first="2020-01-06 03:30", last="2026-11-09 03:30") -> pd.DataFrame:
        t0s = _tmin(pd.date_range(pd.Timestamp(first, tz="UTC"), pd.Timestamp(last, tz="UTC"), freq="7D"))
        dpos = {int(d): i for i, d in enumerate(self.days)}
        rows = []
        for t0 in t0s:
            if t0 > self.end_min:
                break
            mo = int(np.datetime64(_ts(t0).tz_localize(None).strftime("%Y-%m"), "M").astype(np.int64))
            if mo not in self.months:
                continue
            d0 = int(t0 // DAY_M) - 1
            j = dpos.get(d0)
            if j is None or j < 30 or int(self.days[j - 30]) != d0 - 30:
                continue                                     # needs 30 consecutive daily returns ending d0
            cl = self.dclose[j - 30:j + 1]
            sig = float(np.std(np.diff(np.log(cl)), ddof=1))
            P0 = float(cl[-1])
            P0n = int(self.dclose_n[j])
            if not sig > 0:
                continue                                     # sigma30 = 0 is not a valid input
            for k in rungs:
                n = _dec_floor_n(P0 * math.exp(-k * sig), self.tick)
                if n < 1 or n >= P0n:
                    continue                                 # a level must be a positive price below P0
                rows.append(dict(coin=self.coin, t0=int(t0), rung=float(k), P0=P0, P0_n=P0n, sigma30=sig, L_n=n,
                                 L=_dec_val(n, self.tick), life_end=int(min(t0 + 7 * DAY_M, self.end_min + 1))))
        return pd.DataFrame(rows)

    def fills(self, b: pd.DataFrame) -> np.ndarray:
        if not len(b):
            return np.zeros(0, np.int64)
        return _o_fills(self.t, self.ln, self.live, b.t0.to_numpy(np.int64) + 1, b.life_end.to_numpy(np.int64),
                        b.L_n.to_numpy(np.int64) - 1)

    def exits(self, g, S, T, up):
        return _o_exits(self.t, self.o, self.h, self.nxt, np.asarray(g, np.int64), np.asarray(S, np.int64),
                        np.asarray(T, float), np.asarray(up, float), self.last_live_t, self.delisted, self.end_min)

    def exit_prices(self, kind, px):
        """Exit prices with the delisting value filled in (kind 3)."""
        return np.where(kind == 3, self.dl_value, px)

    def first_open_at(self, m):
        """Open of the first live minute at or after each minute m (B-ALERT), NaN if trading has stopped."""
        i = self.nxt[np.searchsorted(self.t, np.asarray(m, np.int64))]
        ok = i < len(self.t)
        return np.where(ok, self.o[np.minimum(i, len(self.t) - 1)], np.nan)

    # ---- twins (§10.1 B-TWIN), drawn with the oracle's own generator
    def eligible(self, stop_m: int):
        """Live bars in member months whose exit horizon M(entry + stop) is at or before the data end (windows cut
        by a delisting are kept): the sorted entry bars."""
        mo = (self.t // DAY_M).astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
        ok = self.live & np.isin(mo, np.fromiter(self.months, np.int64))
        bars = np.flatnonzero(ok)
        # the last entry minute whose horizon is inside the data (rule M is non-decreasing): binary search
        lo, hi = self.end_min - stop_m - 5 * DAY_M, self.end_min
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if _rule_m_py(mid + stop_m) <= self.end_min:
                lo = mid
            else:
                hi = mid
        cut = lo
        return bars[self.t[bars] <= cut]

    def twin_draws(self, bars_el: np.ndarray, tau_f: int, rng, n: int = 100, excl_days: int = 182):
        tt = self.t[bars_el]
        i0 = int(np.searchsorted(tt, tau_f - excl_days * DAY_M, side="left"))
        i1 = int(np.searchsorted(tt, tau_f + excl_days * DAY_M, side="right"))
        nL, nR = i0, len(tt) - i1
        days = len(np.unique(tt[:i0] // DAY_M)) + len(np.unique(tt[i1:] // DAY_M))
        if nL + nR == 0 or days < 182:
            return None
        k = rng.integers(0, nL + nR, n)
        return np.where(k < nL, bars_el[np.minimum(k, max(nL - 1, 0))], bars_el[np.minimum(i1 + k - nL, len(tt) - 1)])


EXIT_DEF = {"FLIP": ("flip", False, 72 * 60), "FLIP_bot": ("flip", True, 72 * 60), "HOLD90": ("hold", False, 90 * DAY_M)}


def _clock(kind: str, bot: bool, stop_m: int, te: np.ndarray):
    """(go-live, stop) minutes of exits from entry minutes te under rule M (§8)."""
    S = rule_m_oracle(te + stop_m)
    if kind == "hold":
        return S.copy(), S
    g = te + 1 if bot else rule_m_oracle(te)
    return g, S


def oracle_market(market: SynthMarket, exits=("FLIP", "FLIP_bot", "HOLD90"), n_twins: int = 100,
                  seed: int = SEED + 7, coins=None) -> dict:
    """The K1 / K2 oracle on a synthetic market: per coin, the M2 bids (k = 6, 8, 10) from its own daily closes, F1
    fills, every exit in `exits` (r before costs and at C-RH, kind, exit minute), the B-ALERT advantage a_f under rule
    M, and the mean of n_twins twins per fill and exit drawn with the oracle's own generator from the eligible
    minutes (live, member month, outside +-182 days, horizon inside the data). Returns {'bids', 'fills', 'twins'}."""
    end_day = market.spec.end
    rows_b, rows_f, tw_rows = [], [], []
    for coin in (coins or market.coins):
        oc = OracleCoin(market, coin, end_day)
        b = oc.bids()
        if not len(b):
            continue
        fi = oc.fills(b)
        b["i_fill"] = fi
        b["t_fill"] = np.where(fi >= 0, oc.t[np.maximum(fi, 0)], -1)
        rows_b.append(b)
        F = b[b.i_fill >= 0].reset_index(drop=True)
        if not len(F):
            continue
        m = F.t_fill.to_numpy(np.int64)
        L = F.L.to_numpy(float)
        Rn = np.ceil((F.L_n.to_numpy() + F.P0_n.to_numpy()) / 2).astype(np.int64)
        R = np.array([_dec_val(x, oc.tick) for x in Rn])
        upR = np.array([_dec_val(x + 1, oc.tick) for x in Rn])
        out = dict(coin=coin, t0=F.t0.to_numpy(), rung=F.rung.to_numpy(), t_fill=m, L=L, R=R)
        fi_ = F.i_fill.to_numpy(np.int64)
        out["o_fill"], out["c_fill"] = oc.o[fi_], oc.c[fi_]               # the fill minute's open and close (K1c)
        out["a_M"] = oc.first_open_at(rule_m_oracle(m)) / L - 1.0
        frng = {}
        for ex in exits:
            kd, bot, stop = EXIT_DEF[ex]
            g, S = _clock(kd, bot, stop, m)
            T = R if kd == "flip" else np.full(len(m), np.inf)
            up = upR if kd == "flip" else np.full(len(m), np.inf)
            kind, idx, px = oc.exits(g, S, T, up)
            px = oc.exit_prices(kind, px)
            out[f"kind_{ex}"] = kind
            out[f"xt_{ex}"] = np.where(idx >= 0, oc.t[np.maximum(idx, 0)], -1)
            out[f"r0_{ex}"] = np.where(kind < 4, px / L - 1.0, np.nan)
            out[f"rRH_{ex}"] = np.where(kind < 4, px * (1 - C_RH) / (L * (1 + C_RH)) - 1.0, np.nan)
            # twins
            el = oc.eligible(stop)
            tw_mean = np.full(len(m), np.nan)
            tw_dl = np.full(len(m), np.nan)
            for j in range(len(m)):
                key = int(hashlib.sha1(f"{coin}|{int(F.t0[j])}|{F.rung[j]}".encode()).hexdigest()[:12], 16)
                rng = frng.setdefault(j, np.random.default_rng([seed, key]))
                bars = oc.twin_draws(el, int(m[j]), rng, n_twins)
                if bars is None:
                    continue
                te = oc.t[bars]
                oe = oc.o[bars]
                ratio = R[j] / L[j] if kd == "flip" else np.inf
                gt, St = _clock(kd, bot, stop, te)
                Tt = oe * ratio if kd == "flip" else np.full(len(te), np.inf)
                upt = Tt + oc.tau if kd == "flip" else np.full(len(te), np.inf)
                kk, ii, pp = oc.exits(gt, St, Tt, upt)
                pp = oc.exit_prices(kk, pp)
                r = np.where(kk < 4, pp / oe - 1.0, np.nan)
                tw_mean[j] = np.nanmean(r)
                tw_dl[j] = float(np.mean(kk == 3))
            out[f"tw0_{ex}"] = tw_mean
            out[f"twdl_{ex}"] = tw_dl
        rows_f.append(pd.DataFrame(out))
    bids = pd.concat(rows_b, ignore_index=True) if rows_b else pd.DataFrame()
    fills = pd.concat(rows_f, ignore_index=True) if rows_f else pd.DataFrame()
    return {"bids": bids, "fills": fills}


def oracle_engine_twins(market: SynthMarket, eng_twins: list, ofills: pd.DataFrame, efills: pd.DataFrame,
                        exits=("FLIP", "FLIP_bot", "HOLD90")) -> dict:
    """Checks the engine's own twin draws with the oracle's code: every entry is eligible (live, member month,
    outside +-182 days of its fill, horizon inside the data) and its exit, recomputed from the entry minute with the
    fill's relative target, equals the engine's return before costs. Returns counts and the largest difference."""
    if not eng_twins:
        return dict(n=0)
    key = efills[["fill_id", "coin", "t0", "rung"]].merge(ofills[["coin", "t0", "rung", "L", "R", "t_fill"]],
                                                          on=["coin", "t0", "rung"], how="inner")
    fmap = key.set_index("fill_id")
    res = dict(n=0, n_ineligible=0, n_mismatch=0, max_abs_diff=0.0, n_delist=0, by_exit={})
    by_coin = {}
    for d in eng_twins:
        if d.get("pooled") or d.get("suf", "") != "" or d.get("rule") != "F1" or d.get("spec") not in exits:
            continue
        by_coin.setdefault(d["coin"], []).append(d)
    for coin, lst in by_coin.items():
        oc = OracleCoin(market, coin, market.spec.end)
        for d in lst:
            ex = d["spec"]
            kd, bot, stop = EXIT_DEF[ex]
            fid = np.asarray(d["fill_id"], np.int64)
            ok = np.isin(fid, fmap.index.to_numpy())
            if not ok.all():
                fid = fid[ok]
            te = np.asarray(d["te"], np.int64)[ok]
            r_e = np.asarray(d["r:C-0"], float)[ok]
            tau_f = fmap.loc[fid, "t_fill"].to_numpy(np.int64)
            ratio = (fmap.loc[fid, "R"].to_numpy(float) / fmap.loc[fid, "L"].to_numpy(float)) if kd == "flip" \
                else np.full(len(fid), np.inf)
            el = oc.eligible(stop)
            elt = oc.t[el]
            pos = np.searchsorted(elt, te)
            inel = (pos >= len(elt)) | (elt[np.minimum(pos, len(elt) - 1)] != te) | \
                   (np.abs(te - tau_f) <= 182 * DAY_M)
            bi = np.searchsorted(oc.t, te)
            oe = oc.o[bi]
            gt, St = _clock(kd, bot, stop, te)
            Tt = oe * ratio
            upt = Tt + oc.tau if kd == "flip" else np.full(len(te), np.inf)
            kk, ii, pp = oc.exits(gt, St, Tt if kd == "flip" else np.full(len(te), np.inf), upt)
            pp = oc.exit_prices(kk, pp)
            r_o = np.where(kk < 4, pp / oe - 1.0, np.nan)
            both = np.isfinite(r_o) & np.isfinite(r_e)
            diff = np.abs(r_o - r_e)[both]
            mism = int((diff > 1e-9).sum()) + int((np.isfinite(r_o) != np.isfinite(r_e)).sum())
            e = res["by_exit"].setdefault(ex, dict(n=0, n_ineligible=0, n_mismatch=0, n_delist=0))
            for tgt in (res, e):
                tgt["n"] += int(len(te))
                tgt["n_ineligible"] += int(inel.sum())
                tgt["n_mismatch"] += mism
                tgt["n_delist"] += int((kk == 3).sum())
            if len(diff):
                res["max_abs_diff"] = max(res["max_abs_diff"], float(diff.max()))
    return res


# ============================================================================ parallel helpers
def _pmap(fn, tasks: list, jobs: int = 4):
    """Map fn over tasks (spawned processes when jobs > 1; results in task order)."""
    if jobs <= 1 or len(tasks) <= 1:
        return [fn(t) for t in tasks]
    old = {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}
    os.environ.update({k: "1" for k in old})
    try:
        with cf.ProcessPoolExecutor(min(jobs, len(tasks)), mp_context=mp.get_context("spawn")) as ex:
            return list(ex.map(fn, tasks))
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _chunks(seq: list, n: int) -> list:
    n = max(1, min(n, len(seq)))
    return [seq[i::n] for i in range(n)]


def _oracle_task(args):
    spec, coins, exits = args
    return oracle_market(SynthMarket(spec), exits=exits, coins=coins)


def oracle_parallel(spec: SynthSpec, exits=("FLIP", "FLIP_bot", "HOLD90"), jobs: int = 4) -> dict:
    market = SynthMarket(spec)
    parts = _pmap(_oracle_task, [(spec, c, exits) for c in _chunks(market.coins, jobs * 2)], jobs)
    return {k: pd.concat([p[k] for p in parts if len(p[k])], ignore_index=True) for k in ("bids", "fills")}


def _twin_task(args):
    spec, twins, ofills, efills, exits = args
    return oracle_engine_twins(SynthMarket(spec), twins, ofills, efills, exits)


def engine_twins_parallel(spec: SynthSpec, twins: list, ofills, efills, exits, jobs: int = 4) -> dict:
    by = {}
    for d in twins:
        by.setdefault(d["coin"], []).append(d)
    coins = sorted(by)
    tasks = [(spec, [d for c in ch for d in by[c]], ofills, efills, exits) for ch in _chunks(coins, jobs * 2)]
    parts = _pmap(_twin_task, tasks, jobs)
    out = dict(n=0, n_ineligible=0, n_mismatch=0, max_abs_diff=0.0, n_delist=0, by_exit={})
    for p in parts:
        if not p.get("n"):
            continue
        for k in ("n", "n_ineligible", "n_mismatch", "n_delist"):
            out[k] += p[k]
        out["max_abs_diff"] = max(out["max_abs_diff"], p["max_abs_diff"])
        for ex, e in p["by_exit"].items():
            o = out["by_exit"].setdefault(ex, dict(n=0, n_ineligible=0, n_mismatch=0, n_delist=0))
            for k in o:
                o[k] += e[k]
    return out


# ============================================================================ K1 / K2: engine against the oracle
K1_EXITS = ("FLIP", "FLIP_bot", "HOLD90")


def k1_cfg(jobs: int = 4, **kw) -> dict:
    """The engine configuration of the known-answer runs: F1, X-FLIP (rule M), X-FLIP-bot and X-HOLD-90 with their
    twins, the K5 audit in 'report' mode (violations are counted by K5, not raised), per-twin rows kept, no capacity
    (K1 and K2 do not use it; K4 and K6 check capacity)."""
    c = dict(rules=("F1",), exits={"F1": tuple(sbe.EXIT_SPECS[x] for x in K1_EXITS)}, twin_sens=False, drift=False,
             mw=False, ml=False, usd=False, audit="report", capacity="none", keep_twins=True, verbose=False,
             n_jobs=jobs)
    c.update(kw)
    return c


def _mean_se(x) -> tuple:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return n, (float(x.mean()) if n else np.nan), np.nan
    return n, float(x.mean()), float(x.std(ddof=1) / math.sqrt(n))


def compare_k1(res: dict, O: dict, exits=K1_EXITS) -> dict:
    """Engine run against the oracle: bids (set, tick counts), F1 fills (minutes), and per exit the fill-by-fill
    returns (before costs and at C-RH), exit kinds and minutes, plus the prereg's rule: the engine's mean r_f and
    mean Delta before costs each within 2 SE of the oracle's (SE = the oracle's SD / sqrt(n) over the fills whose
    horizon is complete and whose twins are the coin's own); B-ALERT a_f under rule M fill by fill."""
    B, F, Oc, Bn = res["bids"], res["fills"], res["outcomes"], res.get("bench", pd.DataFrame())
    ob, of = O["bids"], O["fills"]
    out = {}
    eb = B[["coin", "t0", "rung", "n_ticks"]]
    mb = eb.merge(ob[["coin", "t0", "rung", "L_n"]], on=["coin", "t0", "rung"], how="outer", indicator=True)
    both = mb[mb._merge == "both"]
    out["bids"] = dict(engine=len(eb), oracle=len(ob), only_engine=int((mb._merge == "left_only").sum()),
                       only_oracle=int((mb._merge == "right_only").sum()),
                       ticks_differ=int((both.n_ticks != both.L_n).sum()))
    ef = F[F.t_F1 >= 0][["fill_id", "coin", "t0", "rung", "t_F1", "month_block"]] if len(F) else \
        pd.DataFrame(columns=["fill_id", "coin", "t0", "rung", "t_F1", "month_block"])
    mf = ef.merge(of, on=["coin", "t0", "rung"], how="outer", indicator=True)
    fb = mf[mf._merge == "both"].copy()
    out["fills"] = dict(engine=len(ef), oracle=len(of), only_engine=int((mf._merge == "left_only").sum()),
                        only_oracle=int((mf._merge == "right_only").sum()),
                        minute_differ=int((fb.t_F1 != fb.t_fill).sum()))
    if len(Bn) and "alert_M" in Bn:
        a = fb.merge(Bn[Bn.rule == "F1"][["fill_id", "alert_M"]], on="fill_id", how="left")
        d = np.abs(a.alert_M.to_numpy(float) - a.a_M.to_numpy(float))
        fin = np.isfinite(a.alert_M.to_numpy(float)) & np.isfinite(a.a_M.to_numpy(float))
        out["alert"] = dict(n=int(fin.sum()), max_abs_diff=float(d[fin].max()) if fin.any() else 0.0,
                            nan_differ=int((np.isfinite(a.alert_M.to_numpy(float)) !=
                                            np.isfinite(a.a_M.to_numpy(float))).sum()),
                            engine_mean=_mean_se(a.alert_M)[1], oracle_mean=_mean_se(a.a_M)[1])
    ek = {"target": 0, "marketable": 1, "stop": 2, "delist": 3, "censored": 4}
    out["exits"] = {}
    for ex in exits:
        if not len(Oc):
            continue
        e0 = Oc[(Oc.rule == "F1") & (Oc.exit == ex) & (Oc.cost == "C-0")][
            ["fill_id", "r", "delta", "twin_mean", "twin_pooled", "complete", "exit_kind", "exit_t"]]
        eR = Oc[(Oc.rule == "F1") & (Oc.exit == ex) & (Oc.cost == "C-RH")][["fill_id", "r", "delta"]].rename(
            columns={"r": "rRH_e", "delta": "dRH_e"})
        m = fb.merge(e0, on="fill_id", how="inner").merge(eR, on="fill_id", how="left")
        r0o, rRo = m[f"r0_{ex}"].to_numpy(float), m[f"rRH_{ex}"].to_numpy(float)
        r0e, rRe = m.r.to_numpy(float), m.rRH_e.to_numpy(float)
        fin = np.isfinite(r0o) & np.isfinite(r0e)
        kind_e = m.exit_kind.map(ek).fillna(-1).to_numpy()
        kind_o = m[f"kind_{ex}"].to_numpy()
        res_x = dict(n_fills=len(m), n_compared=int(fin.sum()),
                     r0_max_abs_diff=float(np.abs(r0o - r0e)[fin].max()) if fin.any() else 0.0,
                     rRH_max_abs_diff=float(np.nanmax(np.abs(rRo - rRe)[fin])) if fin.any() else 0.0,
                     finite_differ=int((np.isfinite(r0o) != np.isfinite(r0e)).sum()),
                     kind_differ=int((kind_e[fin] != kind_o[fin]).sum()),
                     minute_differ=int((m.exit_t.to_numpy()[fin] != m[f"xt_{ex}"].to_numpy()[fin]).sum()))
        use = fin & m.complete.astype(bool).to_numpy() & ~m.twin_pooled.astype(bool).to_numpy() & \
            np.isfinite(m.twin_mean.to_numpy(float)) & np.isfinite(m[f"tw0_{ex}"].to_numpy(float))
        d_e = (r0e - m.twin_mean.to_numpy(float))[use]
        d_o = (r0o - m[f"tw0_{ex}"].to_numpy(float))[use]
        n, mo_r, se_r = _mean_se(r0o[use])
        _, me_r, _ = _mean_se(r0e[use])
        _, mo_d, se_d = _mean_se(d_o)
        _, me_d, _ = _mean_se(d_e)
        res_x.update(n=n, oracle_r=mo_r, engine_r=me_r, se_r=se_r, oracle_delta=mo_d, engine_delta=me_d, se_delta=se_d,
                     diff_r_se=(me_r - mo_r) / se_r if se_r > 0 else np.nan,
                     diff_delta_se=(me_d - mo_d) / se_d if se_d > 0 else np.nan,
                     pass_r=bool(np.isfinite(se_r) and abs(me_r - mo_r) <= K1_SE_MULT * se_r),
                     pass_delta=bool(np.isfinite(se_d) and abs(me_d - mo_d) <= K1_SE_MULT * se_d),
                     engine_delta_RH=float(np.nanmean(m.dRH_e.to_numpy(float)[use])) if use.any() else np.nan,
                     oracle_twin_delisted=float(np.nanmean(m[f"twdl_{ex}"].to_numpy(float)[use])) if use.any()
                     else np.nan)
        res_x["passed"] = bool(res_x["pass_r"] and res_x["pass_delta"])
        out["exits"][ex] = res_x
    return out


def _exact_ok(c: dict) -> bool:
    """The fill-by-fill diagnostics (reported; the prereg's rule is the 2-SE comparison of the means)."""
    ok = c["bids"]["only_engine"] == 0 and c["bids"]["only_oracle"] == 0 and c["bids"]["ticks_differ"] == 0
    ok &= c["fills"]["only_engine"] == 0 and c["fills"]["only_oracle"] == 0 and c["fills"]["minute_differ"] == 0
    for e in c.get("exits", {}).values():
        ok &= e["r0_max_abs_diff"] <= 1e-9 and e["kind_differ"] == 0 and e["finite_differ"] == 0
    if "alert" in c:
        ok &= c["alert"]["max_abs_diff"] <= 1e-9 and c["alert"]["nan_differ"] == 0
    return bool(ok)


def fill_rates(res_or_bids, fills=None) -> dict:
    """F1 fills per bid-week by rung (counts and rates) from an engine run or an oracle (bids with t_fill)."""
    if isinstance(res_or_bids, dict):
        B, F = res_or_bids["bids"], res_or_bids["fills"]
        nb_ = B.groupby("rung").size()
        nf = F[F.t_F1 >= 0].groupby("rung").size() if len(F) else pd.Series(dtype=float)
    else:
        B = res_or_bids
        nb_ = B.groupby("rung").size()
        nf = B[B.t_fill >= 0].groupby("rung").size()
    return {f"{k:g}": dict(bids=int(nb_[k]), fills=int(nf.get(k, 0)), rate=float(nf.get(k, 0) / nb_[k]))
            for k in nb_.index}


def _k_engine(spec: SynthSpec, jobs: int, **cfg_kw) -> dict:
    t = time.time()
    res = sbe.run_program("P1", "U_Q1", data=SynthMarket(spec).world(), cfg=k1_cfg(jobs, **cfg_kw))
    res["meta"]["wall_s"] = time.time() - t
    return res


def _audit_counts(res: dict) -> dict:
    A = res.get("audit", pd.DataFrame())
    if not len(A):
        return dict(violations=0, gaps=0, checks=0)
    ty = A["type"] if "type" in A else pd.Series(dtype=str)
    return dict(violations=int((ty == "violation").sum()), gaps=int((ty == "gap").sum()),
                checks=int(A.loc[ty == "count", "n"].sum()) if "n" in A else int((ty == "count").sum()))


def run_k1_world(spec: SynthSpec, jobs: int = 4, exits=K1_EXITS, twins_check: bool = True,
                 wrong: tuple = ()) -> dict:
    """One known-answer world: the engine (P1, F1, the K1 exits) against the oracle; the wrong engines (fill booked
    at the fill minute's close / low) when asked. Returns the comparison, fill rates, audit counts, timings."""
    t0 = time.time()
    res = _k_engine(spec, jobs)
    t1 = time.time()
    O = oracle_parallel(spec, exits, jobs)
    t2 = time.time()
    c = compare_k1(res, O, exits)
    out = dict(spec=asdict(spec), rates_engine=fill_rates(res), rates_oracle=fill_rates(O["bids"]), compare=c,
               exact_ok=_exact_ok(c), audit=_audit_counts(res), timings=dict(engine_s=t1 - t0, oracle_s=t2 - t1))
    if twins_check:
        out["engine_twins"] = engine_twins_parallel(spec, res.get("twins", []), O["fills"], res["fills"], exits, jobs)
        out["timings"]["twins_s"] = time.time() - t2
    out["_res"], out["_oracle"] = res, O
    for fp in wrong:
        t3 = time.time()
        rw = _k_engine(spec, jobs, fill_price=fp, keep_twins=False)
        cw = compare_k1(rw, O, ("FLIP",))["exits"]["FLIP"]
        out[f"wrong_{fp}"] = dict(engine_r=cw["engine_r"], engine_delta=cw["engine_delta"], oracle_r=cw["oracle_r"],
                                  oracle_delta=cw["oracle_delta"], se_r=cw["se_r"], se_delta=cw["se_delta"],
                                  diff_r_se=cw["diff_r_se"], diff_delta_se=cw["diff_delta_se"],
                                  fails=bool(not cw["passed"]), seconds=time.time() - t3)
    return out


# ============================================================================ K1b: jumps tuned to P1's real fill counts
# The frozen starting point of the tuning (found by tune_k1b on the real counts of 2026-11-18, counts only); run()
# verifies the +-25% match on the engine's own synthetic counts and re-tunes when it fails.
K1B_JUMP_RATE = 6.0                               # market-wide jumps a year hitting 35% of the coins, 9.5-12.5 daily
K1B_JUMP_MEAN = 0.0                               # sigmas (oracle, 40 coins: -15.0% / -7.1% / +7.5% against the real
#                                                   rates; K2's planted effect +7.7% per fill, month-block t 6.8)


def _count_task(args):
    spec, coins = args
    market = SynthMarket(spec)
    out = []
    for c in coins:
        oc = OracleCoin(market, c, spec.end)
        b = oc.bids()
        if len(b):
            b["t_fill"] = np.where(oc.fills(b) >= 0, 1, -1)
            out.append(b[["rung", "t_fill"]])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["rung", "t_fill"])


def oracle_rates(spec: SynthSpec, jobs: int = 4, n_coins: int | None = None) -> dict:
    """P1's F1 fill rates per bid-week by rung on a synthetic market, from the oracle's own bids and fills."""
    coins = SynthMarket(spec).coins[:n_coins] if n_coins else SynthMarket(spec).coins
    parts = _pmap(_count_task, [(spec, ch) for ch in _chunks(coins, jobs * 2)], jobs)
    return fill_rates(pd.concat(parts, ignore_index=True))


def rate_errors(rates: dict, target: dict) -> dict:
    """Synthetic / real - 1 per rung (k = 6, 8, 10)."""
    return {k: rates[k]["rate"] / target[k] - 1.0 for k in ("6", "8", "10") if k in rates and k in target}


def tune_k1b(target: dict, base: SynthSpec, jobs: int = 4, n_coins: int = 20, grid=None, log=_say) -> tuple:
    """Grid search over (jumps a year, mean log jump) for P1's synthetic F1 fill rates at k = 6, 8, 10 to match the
    real ones (counts only): the pair with the smallest largest relative error. Returns (rate, mean, errors)."""
    grid = grid or [(lam, 0.0) for lam in (4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0)]
    best = None
    for lam, mu in grid:
        sp = replace(base, jump_rate=lam, jump_mean=mu)
        err = rate_errors(oracle_rates(sp, jobs, n_coins), target)
        worst = max(abs(v) for v in err.values())
        log(f"  tune K1b: {lam:g} jumps a year, mean {mu:.2f}: errors " +
            ", ".join(f"k={k} {v:+.1%}" for k, v in err.items()))
        if best is None or worst < best[2]:
            best = (lam, mu, worst, err)
    return best[0], best[1], best[3]


def k1_specs(rate: float = K1B_JUMP_RATE, mean: float = K1B_JUMP_MEAN, n_coins: int = K1_COINS,
             start: str = SYN_START, end: str = END_DAY) -> dict:
    """The known-answer markets (§10.5): K1a no jumps; K1b market-wide jumps that do not revert (tuned to P1's real
    fill counts); K1c regime-switching drift (+-0.2% a day in 6-month regimes, S13) with crash intensity 3x higher in
    bear regimes; K1c0, K1c's paired null (the same seed, regime states, crash schedule and shocks, with no regime
    drift and each regime's crashes compensated at its own intensity, so every regime is a martingale: its Delta is
    the minute-level gap-through cost of K1b's jumps alone, which K1c - K1c0 removes); K1d K1b with synthetic
    delistings (24 of 48 coins stop trading at a uniform random minute between 40% of the span (2022-08) and 50 days
    before its end, so every coin keeps >= 182 eligible twin days); K2 K1b with each jump split into a permanent half
    and a transient half reverting with a 30-minute half-life. K1b, K1d and K2 share the seed (same shocks and jump
    minutes)."""
    a = SynthSpec(name="K1a", n_coins=n_coins, start=start, end=end)
    b = replace(a, name="K1b", jump_rate=rate, jump_mean=mean)
    t_a, t_b = pd.Timestamp(start), pd.Timestamp(end)
    d_from = (t_a + 0.4 * (t_b - t_a)).normalize()                   # 2022-08 on the full span
    d_to = (t_b - pd.Timedelta(days=50)).normalize()
    c = replace(b, name="K1c", regime_drift=0.002, bear_mult=3.0)
    return {"K1a": a, "K1b": b, "K1c": c,
            "K1c0": replace(c, name="K1c0", regime_drift=0.0, comp_regime=True),
            "K1d": replace(b, name="K1d", n_coins=int(round(n_coins * 1.2)), delist_n=int(round(n_coins * 0.6)),
                           delist_from=d_from.strftime("%Y-%m-%d"), delist_to=d_to.strftime("%Y-%m-%d")),
            "K2": replace(b, name="K2", transient=0.5)}


def _strip(w: dict) -> dict:
    """A world result without the raw tables (for JSON)."""
    return {k: v for k, v in w.items() if not k.startswith("_")}


def k1d_haircut(spec: SynthSpec, w: dict) -> dict:
    """K1d (§10.5): fills and twins must take the delisting haircut at equal rates. Checked three ways on X-HOLD-90
    (and reported on X-FLIP): (a) every position (fill or the engine's twin) whose exit horizon M(entry + 90 d) lies
    after its coin's last trade is valued at the §4.1 value (VWAP of the last full trading day x 0.70) and none other
    is (exact valuation is part of the fill-by-fill and twin-by-twin oracle checks); (b) the engine's twins take it
    at the rate their eligibility implies: their count of delisted twins against the oracle's own independent draws
    for the same fills, within 2 SE (binomial, per fill); (c) the raw shares of fills and of twins closed at the
    delisting value are reported (the +-182-day exclusion around each fill makes them differ by design)."""
    res, O = w["_res"], w["_oracle"]
    market = SynthMarket(spec)
    last = {}
    for c in market.coins:
        P = market.params(c)
        if P["delist"] >= 0:
            last[c] = OracleCoin(market, c, spec.end).last_live_t
    out = {}
    F = res["fills"]
    Oc = res["outcomes"]
    for ex in ("HOLD90", "FLIP"):
        kd, bot, stop = EXIT_DEF[ex]
        e0 = Oc[(Oc.rule == "F1") & (Oc.exit == ex) & (Oc.cost == "C-0")][["fill_id", "coin", "exit_kind", "complete"]]
        e0 = e0.merge(F[["fill_id", "t_F1"]], on="fill_id")
        dl = e0.coin.isin(list(last))
        hz = rule_m_oracle(e0.t_F1.to_numpy(np.int64) + stop)
        lt = e0.coin.map(last).fillna(np.inf).to_numpy(float)
        open_at_end = dl.to_numpy() & (hz > lt)
        is_dl = (e0.exit_kind == "delist").to_numpy()
        # twins of the engine (own twins of this exit)
        tk, tdl, topen = [], [], []
        for d in res.get("twins", []):
            if d.get("rule") != "F1" or d.get("spec") != ex or d.get("pooled") or d.get("suf", ""):
                continue
            te = np.asarray(d["te"], np.int64)
            l_ = last.get(d["coin"], np.inf)
            tk.append(np.asarray(d["kind"], np.int64))
            tdl.append(np.full(len(te), d["coin"] in last))
            topen.append(rule_m_oracle(te + stop) > l_)
        tk = np.concatenate(tk) if tk else np.zeros(0, np.int64)
        topen = np.concatenate(topen) if topen else np.zeros(0, bool)
        r = dict(fills=int(len(e0)), fills_delisted=int(is_dl.sum()), fills_share=float(is_dl.mean()) if len(e0) else 0.0,
                 twins=int(len(tk)), twins_delisted=int((tk == sbe.EK_DELIST).sum()),
                 twins_share=float(np.mean(tk == sbe.EK_DELIST)) if len(tk) else 0.0)
        if ex == "HOLD90":
            r["fills_open_at_end"] = int(open_at_end.sum())
            r["fills_open_at_end_haircut"] = int((is_dl & open_at_end).sum())
            r["fills_haircut_not_open"] = int((is_dl & ~open_at_end).sum())
            r["twins_open_at_end"] = int(topen.sum())
            r["twins_open_at_end_haircut"] = int(((tk == sbe.EK_DELIST) & topen).sum())
            r["twins_haircut_not_open"] = int(((tk == sbe.EK_DELIST) & ~topen).sum())
            r["conditional_ok"] = bool(r["fills_open_at_end"] == r["fills_open_at_end_haircut"] and
                                       r["fills_haircut_not_open"] == 0 and
                                       r["twins_open_at_end"] == r["twins_open_at_end_haircut"] and
                                       r["twins_haircut_not_open"] == 0 and r["twins_open_at_end"] > 0)
            # (b) the engine's delisted-twin counts against the oracle's independent draws, fill by fill
            of = O["fills"]
            m = F[F.t_F1 >= 0][["fill_id", "coin", "t0", "rung"]].merge(of[["coin", "t0", "rung", "twdl_HOLD90"]],
                                                                         on=["coin", "t0", "rung"])
            ke = {}
            for d in res.get("twins", []):
                if d.get("rule") == "F1" and d.get("spec") == ex and not d.get("pooled") and not d.get("suf", ""):
                    fid = np.asarray(d["fill_id"], np.int64)
                    kk = np.asarray(d["kind"], np.int64) == sbe.EK_DELIST
                    for f_, n_ in zip(*np.unique(fid[kk], return_counts=True)):
                        ke[int(f_)] = ke.get(int(f_), 0) + int(n_)
            k_e = np.array([ke.get(int(f), 0) for f in m.fill_id], float)
            k_o = np.nan_to_num(m.twdl_HOLD90.to_numpy(float)) * sbe.R_TWINS
            p = (k_e + k_o) / (2 * sbe.R_TWINS)
            var = float(np.sum(2 * sbe.R_TWINS * p * (1 - p)))
            d_ = float(k_e.sum() - k_o.sum())
            r.update(engine_twins_delisted=int(k_e.sum()), oracle_twins_delisted=int(round(k_o.sum())),
                     diff_se=d_ / math.sqrt(var) if var > 0 else 0.0,
                     rate_ok=bool(var > 0 and abs(d_) <= K1_SE_MULT * math.sqrt(var)))
        out[ex] = r
    h = out["HOLD90"]
    out["passed"] = bool(h["conditional_ok"] and h["rate_ok"] and h["fills_delisted"] > 0)
    return out


def _k2_stats(w: dict) -> dict:
    """K2 (§10.5): H1's statistic on the K2 world, X-FLIP under rule M and X-FLIP-bot: mean Delta at C-RH over the
    fills with a complete horizon and own twins, month-block CR1 t (stinkbid_stats.test_mean), and the oracle match."""
    res = w["_res"]
    O, F = res["outcomes"], res["fills"]
    out = {}
    for ex in ("FLIP", "FLIP_bot"):
        d = O[(O.rule == "F1") & (O.exit == ex) & (O.cost == "C-RH") & O.complete.astype(bool)
              & ~O.twin_pooled.astype(bool)][["fill_id", "delta"]].merge(F[["fill_id", "month_block"]], on="fill_id")
        d = d[np.isfinite(d.delta.to_numpy(float))]
        t = sbs.test_mean(d.delta.to_numpy(float), d.month_block.to_numpy(), B=sbs.B_BOOT)
        cmp_ = w["compare"]["exits"][ex]
        out[ex] = dict(n=int(len(d)), delta_RH=t["estimate"], se=t["se"], t=t["t"], G=t["G"], gstar=t["gstar"],
                       p_decide=t["p_decide"], t_ok=bool(t["estimate"] > 0 and t["t"] >= K2_T),
                       oracle_match=bool(cmp_["passed"]), oracle_delta=cmp_["oracle_delta"],
                       engine_delta=cmp_["engine_delta"], se_delta=cmp_["se_delta"])
    return out


K1C_EXITS = ("FLIP", "HOLD90")                    # §10.5 K1c: Delta under X-FLIP and X-HOLD-90


def _k1c_table(w: dict) -> pd.DataFrame:
    """Per F1 fill of a K1c-type world (K1c or its null K1c0): the engine's r_f and Delta before costs and at C-RH
    under X-FLIP and X-HOLD-90 with the horizon and twin flags, the month-block, and the oracle's r_f, twin mean and
    fill-minute open / close for the same fill (bid key: coin, placement, rung)."""
    res, O = w["_res"], w["_oracle"]
    F, Oc = res["fills"], res["outcomes"]
    out = F[F.t_F1 >= 0][["fill_id", "coin", "t0", "rung", "t_F1", "month_block"]].copy()
    for ex in K1C_EXITS:
        for cost, s in (("C-0", "0"), ("C-RH", "RH")):
            o = Oc[(Oc.rule == "F1") & (Oc.exit == ex) & (Oc.cost == cost)]
            o = o[["fill_id", "r", "delta"] + (["complete", "twin_pooled"] if s == "0" else [])].rename(
                columns={"r": f"r{s}_{ex}", "delta": f"d{s}_{ex}", "complete": f"complete_{ex}",
                         "twin_pooled": f"pooled_{ex}"})
            out = out.merge(o, on="fill_id", how="left")
    of = O["fills"]
    oc = {f"{k}_{ex}": f"o_{k}_{ex}" for ex in K1C_EXITS for k in ("r0", "rRH", "tw0")}   # the oracle's: o_ prefix
    of = of[["coin", "t0", "rung", "L", "o_fill", "c_fill"] + list(oc)].rename(columns=oc)
    return out.merge(of, on=["coin", "t0", "rung"], how="left").reset_index(drop=True)


def _cl_mean(y, clusters) -> dict:
    """Mean with its one-way CR1 SE (stinkbid_stats.cr1_mean: G / (G - 1), G*) and the iid SE beside it."""
    y = np.asarray(y, float)
    cl = np.asarray(clusters)
    ok = np.isfinite(y)
    n, m, se_iid = _mean_se(y[ok])
    r = sbs.cr1_mean(y[ok], cl[ok]) if n >= 2 else dict(se=np.nan, G=int(len(np.unique(cl[ok]))), gstar=np.nan)
    return dict(mean=m, se=float(r["se"]), se_iid=se_iid, n=int(n), G=int(r["G"]), gstar=float(r["gstar"]))


def _usable(T: pd.DataFrame, ex: str) -> np.ndarray:
    """Fills whose horizon is complete, with the coin's own twins and a finite Delta (as compare_k1 uses)."""
    return (T[f"complete_{ex}"].fillna(False).astype(bool) & ~T[f"pooled_{ex}"].fillna(True).astype(bool) &
            np.isfinite(T[f"d0_{ex}"].to_numpy(float)) & np.isfinite(T[f"dRH_{ex}"].to_numpy(float))).to_numpy()


def k1c_report(spec: SynthSpec, Tc: pd.DataFrame, T0: pd.DataFrame, cmp_c: dict | None = None,
               cmp_0: dict | None = None) -> dict:
    """K1c (§10.5; S13: regime-switching drift, crash intensity 3x higher in bear regimes "and no timing effect at the
    minute level"; its Delta under X-FLIP and X-HOLD-90 "is reported as what regime timing alone produces"). K1c's
    crashes are K1b's non-reverting gaps, whose minute-level gap-through cost (a fill at L above the price that
    follows) is most of K1c's Delta, so the Delta of K1c alone is not regime timing. What is exported is the regime
    component: per fill, K1c's Delta minus the Delta of the same bid's fill in K1c0 (the same seed, regime states,
    crash schedule and shocks, with no regime drift and every regime a martingale), averaged over the fills both
    worlds share (complete horizon, own twins), with a month-block CR1 SE (G, G*; the iid SE beside it). The
    gap-through cost is in both worlds and cancels; what remains is the effect of the regime drift and of the bear
    regime's extra crashes on fills that crashes time into bear stretches. engine_delta_RH (C-RH) and engine_delta
    (C-0) per exit are that component (HOLD90 -> engine_delta_RH = delta90, printed with D-H2); the oracle's paired
    value is beside it. Diagnostics, labelled: K1c's total Delta (the number exported before, clustered SE), the null
    world's Delta (the minute-level cost alone) and the gap-through shares of the fill minutes."""
    k = (1 - C_RH) / (1 + C_RH)
    key = ["coin", "t0", "rung"]
    out = dict(report="what regime timing alone produces",
               measure="paired: K1c minus K1c0 (the same seed, regime states, crash schedule and shocks; no regime "
                       "drift and each regime's crashes compensated at its own intensity) over the fills both "
                       "worlds share; month-block CR1 SE",
               regime_drift_per_day=spec.regime_drift, bear_mult=spec.bear_mult,
               regime_mean_days=spec.regime_mean_days, total={}, minute_level={})
    for ex in K1C_EXITS:
        uc, u0 = _usable(Tc, ex), _usable(T0, ex)
        c, z = Tc[uc], T0[u0]
        m = c.merge(z[key + [f"d0_{ex}", f"dRH_{ex}", f"o_r0_{ex}", f"o_rRH_{ex}", f"o_tw0_{ex}"]], on=key,
                    suffixes=("", "_null"))
        y0 = m[f"d0_{ex}"].to_numpy(float) - m[f"d0_{ex}_null"].to_numpy(float)
        yR = m[f"dRH_{ex}"].to_numpy(float) - m[f"dRH_{ex}_null"].to_numpy(float)
        v = {s_: {x: m[f"o_{x}_{ex}{s_}"].to_numpy(float) for x in ("r0", "rRH", "tw0")} for s_ in ("", "_null")}
        o_c, o_0 = (v[s_]["r0"] - v[s_]["tw0"] for s_ in ("", "_null"))               # the oracle's Delta, C-0
        oR_c, oR_0 = (v[s_]["rRH"] - (k * (1 + v[s_]["tw0"]) - 1) for s_ in ("", "_null"))   # and at C-RH
        cl = m.month_block.to_numpy()
        sR, s0 = _cl_mean(yR, cl), _cl_mean(y0, cl)
        out[ex] = dict(engine_delta_RH=sR["mean"], engine_delta=s0["mean"], se=sR["se"], se_C0=s0["se"],
                       se_iid=sR["se_iid"], n=sR["n"], G=sR["G"], gstar=sR["gstar"], unit="month-block",
                       oracle_delta=_mean_se(o_c - o_0)[1], oracle_delta_RH=_mean_se(oR_c - oR_0)[1],
                       n_K1c=int(uc.sum()), n_K1c0=int(u0.sum()), n_common=int(len(m)))
        tot = _cl_mean(c[f"dRH_{ex}"], c.month_block)
        out["total"][ex] = dict(engine_delta_RH=tot["mean"], engine_delta=_mean_se(c[f"d0_{ex}"])[1], se=tot["se"],
                                se_iid=tot["se_iid"], n=tot["n"], G=tot["G"], gstar=tot["gstar"],
                                engine_matches_oracle=None if cmp_c is None else
                                bool(cmp_c["exits"][ex]["passed"]))
        nul = _cl_mean(z[f"dRH_{ex}"], z.month_block)
        out["minute_level"][ex] = dict(engine_delta_RH=nul["mean"], engine_delta=_mean_se(z[f"d0_{ex}"])[1],
                                       se=nul["se"], se_iid=nul["se_iid"], n=nul["n"], G=nul["G"],
                                       gstar=nul["gstar"], engine_matches_oracle=None if cmp_0 is None else
                                       bool(cmp_0["exits"][ex]["passed"]))
    f = Tc[np.isfinite(Tc.c_fill.to_numpy(float))]
    L_ = f.L.to_numpy(float)
    out["gap_through"] = dict(fills=int(len(f)), share_open_below_L=float(np.mean(f.o_fill.to_numpy(float) < L_))
                              if len(f) else np.nan,
                              mean_close_over_L=float(np.mean(f.c_fill.to_numpy(float) / L_ - 1)) if len(f) else np.nan)
    out["delta90"] = out["HOLD90"]["engine_delta_RH"]
    out["note"] = ("delta90 = HOLD90.engine_delta_RH = the regime component (K1c minus K1c0, paired); total = K1c's own "
                   "Delta, which includes the minute-level gap-through cost of K1b's jumps (minute_level = K1c0's Delta, "
                   "that cost alone); a diagnostic, not what regime timing alone produces")
    return out


def run_k1(jobs: int = 4, target: dict | None = None, specs: dict | None = None, log=_say, wrong=True,
           retune: bool = True) -> dict:
    """K1a, K1b (with the two wrong engines and the fill-count match), K1c (with its paired null K1c0: k1c_report),
    K1d and K2 (§10.5). target: P1's real F1 fill rates per rung ({'6': rate, '8': ..., '10': ...}); None skips the
    match (selftest). Returns the K1 and K2 sections of summary.json (pass flags and headline numbers) and the detail
    for k1.json / k2.json."""
    specs = specs or k1_specs()
    out = {}
    t0 = time.time()
    # ---- K1b tuning check on the oracle's counts (fast), re-tuned when it fails
    if target is not None:
        err = rate_errors(oracle_rates(specs["K1b"], jobs), target)
        tuned = None
        if retune and max(abs(v) for v in err.values()) > K1B_TOL:
            lam, mu, _ = tune_k1b(target, specs["K1b"], jobs, log=log,
                                  grid=[(lam, 0.0) for lam in (4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0)])
            specs = k1_specs(lam, mu, specs["K1a"].n_coins, specs["K1a"].start, specs["K1a"].end)
            tuned = dict(jump_rate=lam, jump_mean=mu)
        out["tuning"] = dict(oracle_errors_frozen=err, retuned=tuned)
    worlds = {}
    import gc
    for name in ("K1a", "K1b", "K1c", "K1c0", "K1d", "K2"):
        ts = time.time()
        wrong_ = ("close", "low") if (name == "K1b" and wrong) else ()
        exits_ = K1C_EXITS if name == "K1c0" else K1_EXITS             # K1c0: K1c's paired null (no control)
        twins_ = name != "K1c0"
        key = hashlib.sha1(json.dumps(dict(spec=asdict(specs[name]), wrong=list(wrong_), exits=list(exits_),
                                           twins=twins_), sort_keys=True).encode()).hexdigest()[:12]
        cache_f = WORK / f"k1w_{name}_{code_hash(_K1_CODE)}_{key}.pkl"
        w = None
        if cache_f.exists():
            import pickle
            with open(cache_f, "rb") as fh:
                w = pickle.load(fh)
            log(f"K1/K2: {name} reused from {cache_f.name}")
        else:
            log(f"K1/K2: {name} ({specs[name].n_coins} coins, {specs[name].start}..{specs[name].end}) ...")
            full = run_k1_world(specs[name], jobs, exits=exits_, twins_check=twins_, wrong=wrong_)
            # reduce to what the verdicts, K5 and K7 need, then free the raw tables (memory)
            w = {k: v for k, v in full.items() if not k.startswith("_")}
            if name == "K1d":
                w["haircut"] = k1d_haircut(specs["K1d"], full)
            if name == "K2":
                w["k2"] = _k2_stats(full)
            if name in ("K1c", "K1c0"):
                w["k1c_table"] = _k1c_table(full)
            w["record"] = _compact_audit(full["_res"].get("audit"))
            B_ = full["_res"]["bids"]
            w["bids"] = B_[[c for c in ("program", "method", "L", "L_tau", "n_ticks", "tick_str") if c in B_]].copy()
            del full
            gc.collect()
            if WORK.exists() or True:
                import pickle
                WORK.mkdir(parents=True, exist_ok=True)
                with open(cache_f.with_suffix(".tmp"), "wb") as fh:
                    pickle.dump(w, fh)
                os.replace(cache_f.with_suffix(".tmp"), cache_f)
        worlds[name] = w
        e = w["compare"]["exits"]
        log(f"  {name}: {w['compare']['fills']['engine']} fills; FLIP oracle r {e['FLIP']['oracle_r']:+.4f} engine "
            f"{e['FLIP']['engine_r']:+.4f} (SE {e['FLIP']['se_r']:.4f}); delta oracle {e['FLIP']['oracle_delta']:+.4f}"
            f" engine {e['FLIP']['engine_delta']:+.4f} (SE {e['FLIP']['se_delta']:.4f}); exact {w['exact_ok']}; "
            f"twins {w.get('engine_twins', {}).get('n', 0)} checked, {w.get('engine_twins', {}).get('n_mismatch', 0)} "
            f"mismatches; {time.time() - ts:.0f}s")
    # ---- verdicts
    k1 = {}
    for name in ("K1a", "K1b"):
        e = worlds[name]["compare"]["exits"]
        k1[name] = dict(passed=all(x["passed"] for x in e.values()), exits={x: _strip(v) for x, v in e.items()},
                        fills=worlds[name]["compare"]["fills"]["engine"], exact_ok=worlds[name]["exact_ok"])
    wb = worlds["K1b"]
    if wrong:
        k1["wrong_engines"] = {fp: wb[f"wrong_{fp}"] for fp in ("close", "low")}
        k1["wrong_engines_fail"] = all(wb[f"wrong_{fp}"]["fails"] for fp in ("close", "low"))
    if target is not None:
        err = rate_errors(wb["rates_engine"], target)
        k1["K1b"]["fill_counts"] = dict(real_rates=target, synthetic=wb["rates_engine"], rel_error=err,
                                        within_25pct=bool(all(abs(v) <= K1B_TOL for v in err.values())))
    # K1c: the regime component (K1c minus its paired null K1c0), not K1c's own Delta (k1c_report)
    k1["K1c"] = k1c_report(specs["K1c"], worlds["K1c"]["k1c_table"], worlds["K1c0"]["k1c_table"],
                           worlds["K1c"]["compare"], worlds["K1c0"]["compare"])
    k1["K1d"] = dict(worlds["K1d"]["haircut"])
    k1["K1d"]["engine_matches_oracle"] = all(x["passed"] for x in worlds["K1d"]["compare"]["exits"].values())
    passed = k1["K1a"]["passed"] and k1["K1b"]["passed"] and k1["K1d"]["passed"]
    if wrong:
        passed &= k1["wrong_engines_fail"]
    if target is not None:
        passed &= k1["K1b"]["fill_counts"]["within_25pct"]
    k1["passed"] = bool(passed)
    k1["diagnostics"] = {n: dict(exact_ok=w["exact_ok"], bids=w["compare"]["bids"], fills=w["compare"]["fills"],
                                 alert=w["compare"].get("alert"), engine_twins=w.get("engine_twins"),
                                 audit=w["audit"], timings=w["timings"]) for n, w in worlds.items()}
    # ---- K2
    k2 = dict(worlds["K2"]["k2"])
    k2["passed"] = bool(all(k2[ex]["t_ok"] and k2[ex]["oracle_match"] for ex in ("FLIP", "FLIP_bot")))
    out.update(K1=k1, K2=k2, seconds=time.time() - t0, specs={k: asdict(v) for k, v in specs.items()})
    out["_worlds"] = worlds
    return out


# ============================================================================ real fill calendars (counts only)
P1_RULES_CAL = ("F1", "F2", "F3_1", "F3_3", "F3d_1", "F5")      # K3 calendar, K5 audit, K8 venue flags


def _cal_paths() -> dict:
    return {k: WORK / f"{k}.parquet" for k in ("p1_bids", "p1_fills", "h4_bids", "h4_fills")} | \
        {"meta": WORK / "calendars.json"}


def prefetch_venues(bids: pd.DataFrame, log=_say) -> dict:
    """V4's fetch rule (prereg §4): the index and perpetual 1m coin-months that hold a candidate day of a bid's life
    (stinkbid_data.index_fetch_days: the 1d index or spot low within 5% of L/(1 + s) or L), fetched into
    stinkbid_data's cache (checksum-verified; missing days recorded, never filled). Counts only."""
    b = pd.DataFrame({"coin": bids.coin.to_numpy(), "L": bids.L.to_numpy(float),
                      "live_from": pd.DatetimeIndex(bids.live_from.to_numpy(np.int64) * MIN_NS, tz="UTC"),
                      "live_to": pd.DatetimeIndex((bids.life_end.to_numpy(np.int64) - 1) * MIN_NS, tz="UTC")})
    t = time.time()
    cd = sbd.index_fetch_days(b)
    pairs = list(zip(cd.coin, cd.day))
    log(f"  venue prefetch: {len(cd)} candidate coin-days in {cd.coin.nunique() if len(cd) else 0} coins "
        f"({time.time() - t:.0f}s to find them)")
    out = dict(coin_days=len(cd))
    for kind in ("index", "perp"):
        t = time.time()
        st = sbd.fut_prefetch(kind, pairs) if pairs else pd.DataFrame()
        out[kind] = dict(coin_months=int(len(st)), missing_days=int(st.missing.sum()) if len(st) else 0,
                         errors=int((st.error != "").sum()) if len(st) else 0, seconds=time.time() - t)
    return out


# The calendars' key (review finding: calendars reused under older code or data): the code that builds them (the
# engine and the modules it imports for levels, data, clusters and MoneyLine), this module's calendar code and
# configurations, and the stamps of every data input they read under data/stinkbid/.
CAL_SOURCES = ("stinkbid_engine.py", "stinkbid_levels.py", "stinkbid_data.py", "stinkbid_stats.py", "moneyline_ref.py",
               "fetch_stinkbid_data.py")
CAL_INPUTS = ("ref/universes.parquet", "ref/ranks.parquet", "ref/segments.csv", "ref/last_minute.json",
              "ref/currency_pairs.json", "ref/um_contracts.csv", "ref/ages_quotes.csv", "d1_full_all.parquet",
              "d1_spot_all.parquet", "d1_full", "d1_spot", "h1_spot", "h1_spot_pre", "m1_spot", "metrics", "mark1h",
              "perp1h", "fut1m", "fut1d", "usd")


def _cal_cfg(step: str, venues: bool = True, jobs=None) -> dict:
    """The engine configuration of each calendar run (r0: the bids whose venue days are prefetched; p1: P1 under every
    calendar rule with C1 capacity, the USD index, the market-wide flag and MoneyLine; h4: the H4 program)."""
    c = dict(counts_only=True, verbose=False, audit="report")
    if jobs is not None:
        c["n_jobs"] = jobs
    if step == "r0":
        return dict(c, rules=("F1",), capacity="none", mw=False, ml=False)
    if step == "p1":
        return dict(c, rules=P1_RULES_CAL if venues else ("F1", "F2"), capacity="c1", usd=True, mw=True, ml=True)
    if step == "h4":
        return dict(c, rules=("F1",), capacity="none", mw=False, ml=False)
    raise ValueError(step)


def _stamp(root: Path, rels) -> str:
    """sha1 of (path, size, modification time) of every file of the inputs (directories recursively); a missing
    input is recorded as missing."""
    h = hashlib.sha1()
    for rel in rels:
        p = Path(root) / rel
        files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else ([p] if p.exists() else [])
        if not files:
            h.update(f"{rel}|missing\n".encode())
        for f in files:
            st = f.stat()
            h.update(f"{f.relative_to(root)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:16]


def calendar_key(venues: bool = True, root=None, sources=None, inputs=None) -> dict:
    """The key of the real fill calendars: {key, code, cfg, data}. code = sha256 of CAL_SOURCES (paths relative to
    analysis_2026/ or absolute) and of this module's calendar functions; cfg = the calendar runs' configurations;
    data = the stamps of CAL_INPUTS under `root` (default data/stinkbid/). real_calendars rebuilds the calendars when
    the key differs from the one stored with them (calendars.json)."""
    root = Path(root) if root is not None else sbd.OUT
    hc = hashlib.sha256()
    for f in (sources or CAL_SOURCES):
        p = Path(f) if Path(f).is_absolute() else ROOT / "analysis_2026" / f
        hc.update(p.read_bytes() if p.exists() else f"{f}|missing".encode())
    for fn in (real_calendars, _build_calendars, prefetch_venues, _cal_cfg):
        hc.update(_obj_sig(fn))
    code = hc.hexdigest()[:16]
    cfg = hashlib.sha1(json.dumps(_js(dict(steps={s: _cal_cfg(s, venues) for s in ("r0", "p1", "h4")},
                                          venues=bool(venues), rules=P1_RULES_CAL)), sort_keys=True).encode()
                       ).hexdigest()[:16]
    data = _stamp(root, inputs or CAL_INPUTS)
    return dict(key=hashlib.sha1(f"{code}|{cfg}|{data}".encode()).hexdigest()[:16], code=code, cfg=cfg, data=data)


def real_calendars(jobs: int = 4, force: bool = False, log=_say, venues: bool = True, build=None,
                   key_fn=None) -> dict:
    """The real fill calendars (counts only; §14 "fill counts before returns"): P1 on U-Q1 under F1, F2, F3 (s = 1%,
    3%), F3d (s = 1%) and F5 with C1 capacity and the K5 audit (bids, fills and venue flags are counts), and the H4
    program on U-Q1 under F1 (the real chart levels and their four placebos). Written under data/stinkbid/controls/
    with their key (calendar_key: code, configurations, data stamps) and reused only while the key is unchanged;
    force rebuilds (run(rebuild_calendars=True), CLI --rebuild-calendars). The key stored is computed after the build
    (the venue prefetch may add index / perpetual files). No outcome is computed (counts_only=True)."""
    P = _cal_paths()
    key_fn = key_fn or (lambda v: calendar_key(v))
    key = key_fn(venues)
    if not force and all(p.exists() for p in P.values()):
        meta = json.loads(P["meta"].read_text())
        if meta.get("key") == key["key"]:
            meta["reused"] = True
            log(f"  real calendars: reused (key {key['key']})")
            return meta
        old = meta.get("key_parts") or {}
        why = (", ".join(k for k in ("code", "cfg", "data") if old.get(k) != key[k]) + " changed since they were built"
               if "key" in meta else "built without a key")
        log(f"  real calendars: stale ({why}); rebuilding")
    elif force:
        log("  real calendars: rebuild forced")
    WORK.mkdir(parents=True, exist_ok=True)
    P["meta"].unlink(missing_ok=True)              # a crashed build never leaves a valid key behind
    meta = (build or _build_calendars)(jobs, log, venues)
    key = key_fn(venues)
    meta.update(key=key["key"], key_parts=key, built=pd.Timestamp.now(tz="UTC").isoformat(), reused=False)
    P["meta"].write_text(json.dumps(_js(meta), indent=1))
    return meta


def _build_calendars(jobs: int, log, venues: bool) -> dict:
    """real_calendars' build: the prefetch of venue days, then the P1 and H4 counts-only runs written to WORK."""
    P = _cal_paths()
    for k in ("p1", "h4"):
        (WORK / f"{k}_audit.parquet").unlink(missing_ok=True)       # rewritten below when the run has audit rows
    meta = {}
    t0 = time.time()
    if venues:
        r0 = sbe.run_program("P1", "U_Q1", cfg=_cal_cfg("r0", venues, jobs))
        meta["prefetch"] = prefetch_venues(r0["bids"], log)
        del r0
    t1 = time.time()
    rules = _cal_cfg("p1", venues)["rules"]
    r = sbe.run_program("P1", "U_Q1", cfg=_cal_cfg("p1", venues, jobs))
    meta["p1"] = dict(seconds=time.time() - t1, bids=len(r["bids"]), fills_F1=int((r["fills"].t_F1 >= 0).sum()),
                      audit=_audit_counts(r), rules=list(rules))
    r["bids"].to_parquet(P["p1_bids"])
    F = r["fills"].copy()
    for c in F.columns:
        if F[c].dtype == object:
            F[c] = F[c].astype(str)
    F.to_parquet(P["p1_fills"])
    if len(r["audit"]):
        A = r["audit"].copy()
        for c in A.columns:
            A[c] = A[c].astype(str)
        A.to_parquet(WORK / "p1_audit.parquet")
    log(f"  P1 calendar: {meta['p1']['bids']} bids, {meta['p1']['fills_F1']} F1 fills, audit "
        f"{meta['p1']['audit']} ({meta['p1']['seconds']:.0f}s)")
    del r
    t2 = time.time()
    r = sbe.run_program("H4", "U_Q1", cfg=_cal_cfg("h4", venues, jobs))
    meta["h4"] = dict(seconds=time.time() - t2, bids=len(r["bids"]), fills_F1=int((r["fills"].t_F1 >= 0).sum()),
                      audit=_audit_counts(r))
    r["bids"].to_parquet(P["h4_bids"])
    F = r["fills"].copy()
    for c in F.columns:
        if F[c].dtype == object:
            F[c] = F[c].astype(str)
    F.to_parquet(P["h4_fills"])
    if len(r["audit"]):
        A = r["audit"].copy()
        for c in A.columns:
            A[c] = A[c].astype(str)
        A.to_parquet(WORK / "h4_audit.parquet")
    log(f"  H4 calendar: {meta['h4']['bids']} bids, {meta['h4']['fills_F1']} F1 fills ({meta['h4']['seconds']:.0f}s)")
    meta["seconds"] = time.time() - t0
    return meta


def real_p1_rates() -> dict:
    """P1's real F1 fill rates per bid-week by rung (U-Q1), from the counts-only calendar."""
    P = _cal_paths()
    B = pd.read_parquet(P["p1_bids"], columns=["rung"])
    F = pd.read_parquet(P["p1_fills"], columns=["rung", "t_F1"])
    nb_ = B.groupby("rung").size()
    nf = F[F.t_F1 >= 0].groupby("rung").size()
    return {f"{k:g}": float(nf.get(k, 0) / nb_[k]) for k in nb_.index}


# ============================================================================ K3: inference on the real fill calendar
# Hourly synthetic martingale paths (build spec: hourly paths allowed for K3) on the REAL fill calendar: which coin,
# which minute, which level and target, which month-block and episode. Nothing after any fill is real. The path model
# is the draft's power model (§12.5, critique S7): market + idiosyncratic Student-t(4) shocks, a log-AR(1) volatility
# regime (phi 0.98, SD 0.09 a day), a crash-time volatility multiplier for CD days after each crash day (base 2x for
# 3 days, sigma_e 3%; high dispersion 3x for 7 days, sigma_e 4.5%), beta 1.1, market sigma 3% a day, Brownian-bridge
# hourly highs; hetero = base plus a mean-zero Student-t(3) effect of SD 3% per episode on the tested contrast.
K3_H0 = "2019-07-01"
K3_SC = {"base": dict(sig_e=0.030, cm=2.0, cd=3, hetero=False), "high": dict(sig_e=0.045, cm=3.0, cd=7, hetero=False),
         "hetero": dict(sig_e=0.030, cm=2.0, cd=3, hetero=True)}
K3_SIG_M, K3_BETA, K3_TW = 0.030, 1.1, 100
K3_STOP_M = 72 * 60
K3_CRASH_COINS = 3                                 # a crash day: P1 F1 fills in >= 3 distinct U-Q1 coins that day
_K3: dict = {}


def _hour_idx(minutes, h0_min: int, up: bool = True) -> np.ndarray:
    """Grid hour of minute times: the first hour boundary at or after (up) / the hour containing (down) each."""
    m = np.asarray(minutes, np.int64) - h0_min
    return ((m + 59) // 60 if up else m // 60).astype(np.int64)


def k3_setup(force: bool = False, universe: pd.DataFrame | None = None) -> Path:
    """The K3 calendar arrays (saved to data/stinkbid/controls/k3_setup.npz): P1's F1 fills (coin, fill hour, flip
    target ln(R1/2 / L), rule-M go-live and stop hours, month-block, episode) and H4's stacked fills per method (the
    same plus real flag, depth delta_f - delta_real,cw, coin-week, the one month-block partition of test_h4), each
    coin's eligible twin hours (U-Q1 member months, a complete window), rule M for every grid hour, crash days."""
    path = WORK / "k3_setup.pkl"
    if path.exists() and not force:
        return path
    import pickle
    P = _cal_paths()
    h0 = _tmin(K3_H0)
    end_min = _tmin(pd.Timestamp(END_DAY) + pd.Timedelta(days=1)) - 1
    n_h = (end_min + 1 - h0) // 60
    u = sbd.universes() if universe is None else universe
    q = u[u.U_Q1.astype(bool)]
    F1 = pd.read_parquet(P["p1_fills"])
    F1 = F1[F1.t_F1 >= 0].copy()
    H4f = pd.read_parquet(P["h4_fills"])
    H4f = H4f[H4f.t_F1 >= 0].copy()
    H4b = pd.read_parquet(P["h4_bids"])
    coins = sorted(set(F1.coin) | set(H4f.coin))
    cix = {c: i for i, c in enumerate(coins)}
    # rule M for every grid hour (twins enter at an hour's open) and the stop
    hm = h0 + 60 * np.arange(n_h + 1, dtype=np.int64)
    g_h = _hour_idx(rule_m_oracle(hm), h0)
    s_h = _hour_idx(rule_m_oracle(hm + K3_STOP_M), h0)
    # eligible twin hours per coin: member month, stop inside the grid
    mon = (hm[:n_h] // DAY_M).astype("datetime64[D]").astype("datetime64[M]").astype(str)
    elig = {}
    for c in coins:
        mm = set(q.month[q.coin == c].astype(str))
        ok = np.isin(mon, list(mm)) & (s_h[:n_h] < n_h)
        elig[c] = np.flatnonzero(ok).astype(np.int64)

    def positions(df):
        m = df.t_F1.to_numpy(np.int64)
        L = df.L.to_numpy(float)
        P0 = df.P0.to_numpy(float)
        R = np.array([sbl.ceil_tick(l_ + 0.5 * (p_ - l_), ts) for l_, p_, ts in zip(L, P0, df.tick_str.astype(str))])
        hf = _hour_idx(m, h0, up=False)
        g = np.maximum(_hour_idx(rule_m_oracle(m), h0), hf + 1)
        S = _hour_idx(rule_m_oracle(m + K3_STOP_M), h0)
        ok = (S < n_h) & np.isfinite(R) & (R > 0)
        return dict(coin=np.array([cix[c] for c in df.coin]), hf=hf, g=g, S=S, tgt=np.log(R / L), ok=ok, m=m)

    p1 = positions(F1)
    keep = p1["ok"]
    F1 = F1[keep].reset_index(drop=True)
    p1 = {k: v[keep] for k, v in p1.items()}
    t1 = pd.to_datetime(F1.t_F1.to_numpy(np.int64) * MIN_NS, utc=True)
    p1["mb"] = sbs.month_blocks(t1)[0]
    p1["ep"] = sbs.episodes(t1)[0]
    p1["half"] = sbs.half_key(t1)
    # crash days for the volatility multiplier
    day = F1.t_F1.to_numpy(np.int64) // DAY_M
    nco = pd.DataFrame({"d": day, "c": F1.coin}).groupby("d").c.nunique()
    crash_days = nco[nco >= K3_CRASH_COINS].index.to_numpy(np.int64)
    # H4 stacked fills per method (the real level's fill and its placebos' fills, same coin-week)
    names = dict(sbe.H4_NAMES)
    H4f["meth"] = H4f.variant.map(names)
    real_d = H4b[H4b.real.astype(bool)][["variant", "cw", "delta"]].rename(columns={"delta": "delta_real"})
    H4f = H4f.merge(real_d, on=["variant", "cw"], how="left")
    H4f = H4f[H4f.meth.isin(sbs.H4_METHODS) & np.isfinite(H4f.delta_real.to_numpy(float))].reset_index(drop=True)
    p4 = positions(H4f)
    keep = p4["ok"]
    H4f = H4f[keep].reset_index(drop=True)
    p4 = {k: v[keep] for k, v in p4.items()}
    t4 = pd.to_datetime(H4f.t_F1.to_numpy(np.int64) * MIN_NS, utc=True)
    p4["cluster"] = sbs.month_blocks(t4)[0]                      # one partition shared by the four methods
    p4["ep"] = sbs.episodes(t4)[0]
    p4["meth"] = H4f.meth.to_numpy()
    p4["real"] = H4f.real.astype(bool).to_numpy()
    p4["depth"] = (H4f.delta - H4f.delta_real).to_numpy(float)
    p4["cw"] = H4f.cw.astype(str).to_numpy()
    S = dict(h0=h0, n_h=n_h, coins=coins, elig=elig, g_h=g_h, s_h=s_h, crash_days=crash_days, p1=p1, p4=p4,
             day0=h0 // DAY_M)
    with open(path, "wb") as fh:
        pickle.dump(S, fh)
    return path


def _k3_load() -> dict:
    if "S" not in _K3:
        import pickle
        p = Path(os.environ.get("SB_K3_SETUP", str(WORK / "k3_setup.pkl")))
        with open(p, "rb") as fh:
            S = pickle.load(fh)
        # per position: twin draw structure (own eligible hours outside +-182 days, else pooled)
        X = 182 * 24
        cdays = {}
        for c in S["coins"]:
            e = S["elig"][c]
            d = e // 24
            cdays[c] = np.r_[0, np.cumsum(np.r_[True, d[1:] != d[:-1]] if len(d) else np.zeros(0, bool))]
        for key in ("p1", "p4"):
            pp = S[key]
            n = len(pp["coin"])
            i0 = np.zeros(n, np.int64)
            i1 = np.zeros(n, np.int64)
            pooled = np.zeros(n, bool)
            for j in range(n):
                c = S["coins"][pp["coin"][j]]
                e = S["elig"][c]
                a = int(np.searchsorted(e, pp["hf"][j] - X, side="left"))
                b = int(np.searchsorted(e, pp["hf"][j] + X, side="right"))
                i0[j], i1[j] = a, b
                cd = cdays[c]
                days = int(cd[a]) + int(cd[len(e)] - cd[b]) + (1 if 0 < b < len(e) and e[b] // 24 == e[b - 1] // 24
                                                                else 0)
                pooled[j] = days < 182 or len(e) == 0 or (a + len(e) - b) == 0
            pp["i0"], pp["i1"], pp["pooled"] = i0, i1, pooled
        allh = [(ci, S["elig"][c]) for ci, c in enumerate(S["coins"])]
        pc = np.concatenate([np.full(len(h), ci, np.int64) for ci, h in allh])
        ph = np.concatenate([h for _, h in allh])
        o = np.argsort(ph, kind="stable")
        S["pool_c"], S["pool_h"] = pc[o], ph[o]
        _K3["S"] = S
    return _K3["S"]


@nb.njit(cache=True)
def _k3_exit(X, HI, c, xe, g, S, tgt):
    """Hourly flip / hold exits: the sell is live from the open of hour g; marketable if that open is at or above the
    target; else the first hour in [g, S) whose high reaches it sells at the target; else the open of hour S.
    tgt = inf is a hold. Returns the exit log price."""
    n = c.size
    out = np.empty(n)
    for p in range(n):
        ci = c[p]
        T = xe[p] + tgt[p]
        gp, sp = g[p], S[p]
        if X[ci, gp] >= T:
            out[p] = X[ci, gp]
            continue
        v = X[ci, sp]
        if np.isfinite(T):
            for j in range(gp, sp):
                if HI[ci, j] >= T:
                    v = T
                    break
        out[p] = v
    return out


def _k3_paths(S: dict, sc: dict, rng):
    """Hourly log prices X (coins x (n_h + 1)) and highs HI (coins x n_h) of one replication."""
    n_h = S["n_h"]
    nd = n_h // 24 + 2
    x = np.empty(nd)
    e = rng.normal(0.0, 0.09, nd)
    sd = 0.09 / math.sqrt(1 - 0.98 ** 2)
    x[0] = rng.normal(0.0, sd)
    for i in range(1, nd):
        x[i] = 0.98 * x[i - 1] + e[i]
    v_d = np.exp(x - sd ** 2)
    mult = np.ones(nd)
    for d in S["crash_days"] - S["day0"]:
        if 0 <= d < nd:
            mult[d:d + sc["cd"]] = sc["cm"]
    v = (v_d * mult)[np.arange(n_h) // 24]
    s_m = K3_SIG_M / math.sqrt(24) * v
    s_e = sc["sig_e"] / math.sqrt(24) * v
    var = (K3_BETA * s_m) ** 2 + s_e ** 2
    mk = K3_BETA * s_m * _t4(rng, n_h)
    nc = len(S["coins"])
    X = np.empty((nc, n_h + 1))
    HI = np.empty((nc, n_h))
    for i in range(nc):
        r = mk + s_e * _t4(rng, n_h) - 0.5 * var
        X[i, 0] = 0.0
        np.cumsum(r, out=X[i, 1:])
        a, b = X[i, :-1], X[i, 1:]
        HI[i] = 0.5 * (a + b + np.sqrt((a - b) ** 2 - 2.0 * var * np.log(rng.random(n_h))))
    return X, HI


def _k3_twins(S: dict, pp: dict, rng):
    """100 twin entry hours per position (own coin's eligible hours outside +-182 days; pooled when fewer than 182
    eligible days remain): (coin, hour) arrays of shape (n, 100). Vectorised over positions."""
    n = len(pp["coin"])
    u = rng.random((n, K3_TW))
    X = 182 * 24
    if "E_all" not in S:
        lens = np.array([len(S["elig"][c]) for c in S["coins"]], np.int64)
        S["E_off"] = np.r_[0, np.cumsum(lens)[:-1]]
        S["E_len"] = lens
        S["E_all"] = np.concatenate([S["elig"][c] for c in S["coins"]]) if lens.sum() else np.zeros(0, np.int64)
    c = pp["coin"]
    nL = pp["i0"]
    nR = S["E_len"][c] - pp["i1"]
    tot = np.maximum(nL + nR, 1)
    k = np.minimum((u * tot[:, None]).astype(np.int64), (tot - 1)[:, None])
    base = S["E_off"][c][:, None]
    idx = np.where(k < nL[:, None], base + k, base + pp["i1"][:, None] + k - nL[:, None])
    idx = np.clip(idx, 0, max(len(S["E_all"]) - 1, 0))
    H = S["E_all"][idx] if len(S["E_all"]) else np.zeros((n, K3_TW), np.int64)
    C = np.repeat(c[:, None], K3_TW, axis=1)
    pj = np.flatnonzero(pp["pooled"])
    if len(pj):
        ph, pc = S["pool_h"], S["pool_c"]                             # sorted by hour
        a = np.searchsorted(ph, pp["hf"][pj] - X, side="left")
        b = np.searchsorted(ph, pp["hf"][pj] + X, side="right")
        nL2, nR2 = a, len(ph) - b
        tot2 = np.maximum(nL2 + nR2, 1)
        k2 = np.minimum((u[pj] * tot2[:, None]).astype(np.int64), (tot2 - 1)[:, None])
        i2 = np.where(k2 < nL2[:, None], k2, b[:, None] + k2 - nL2[:, None])
        H[pj], C[pj] = ph[i2], pc[i2]
    return C, H


def _k3_delta(S, X, HI, pp, rng):
    """Per position: r_f (C-RH) of the flip from the fill, the mean of its 100 twins, Delta = r_f - twin mean, and the
    B-ALERT advantage a_f (the open at the rule-M hour against the price at the fill)."""
    k = (1 - C_RH) / (1 + C_RH)
    c = pp["coin"]
    xe = X[c, pp["hf"] + 1]
    ex = _k3_exit(X, HI, c, xe, pp["g"], pp["S"], pp["tgt"])
    r_f = np.exp(ex - xe) * k - 1.0
    TC, TH = _k3_twins(S, pp, rng)
    tc, th = TC.ravel(), TH.ravel()
    xt = X[tc, th]
    et = _k3_exit(X, HI, tc, xt, S["g_h"][th], S["s_h"][th], np.repeat(pp["tgt"], K3_TW))
    r_t = (np.exp(et - xt) * k - 1.0).reshape(-1, K3_TW).mean(axis=1)
    a_f = np.exp(X[c, pp["g"]] - xe) - 1.0
    return r_f - r_t, a_f, r_f


def k3_sim(scenario: str, rep: int, rng) -> dict:
    """K3's sim_fn for stinkbid_stats.inference_calibration: one null replication of H1 (Delta_f), H2R (a_f) and H4
    (per-method stacked Delta_f) on the real fill calendar. Caches the per-fill values of the first SB_K3_POWER
    replications of each scenario for the power re-run."""
    S = _k3_load()
    sc = K3_SC[scenario]
    X, HI = _k3_paths(S, sc, rng)
    p1, p4 = S["p1"], S["p4"]
    d1, a1, _ = _k3_delta(S, X, HI, p1, rng)
    d4, _, _ = _k3_delta(S, X, HI, p4, rng)
    del X, HI
    if sc["hetero"]:
        def eff(ep):
            u_ = np.unique(ep)
            z = 0.03 * rng.standard_t(3, size=len(u_)) / math.sqrt(3.0)
            return z[np.searchsorted(u_, ep)]
        d1 = d1 + eff(p1["ep"])
        a1 = a1 + eff(p1["ep"])
        d4 = d4 + np.where(p4["real"], eff(p4["ep"]), 0.0)
    meth = {}
    for m_ in sbs.H4_METHODS:
        s_ = p4["meth"] == m_
        meth[m_] = pd.DataFrame({"y": d4[s_], "real": p4["real"][s_], "depth": p4["depth"][s_], "cw": p4["cw"][s_],
                                 "cluster": p4["cluster"][s_]})
    n_pow = int(os.environ.get("SB_K3_POWER", "0"))
    if rep < n_pow:
        cd = Path(os.environ.get("SB_K3_CACHE", str(WORK / "k3_cache")))
        cd.mkdir(parents=True, exist_ok=True)
        np.savez(cd / f"{scenario}_{rep:05d}.npz", d1=d1, a1=a1, d4=d4)
    return {"H1": {"y": d1, "clusters": p1["mb"], "truth": 0.0},
            "H2R": {"y": a1, "clusters": p1["mb"], "truth": 0.0},
            "H4": {"methods": meth, "truth": 0.0}}


# K3 power re-run (S18): effects added to the cached null values of the same replications
POWER_GRID = {"H1": (0.0, 0.02, 0.0375, 0.05, 0.06, 0.08), "H2R": (0.0, 0.01, 0.02, 0.03),
              "H4": (0.0, 0.01, 0.02, 0.03)}            # 0.0: the null itself (size and NO EDGE reachability)
POWER_CONC = {"H1": 0.05, "H2R": 0.03}            # an edge confined to the 10 / 3 largest episodes (critique 2.3)


def _pw_row(r: dict, h4: bool = False) -> dict:
    """What the power re-run keeps of one test result: the nominal p_decide and bound, and what the simulation-
    calibrated rule needs (the statistic, estimate and SE; per method for H4)."""
    if h4:
        tab = r["methods"]
        return dict(p=r["p_decide"], ub=r["ub"], stat=r["T"], n_bonf=r.get("n_bonf"),
                    methods=tab["method"].astype(str).tolist(), b=tab["b"].to_numpy(float).tolist(),
                    se=tab["se"].to_numpy(float).tolist(), ubm=tab["ub"].to_numpy(float).tolist())
    return dict(p=r["p_decide"], ub=r["ub"], stat=r["t"], est=r["estimate"], se=r["se"])


def _pw_decide(test: str, x: dict, calib: dict) -> tuple:
    """(p, bound, rule) of one power row under the rule K3 assigns the test (§10.5): nominal, or, when K3 failed for
    it, the simulation-calibrated p and the widened NO EDGE bound (stinkbid_stats.apply_calibration, as the primary
    stage applies them)."""
    if not calib["tests"].get(test, {}).get("needs_calibration", False):
        return x["p"], x["ub"], "nominal"
    if test == "H4":
        row = dict(p_decide=x["p"], ub=x["ub"], T=x["stat"], n_bonf=x.get("n_bonf") or len(x["methods"]),
                   E=E_TESTS[test], methods=pd.DataFrame({"method": x["methods"], "b": x["b"], "se": x["se"],
                                                          "ub": x["ubm"]}))
    else:
        row = dict(p_decide=x["p"], ub=x["ub"], t=x["stat"], estimate=x["est"], se=x["se"], E=E_TESTS[test])
    r = sbs.apply_calibration(row, test, calib)
    return r["p_decide"], r["ub"], "simulation-calibrated"


def _calib_crit(test: str, calib: dict, alpha: float) -> float:
    """The critical statistic of the simulation-calibrated rule at level alpha: calibrated_p(s) < alpha needs, in
    every scenario, at most m = ceil(alpha (n + 1) - 1) - 1 null statistics at or above s, i.e. s above the (m + 1)-th
    largest; the largest of these over the scenarios (inf when n is too small for alpha)."""
    crit = -np.inf
    for d in calib["null"][test].values():
        st = np.sort(np.asarray(d["stat"], float)[np.isfinite(np.asarray(d["stat"], float))])[::-1]
        m = math.ceil(alpha * (len(st) + 1) - 1) - 1
        crit = max(crit, float(st[m]) if 0 <= m < len(st) else np.inf)
    return float(crit)


def _power_task(args):
    files, B = args
    S = _k3_load()
    p1, p4 = S["p1"], S["p4"]
    ep_sizes = pd.Series(p1["ep"]).value_counts()
    top10 = np.isin(p1["ep"], ep_sizes.index[:10])
    top3 = np.isin(p1["ep"], ep_sizes.index[:3])
    out = []
    for f in files:
        z = np.load(f)
        sc = Path(f).stem.rsplit("_", 1)[0]
        rec = dict(scenario=sc, file=Path(f).name)
        rng = np.random.default_rng(int(hashlib.sha1(Path(f).name.encode()).hexdigest()[:8], 16))
        W = sbs.webb_weights(B, len(np.unique(p1["mb"])), rng)
        for test, y0 in (("H1", z["d1"]), ("H2R", z["a1"])):
            for eff in POWER_GRID[test]:
                r = sbs.test_mean(y0 + eff, p1["mb"], B=B, W=W)
                rec[f"{test}|const|{eff}"] = _pw_row(r)
            for nm, msk in (("top10", top10), ("top3", top3)):
                r = sbs.test_mean(y0 + POWER_CONC[test] * msk, p1["mb"], B=B, W=W)
                rec[f"{test}|{nm}|{POWER_CONC[test]}"] = _pw_row(r)
        d4 = z["d4"]
        for eff in POWER_GRID["H4"]:
            for scope in ("M4", "all"):
                y = d4 + eff * (p4["real"] & ((p4["meth"] == "M4") if scope == "M4" else True))
                meth = {m_: pd.DataFrame({"y": y[p4["meth"] == m_], "real": p4["real"][p4["meth"] == m_],
                                          "depth": p4["depth"][p4["meth"] == m_], "cw": p4["cw"][p4["meth"] == m_],
                                          "cluster": p4["cluster"][p4["meth"] == m_]}) for m_ in sbs.H4_METHODS}
                r = sbs.test_h4(meth, B=B, seed=rng)
                rec[f"H4|{scope}|{eff}"] = _pw_row(r, h4=True)
        out.append(rec)
    return out


def k3_power(calib: dict, jobs: int = 4, B: int = sbs.B_BOOT) -> dict:
    """The power re-run (S18) on the corrected machinery, each test under the rule K3 assigns it (§10.5: a test whose
    K3 rates fail the 1.5x rule is decided by its simulation-calibrated p and widened bound; rule per test in 'rule'
    and on every row): per test and scenario, the MDE (formula: median over the null replications of (c +
    t_{0.80, G*-1}) SE, with c = t_{1-0.05/3, G*-1} under the nominal rule and the calibrated rule's critical statistic
    at 0.05/3 otherwise (mde_rule; the nominal mde_formula kept beside it); empirical: the same with the SD of the
    estimates), the NO EDGE reachability under the null (share of null replications whose 98.33% bound is below E),
    and power (the share rejected at 0.05/3, Holm's first step, and at 0.05) at constant true effects and at edges
    confined to the 10 and the 3 largest episodes (P1; critique 2.3), from the cached null values of the first
    replications; the nominal rule's rates are kept beside a calibrated test's (*_nominal)."""
    files = sorted(str(p) for p in Path(os.environ.get("SB_K3_CACHE", str(WORK / "k3_cache"))).glob("*.npz"))
    rules = {t: ("simulation-calibrated" if d.get("needs_calibration") else "nominal") for t, d in calib["tests"].items()}
    out = {"rule": rules, "mde": {}, "noedge_reachable_null": {}, "power": {}, "n_reps_power": {}}
    q80 = lambda g: float(sps.t.ppf(0.80, g - 1)) if np.isfinite(g) and g > 1 else np.nan
    for test, d in calib["tests"].items():
        crit = _calib_crit(test, calib, sbs.ALPHA_B) if rules[test] != "nominal" else np.nan
        out["mde"][test] = {}
        for s, v in d["by_scenario"].items():
            g = v["gstar_median"]
            se_med = float(np.nanmedian(np.asarray(calib["null"][test][s]["se"], float))) if calib.get("null") else \
                v["se_mean"]
            row = dict(rule=rules[test], mde_formula=v["mde_formula"], mde_empirical=v["mde_empirical"],
                       se_mean=v["se_mean"], est_sd=v["est_sd"], gstar_median=g,
                       crit_nominal=float(sps.t.ppf(1 - sbs.ALPHA_B, g - 1)) if np.isfinite(g) and g > 1
                       else np.nan)
            if rules[test] != "nominal":
                row.update(crit_calibrated=crit, mde_calibrated=(crit + q80(g)) * se_med,
                           mde_calibrated_empirical=(crit + q80(g)) * v["est_sd"])
            row["mde_rule"] = row.get("mde_calibrated", row["mde_formula"])
            out["mde"][test][s] = row
    if not files:
        return out
    recs = [r for part in _pmap(_power_task, [(ch, B) for ch in _chunks(files, jobs * 4)], jobs) for r in part]
    df = pd.DataFrame(recs)
    for sc, g in df.groupby("scenario"):
        out["n_reps_power"][sc] = int(len(g))
        for col in [c for c in df.columns if "|" in c]:
            test, kind, eff = col.split("|")
            dec = [_pw_decide(test, x, calib) for x in g[col]]
            p = np.array([x[0] for x in dec], float)
            ub = np.array([x[1] for x in dec], float)
            row = dict(kind=kind, effect=float(eff), rule=rules[test], reject_alpha3=float(np.mean(p < sbs.ALPHA / 3)),
                       reject_05=float(np.mean(p < sbs.ALPHA)), noedge=float(np.mean(ub < E_TESTS[test])))
            if rules[test] != "nominal":
                pn = np.array([x["p"] for x in g[col]], float)
                un = np.array([x["ub"] for x in g[col]], float)
                row.update(reject_alpha3_nominal=float(np.mean(pn < sbs.ALPHA / 3)),
                           reject_05_nominal=float(np.mean(pn < sbs.ALPHA)),
                           noedge_nominal=float(np.mean(un < E_TESTS[test])))
            out["power"].setdefault(test, {}).setdefault(sc, []).append(row)
            if float(eff) == 0.0 and kind in ("const", "all"):
                out["noedge_reachable_null"].setdefault(test, {})[sc] = row["noedge"]
    return out


def run_k3(n_reps: int = K3_REPS, jobs: int = 4, n_power: int = 300, B: int = sbs.B_BOOT, log=_say,
           scenarios=K3_SCENARIOS, universe: pd.DataFrame | None = None) -> dict:
    """K3 (§10.5): >= 2,000 null replications per scenario (base, high dispersion, heterogeneous-effect null) on the
    real fill calendar, through stinkbid_stats.inference_calibration (the decisive machinery: p = max(p_WCR, p_G*),
    B = 9,999, the 98.33% NO EDGE bound): false-PASS rates at 1.67%, 2.5% and 5% and the NO EDGE miss rate for H1,
    H2R and H4 with Clopper-Pearson intervals; pass when each upper end is at most 1.5x nominal, else that test's
    p becomes its simulation-calibrated p (worst scenario) and its bound the simulated quantile. Plus the power
    re-run (S18) and D11's null distribution. Returns (summary, calib, power, d11 frame)."""
    t0 = time.time()
    path = k3_setup(force=True, universe=universe)
    os.environ["SB_K3_SETUP"] = str(path)
    os.environ["SB_K3_POWER"] = str(int(n_power))
    os.environ["SB_K3_CACHE"] = str(WORK / "k3_cache")
    _K3.clear()
    cd = WORK / "k3_cache"
    if cd.exists():
        for f in cd.glob("*.npz"):
            f.unlink()
    S = _k3_load()
    log(f"K3: {len(S['p1']['coin'])} P1 fills ({len(np.unique(S['p1']['mb']))} month-blocks), "
        f"{len(S['p4']['coin'])} H4 stacked fills, {len(S['coins'])} coins, {len(S['crash_days'])} crash days; "
        f"{n_reps} replications x {len(scenarios)} scenarios, B = {B}")
    calib = sbs.inference_calibration(k3_sim, n_reps=n_reps, scenarios=tuple(scenarios), B=B, n_jobs=jobs,
                                      keep_null=True)
    t1 = time.time()
    log(f"  K3 null replications: {t1 - t0:.0f}s")
    power = k3_power(calib, jobs, B)
    power["seconds"] = time.time() - t1
    rows = []
    for s, d in calib.get("null", {}).get("H1", {}).items():
        for i, (tot, est, se, st) in enumerate(zip(d["total"], d["est"], d["se"], d["stat"])):
            rows.append(dict(scenario=s, rep=i, total=tot, mean=est, se=se, t=st, n=len(S["p1"]["coin"])))
    d11 = pd.DataFrame(rows)
    summ = {"n_reps": n_reps, "B": B, "scenarios": list(scenarios), "all_nominal_ok": calib["all_pass"],
            "seconds": time.time() - t0, "tests": {}}
    for test, d in calib["tests"].items():
        summ["tests"][test] = dict(rule=d["rule"], k3_nominal_ok=d["k3_pass"], worst_scenario=d["worst_scenario"],
                                   by_scenario={s: dict(false_pass={lv: dict(rate=x["rate"], ci95=x["ci95"],
                                                                             limit=x["limit"], ok=x["ok"])
                                                                    for lv, x in v["false_pass"].items()},
                                                        noedge_miss=dict(rate=v["noedge_miss"]["rate"],
                                                                         ci95=v["noedge_miss"]["ci95"],
                                                                         limit=v["noedge_miss"]["limit"],
                                                                         ok=v["noedge_miss"]["ok"]),
                                                        est_mean=v["est_mean"], mde_formula=v["mde_formula"],
                                                        gstar_median=v["gstar_median"])
                                                for s, v in d["by_scenario"].items()})
    summ["passed"] = bool(all(min(len(v["null"][t][s]["stat"]) for s in scenarios) >= K3_REPS
                              for t in calib["null"] for v in [calib])) if n_reps >= K3_REPS else False
    return summ, calib, power, d11


# ============================================================================ K4 / K4b: look-ahead (§10.5)
@dataclass(frozen=True)
class Pert:
    """A K4 perturbation at cut minute t: 'scale' (every price from t on x 1.5, every volume and open interest x 0.5,
    every coin and series), 'delete' (every bar of `coin` from t on removed: it stops trading at t), 'gap' (the bars
    of `coin` in [t, t + 3 days) removed: a 3-day gap after the cut); 'none' is the base world."""
    mode: str = "none"
    t: int = 0
    coin: str = ""
    leak: bool = False                     # selftest: a planted look-ahead (the minute before the cut sees ahead)


PRICE_COLS = ("open", "high", "low", "close")
VOL_COLS = ("volume", "quote_volume", "taker_buy_quote")


def _pert_frame(k: pd.DataFrame, pert: Pert, coin: str, tcol: str = "open_time", price=PRICE_COLS, vol=VOL_COLS,
                oi=()) -> pd.DataFrame:
    if k is None or pert.mode == "none" or not len(k):
        return k
    tm = _tmin(k[tcol])
    if pert.mode == "scale":
        k = k.copy()
        after = tm >= pert.t
        for c in price:
            if c in k:
                k[c] = np.where(after, k[c].to_numpy(float) * 1.5, k[c].to_numpy(float))
        for c in tuple(vol) + tuple(oi):
            if c in k:
                k[c] = np.where(after, k[c].to_numpy(float) * 0.5, k[c].to_numpy(float))
        return k
    if coin != pert.coin:
        return k
    if pert.mode == "delete":
        return k[tm < pert.t].reset_index(drop=True)
    if pert.mode == "gap":
        return k[(tm < pert.t) | (tm >= pert.t + 3 * DAY_M)].reset_index(drop=True)
    raise ValueError(pert.mode)


def _daily_bars(m1: pd.DataFrame) -> pd.DataFrame:
    """UTC daily bars from 1m bars with trades > 0 (the panel rows of a synthetic coin)."""
    k = m1[m1.trades.to_numpy() > 0]
    t = _tmin(k.open_time)
    day = t // DAY_M
    ud, st = np.unique(day, return_index=True)
    en = np.r_[st[1:], len(day)] - 1
    return pd.DataFrame({"open_time": pd.DatetimeIndex(ud * DAY_M * MIN_NS, tz="UTC"),
                         "open": k.open.to_numpy(float)[st], "high": np.maximum.reduceat(k.high.to_numpy(float), st),
                         "low": np.minimum.reduceat(k.low.to_numpy(float), st), "close": k.close.to_numpy(float)[en],
                         "volume": np.add.reduceat(k.volume.to_numpy(float), st),
                         "quote_volume": np.add.reduceat(k.quote_volume.to_numpy(float), st),
                         "trades": np.add.reduceat(k.trades.to_numpy(np.int64), st)})


_PANEL: dict = {}


class K4Market(SynthMarket):
    """The K4 synthetic world: SynthMarket coins with index and perpetual series, M7's inputs (5-minute open interest,
    1h mark and perpetual bars) and M3 / M8's pooled daily panel (the coins plus daily-only pairs), all derived from
    the minute paths after the perturbation, so that a perturbation reaches every series the way it would reach the
    archive files."""

    def __init__(self, spec: SynthSpec, pert: Pert = Pert()):
        super().__init__(spec)
        self.pert = pert

    def raw(self, coin: str) -> dict:
        fr = SynthMarket.frames(self, coin)
        fr["m1"] = _pert_frame(fr["m1"], self.pert, coin)
        if self.pert.leak:
            # a planted look-ahead: the low of the hour before the cut is pulled down to half the next day's mean
            # close, as code reading the future would do; base and perturbed futures differ, so K4 must see it
            k = fr["m1"].copy()
            tm = _tmin(k.open_time)
            fut = k.close.to_numpy(float)[(tm >= self.pert.t) & (tm < self.pert.t + DAY_M)]
            if len(fut):
                w = (tm >= self.pert.t - 60) & (tm < self.pert.t)
                k["low"] = np.where(w, np.minimum(k.low.to_numpy(float), 0.5 * fut.mean()), k.low.to_numpy(float))
                fr["m1"] = k
        if "index_m1" in fr:
            fr["index_m1"] = _pert_frame(fr["index_m1"], self.pert, coin, vol=())
        if "perp_m1" in fr:
            fr["perp_m1"] = _pert_frame(fr["perp_m1"], self.pert, coin)
        return fr

    def frames(self, coin: str, perturb=None) -> dict:
        fr = self.raw(coin)
        lv = self._m7(coin, fr.get("perp_m1"))
        lv.update(self.panel())
        fr["levels"] = lv
        return fr

    def _m7(self, coin: str, perp) -> dict:
        if perp is None or not len(perp):
            return {}
        i = self.coins.index(coin)
        rng = np.random.default_rng([self.spec.seed, 6, i])
        t = _tmin(perp.open_time)
        h = t // 60
        hu, st = np.unique(h, return_index=True)
        ot = pd.DatetimeIndex(hu * 60 * MIN_NS, tz="UTC")
        mark = pd.DataFrame({"open_time": ot, "low": np.minimum.reduceat(perp.low.to_numpy(float), st)})
        p1h = pd.DataFrame({"open_time": ot, "volume": np.add.reduceat(perp.volume.to_numpy(float), st),
                            "quote_volume": np.add.reduceat(perp.quote_volume.to_numpy(float), st)})
        g = _market_globals(self.spec)
        t5 = np.arange(g["t0"] + 5, g["t0"] + g["N"], 5, dtype=np.int64)          # fixed grid, unperturbed path
        lo = np.cumsum(rng.normal(0.0, 0.004, len(t5)))
        ev = g["ev_t"]
        if len(ev):
            k = np.searchsorted(t5, ev)
            drops = np.zeros(len(t5))
            ok = k < len(t5)
            np.add.at(drops, k[ok], rng.uniform(0.05, 0.25, int(ok.sum())))
            lo -= np.cumsum(drops)
        met = pd.DataFrame({"create_time": pd.DatetimeIndex(t5 * MIN_NS, tz="UTC"), "oi": 1e6 * np.exp(lo)})
        met = met[_tmin(met.create_time) <= t[-1] + 5]
        met = _pert_frame(met, self.pert, coin, tcol="create_time", price=(), vol=(), oi=("oi",))
        return {"metrics": met, "mark1h": mark, "perp1h": p1h}

    def panel(self) -> dict:
        key = (self.spec.key(), self.pert)
        if key in _PANEL:
            return _PANEL[key]
        rows = []
        for c in self.coins:
            d = _daily_bars(self.raw(c)["m1"])
            d["coin"] = c
            rows.append(d)
        # daily-only pairs (M3's pool and M8's market-wide days): daily t(4) returns with the market's jump days
        g = _market_globals(self.spec)
        days = np.arange(g["D"])
        ev_d = (g["ev_t"] - g["t0"]) // DAY_M
        for j in range(self.spec.panel_extra):
            rng = np.random.default_rng([self.spec.seed, 7, j])
            sd = rng.uniform(0.03, 0.06)
            r = sd * g["v_day"] * _t4(rng, len(days)) - 0.5 * (sd * g["v_day"]) ** 2
            if len(ev_d):
                np.add.at(r, ev_d, -rng.uniform(4, 14, len(ev_d)) * sd)
            c = 10.0 * np.exp(np.cumsum(r))
            o = np.r_[10.0, c[:-1]]
            hi = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, sd / 2, len(days))))
            lo_ = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, sd / 2, len(days))))
            d = pd.DataFrame({"open_time": pd.DatetimeIndex((g["t0"] + days * DAY_M) * MIN_NS, tz="UTC"), "open": o,
                              "high": hi, "low": lo_, "close": c, "volume": np.full(len(days), 1e5),
                              "quote_volume": c * 1e5, "trades": np.full(len(days), 1000), "coin": f"X{j:02d}"})
            if self.pert.mode == "scale":
                dm = _tmin(d.open_time)
                after = dm >= self.pert.t
                cut_day = (dm < self.pert.t) & (dm + DAY_M > self.pert.t)
                for col in ("high", "close"):
                    d[col] = np.where(after | cut_day, d[col] * 1.5, d[col])
                for col in ("open", "low"):
                    d[col] = np.where(after, d[col] * 1.5, d[col])
                for col in ("volume", "quote_volume"):
                    d[col] = np.where(after | cut_day, d[col] * 0.5, d[col])
            rows.append(d)
        P = pd.concat(rows, ignore_index=True)
        P["excluded"] = ""
        months = pd.period_range(pd.Timestamp(self.spec.start), pd.Timestamp(self.spec.end), freq="M").strftime("%Y-%m")
        coins = sorted(P.coin.unique())
        univ = pd.DataFrame([dict(month=m, coin=c, U_B=True, U_Q1=c in self.coins) for m in months for c in coins])
        back = pd.DataFrame([dict(month=m, coin=c, excluded=False) for m in months for c in coins])
        out = {"panel": P, "backstop": back, "univ": univ}
        if len(_PANEL) > 6:
            _PANEL.clear()
        _PANEL[key] = out
        return out

    def world(self) -> dict:
        months = pd.period_range(pd.Timestamp(self.spec.start) + pd.Timedelta(days=45), pd.Timestamp(self.spec.end),
                                 freq="M").strftime("%Y-%m")
        u = pd.DataFrame([dict(month=m, coin=c, U_Q1=True, U_B=True) for c in self.coins for m in months])
        return {"universe": u, "coins": self, "end": self.spec.end, "tbill": 0.0}


def k4_spec(rate: float = K1B_JUMP_RATE) -> SynthSpec:
    """The K4 world: 3 coins, 2021-03..2022-10 (M7 from 2021-12, M4's 365-day look-back from 2022-03), index and
    perpetual series, M7's inputs and a pooled panel of 13 pairs; jumps as K1b's; segments derived by the engine."""
    return SynthSpec(name="K4", n_coins=3, start="2021-03-01", end="2022-10-31", seed=SEED + 400, jump_rate=rate,
                     with_seg=False, index=True, m7=False, panel_extra=10)


K4_COUNT_PROGRAMS = ("P1", "P1-k5-12", "P1-30", "P1-90", "P1-1", "P1-lazy", "P1-G", "P1-1330", "M1", "M2a", "M3", "M8",
                     "H4-all")
K4_OUTCOME_PROGRAMS = ("P1", "P1-90")
BID_KEY = ["program", "coin", "variant", "t0", "shift"]
BID_COLS_CMP = ["L", "n_ticks", "delta", "P0", "sigma30", "atr_pct", "tick_str", "live_from", "seg", "ml_d0", "cw",
                "real", "rung"]
FILL_COLS_CMP = ["gap_through", "open_below", "prev_close_above", "H24", "s24", "s6", "s1", "idx_missing", "idx_outage",
                 "rh_outage"]


def _k4_run(world: dict, prog: str, outcomes: bool, jobs: int = 1) -> dict:
    cfg = dict(rules=sbe.RULES_ALL, counts_only=not outcomes, capacity="c1", verbose=False, audit="report", usd=False,
               mw=False, twin_sens=False, drift=False, keep_twins=outcomes and prog == "P1", n_jobs=jobs)
    if outcomes and prog == "H4":
        cfg["exits"] = {r: (sbe.FLIP,) for r in sbe.RULES_ALL}
    res = sbe.run_program(prog, "U_Q1", data=world, cfg=cfg)
    res["program"] = prog
    return res


def _k4_keyed(res: dict) -> dict:
    """The tables of one run keyed by bid identity (program, coin, variant, t0, shift) instead of bid ids, which
    shift when a later placement changes."""
    B = res["bids"].copy()
    B["program"] = res["program"]
    B["shift"] = pd.to_numeric(B["shift"], errors="coerce").fillna(0.0).astype(float) if "shift" in B else 0.0
    idk = B.set_index("bid_id")[["program", "coin", "variant", "t0", "shift"]]
    out = {"bids": B, "status": res["bid_status"].assign(program=res["program"]), "audit": res.get("audit")}
    F = res["fills"]
    if len(F):
        F = F.copy()
        F["program"] = res["program"]
        F["shift"] = pd.to_numeric(F["shift"], errors="coerce").fillna(0.0).astype(float) if "shift" in F else 0.0
    out["fills"] = F
    cc = res.get("cap_curve", pd.DataFrame())
    if len(cc):
        cc = cc.merge(idk, left_on="bid_id", right_index=True, how="left")
    out["cap"] = cc
    O = res.get("outcomes", pd.DataFrame())
    if len(O) and len(F):
        O = O.merge(F[["fill_id"] + BID_KEY + ["t_F1"]], on="fill_id", how="left", suffixes=("", "_f"))
    out["outcomes"] = O
    Bn = res.get("bench", pd.DataFrame())
    if len(Bn) and len(F):
        Bn = Bn.merge(F[["fill_id"] + BID_KEY], on="fill_id", how="left", suffixes=("", "_f"))
    out["bench"] = Bn
    tw = []
    for d in res.get("twins", []) or []:
        if d.get("pooled"):
            continue
        fid = np.asarray(d["fill_id"], np.int64)
        tw.append(pd.DataFrame({"fill_id": fid, "rule": d["rule"], "spec": d["spec"], "suf": d.get("suf", ""),
                                "te": np.asarray(d["te"], np.int64), "kind": np.asarray(d["kind"], np.int64),
                                "t": np.asarray(d["t"], np.int64), "px": np.asarray(d["px"], float)}))
    if tw and len(F):
        T = pd.concat(tw, ignore_index=True).merge(F[["fill_id"] + BID_KEY], on="fill_id", how="left")
        out["twins"] = T
    else:
        out["twins"] = pd.DataFrame()
    return out


def _nk(df, keys) -> pd.DataFrame:
    """A copy of df whose merge keys have one dtype on every side (strings, int64 minutes, float shift), also when a
    table is empty (an empty frame's columns default to object)."""
    str_keys = ("program", "coin", "variant", "rule", "spec", "suf", "exit", "cost")
    int_keys = ("t0", "minute", "te")
    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    for k in keys:
        if k not in df:
            df[k] = pd.Series(dtype=float if k == "shift" else (np.int64 if k in int_keys else object))
        if k in str_keys:
            df[k] = df[k].astype(str)
        elif k in int_keys:
            df[k] = pd.to_numeric(df[k], errors="coerce").fillna(-1).astype(np.int64)
        elif k == "shift":
            df[k] = pd.to_numeric(df[k], errors="coerce").fillna(0.0).astype(float)
    return df


def _pre(v, cut):
    """A time stamp as seen at the cut: the value when before it, else None."""
    return int(v) if (v is not None and np.isfinite(v) and 0 <= v < cut) else None


def k4_compare(base: dict, pert: dict, cut: int, mode: str) -> dict:
    """Every decision stamped before the cut, base against perturbed (§10.5 K4): bids placed before it (identity,
    level, inputs, live time, segment, MoneyLine state, coin-week) and the placements without a bid; for every rule
    the fill minute when before the cut and the fill's attributes stamped then; the capacity accumulated through each
    minute before the cut; exits (kind, minute, price) and B-ALERT buys stamped before it; twins of fills before it
    with the same entry minute in both runs, when their exit is before it. A K4b perturbation stops trading at the cut
    (or 3 days), so a position the base run still holds there may be valued at the delisting value from the cut on:
    such an exit is post-cut, not a change. Returns counts compared and the differences (first few listed)."""
    out = dict(compared={}, diffs={}, examples=[])

    def note(kind, n, ex=None):
        out["diffs"][kind] = out["diffs"].get(kind, 0) + n
        if ex is not None and len(out["examples"]) < 8:
            out["examples"].append(dict(kind=kind, example=str(ex)[:300]))

    # bids
    b0 = _nk(base["bids"][base["bids"].t0 < cut] if len(base["bids"]) else base["bids"], BID_KEY)
    b1 = _nk(pert["bids"][pert["bids"].t0 < cut] if len(pert["bids"]) else pert["bids"], BID_KEY)
    m = b0.merge(b1, on=BID_KEY, how="outer", indicator=True, suffixes=("_b", "_p"))
    out["compared"]["bids"] = int(len(b0))
    nd = int((m._merge != "both").sum())
    if nd:
        note("bid_set", nd, m[m._merge != "both"][BID_KEY].head(3).to_dict("records"))
    mb = m[m._merge == "both"]
    for c in BID_COLS_CMP:
        if c + "_b" not in mb:
            continue
        a, b = mb[c + "_b"], mb[c + "_p"]
        eq = (a == b) | (a.isna() & b.isna())
        if (~eq).any():
            note(f"bid_{c}", int((~eq).sum()), mb[~eq][BID_KEY + [c + "_b", c + "_p"]].head(2).to_dict("records"))
    le = np.minimum(mb.life_end_b.to_numpy(np.int64), cut) != np.minimum(mb.life_end_p.to_numpy(np.int64), cut)
    if le.any():
        note("bid_life_end_before_cut", int(le.sum()))
    sk = ["program", "coin", "t0", "status", "detail"]
    s0 = _nk(base["status"], sk)
    s1 = _nk(pert["status"], sk)
    s0 = s0[s0.t0 < cut][sk].astype({"status": str, "detail": str})
    s1 = s1[s1.t0 < cut][sk].astype({"status": str, "detail": str})
    ss = s0.merge(s1, on=sk, how="outer", indicator=True)
    if (ss._merge != "both").any():
        note("bid_status", int((ss._merge != "both").sum()), ss[ss._merge != "both"].head(3).to_dict("records"))
    # fills: per rule, the fill minute when before the cut
    F0, F1_ = _nk(base["fills"], BID_KEY), _nk(pert["fills"], BID_KEY)
    keys = b0[BID_KEY]
    tcols = sorted({c for c in list(F0.columns) + list(F1_.columns) if c.startswith("t_F") and c != "t_F3usd_1"
                    and c != "t_F3usd_3"})
    f0 = keys.merge(F0, on=BID_KEY, how="left") if len(F0) else keys.copy()
    f1 = keys.merge(F1_, on=BID_KEY, how="left") if len(F1_) else keys.copy()
    nf = 0
    for c in tcols:
        a = f0[c].to_numpy(float) if c in f0 else np.full(len(keys), np.nan)
        b = f1[c].to_numpy(float) if c in f1 else np.full(len(keys), np.nan)
        pa = np.array([_pre(x, cut) is not None for x in a], dtype=bool)
        pb = np.array([_pre(x, cut) is not None for x in b], dtype=bool)
        diff = (pa != pb) | (pa & pb & (a != b))
        nf += int(pa.sum())
        if diff.any():
            i = int(np.flatnonzero(diff)[0])
            note(f"fill_{c}", int(diff.sum()), dict(key=keys.iloc[i].to_dict(), base=a[i], pert=b[i]))
    out["compared"]["fills"] = nf
    if "t_F1" in f0 and "t_F1" in f1:
        pre = np.array([_pre(x, cut) is not None for x in f0.t_F1.to_numpy(float)], dtype=bool)
        for c in FILL_COLS_CMP:
            if c in f0 and c in f1:
                a, b = f0[c].to_numpy()[pre], f1[c].to_numpy()[pre]
                eq = np.array([(x == y) or (pd.isna(x) and pd.isna(y)) for x, y in zip(a, b)], bool)
                if (~eq).any():
                    note(f"fill_attr_{c}", int((~eq).sum()))
    # capacity accumulated before the cut
    c0, c1 = _nk(base["cap"], BID_KEY), _nk(pert["cap"], BID_KEY)
    if len(c0):
        mc = c0.merge(c1, on=BID_KEY, how="left", suffixes=("_b", "_p")) if len(c1) else \
            c0.assign(n_p=np.nan, sum_minute_p=np.nan, sum_cum_p=np.nan, last_cum_p=np.nan, max_cum_p=np.nan)
        if "n" in mc:
            mc = mc.rename(columns={c: c + "_b" for c in ("n", "sum_minute", "sum_cum", "last_cum", "max_cum")})
        out["compared"]["capacity_minutes"] = int(mc.n_b.sum())
        bad = (mc.n_b != mc.n_p) | (mc.sum_minute_b != mc.sum_minute_p)
        for c in ("sum_cum", "last_cum", "max_cum"):
            bad |= ~np.isclose(mc[c + "_b"].to_numpy(float), mc[c + "_p"].to_numpy(float), rtol=1e-12, atol=0)
        if bad.any():
            note("capacity", int(bad.sum()), mc[bad].head(2).to_dict("records"))
    # exits stamped before the cut
    ok_ = BID_KEY + ["rule", "exit", "cost"]
    O0, O1 = base["outcomes"], pert["outcomes"]
    O0 = _nk(O0, ok_) if len(O0) else O0
    O1 = _nk(O1, ok_) if len(O1) else O1
    if len(O0):
        k = BID_KEY + ["rule", "exit", "cost"]
        o0 = O0[(O0.exit_t >= 0) & (O0.exit_t < cut)]
        o1 = O1 if len(O1) else O0.iloc[:0]
        mo = o0.merge(o1, on=k, how="left", suffixes=("_b", "_p"))
        out["compared"]["exits"] = int(len(mo))
        same = (mo.exit_t_b == mo.exit_t_p) & (mo.exit_kind_b == mo.exit_kind_p) & \
            np.isclose(mo.exit_px_b.to_numpy(float), mo.exit_px_p.to_numpy(float), rtol=1e-12, atol=0,
                       equal_nan=True)
        if (~same).any():
            note("exit_changed", int((~same).sum()), mo[~same][k + ["exit_t_b", "exit_t_p", "exit_kind_b",
                                                                   "exit_kind_p"]].head(2).to_dict("records"))
        # an exit the base run stamps after the cut must not move before it (K4b: a delisting value from the cut on)
        o0b = O0[(O0.exit_t >= cut) | (O0.exit_t < 0)]
        mo2 = o0b.merge(o1, on=k, how="inner", suffixes=("_b", "_p"))
        early = (mo2.exit_t_p >= 0) & (mo2.exit_t_p < cut)
        if mode != "scale":
            early &= ~mo2.exit_kind_p.isin(["delist", "censored"])
        if early.any():
            note("exit_moved_before_cut", int(early.sum()), mo2[early][k + ["exit_t_b", "exit_t_p",
                                                                        "exit_kind_p"]].head(2).to_dict("records"))
    B0, B1 = base["bench"], pert["bench"]
    B0 = _nk(B0, BID_KEY + ["rule"]) if len(B0) else B0
    B1 = _nk(B1, BID_KEY + ["rule"]) if len(B1) else B1
    if len(B0) and "alert_t_M" in B0:
        for a_ in ("M", "2h", "8h", "24h", "72h"):
            col = f"alert_t_{a_}"
            if col not in B0:
                continue
            x0 = B0[(B0[col] >= 0) & (B0[col] < cut)]
            mx = x0.merge(B1, on=BID_KEY + ["rule"], how="left", suffixes=("_b", "_p")) if len(B1) else x0
            out["compared"]["alerts"] = out["compared"].get("alerts", 0) + int(len(mx))
            if len(B1):
                bad = (mx[col + "_b"] != mx[col + "_p"]) | ~np.isclose(mx[f"alert_px_{a_}_b"].to_numpy(float),
                                                                     mx[f"alert_px_{a_}_p"].to_numpy(float),
                                                                     rtol=1e-12, equal_nan=True)
                if bad.any():
                    note("alert", int(bad.sum()))
    T0, T1 = base["twins"], pert["twins"]
    tk_ = BID_KEY + ["rule", "spec", "suf", "te"]
    T0 = _nk(T0, tk_) if len(T0) else T0
    T1 = _nk(T1, tk_) if len(T1) else T1
    if len(T0) and len(T1):
        k = BID_KEY + ["rule", "spec", "suf", "te"]
        t0_ = T0[(T0.t >= 0) & (T0.t < cut) & (T0.te < cut)].drop_duplicates(k)
        mt = t0_.merge(T1.drop_duplicates(k), on=k, how="inner", suffixes=("_b", "_p"))
        out["compared"]["twin_exits"] = int(len(mt))
        bad = (mt.t_b != mt.t_p) | (mt.kind_b != mt.kind_p) | ~np.isclose(mt.px_b, mt.px_p, rtol=1e-12)
        if bad.any():
            note("twin_exit", int(bad.sum()))
    out["ok"] = not out["diffs"]
    return out


def draw_cuts(n: int, placements: np.ndarray, fill_minutes: np.ndarray, lo: int, hi: int, rng, coins_of_fills=None,
              coins=None) -> pd.DataFrame:
    """K4's cut minutes (§10.5): n random minutes never on an hour boundary, at least 10 within 24 h after a
    placement, 10 inside fill-day crash hours (the hour of a fill), 10 on weekends (UTC Saturday / Sunday); the rest
    uniform in [lo, hi). Each cut carries a coin for K4b (the fill's coin for crash-hour cuts, else a random one)."""
    rows = []

    def ok_min(t):
        return t % 60 != 0 and lo <= t < hi

    pl = placements[(placements >= lo) & (placements < hi - DAY_M)]
    fm = np.asarray(fill_minutes, np.int64)
    sel = (fm >= lo) & (fm < hi)
    fm = fm[sel]
    fc = np.asarray(coins_of_fills)[sel] if coins_of_fills is not None else None
    k = max(10, n // 4)
    while sum(r["why"] == "placement" for r in rows) < k and len(pl):
        t = int(rng.choice(pl)) + int(rng.integers(1, DAY_M))
        if ok_min(t):
            rows.append(dict(t=t, why="placement", coin=str(rng.choice(coins))))
    while sum(r["why"] == "crash_hour" for r in rows) < k and len(fm):
        j = int(rng.integers(0, len(fm)))
        t = (int(fm[j]) // 60) * 60 + int(rng.integers(1, 60))
        if ok_min(t):
            rows.append(dict(t=t, why="crash_hour", coin=str(fc[j]) if fc is not None else str(rng.choice(coins))))
    while sum(r["why"] == "weekend" for r in rows) < k:
        t = int(rng.integers(lo, hi))
        wd = pd.Timestamp(t * MIN_NS, tz="UTC").weekday()
        if wd >= 5 and ok_min(t):
            rows.append(dict(t=t, why="weekend", coin=str(rng.choice(coins))))
    while len(rows) < n:
        t = int(rng.integers(lo, hi))
        if ok_min(t):
            rows.append(dict(t=t, why="uniform", coin=str(rng.choice(coins))))
    df = pd.DataFrame(rows)
    df["time"] = pd.DatetimeIndex(df.t.to_numpy(np.int64) * MIN_NS, tz="UTC").astype(str)
    df["weekend"] = pd.DatetimeIndex(df.t.to_numpy(np.int64) * MIN_NS, tz="UTC").weekday >= 5
    return df


def _k4_world_runs(market: K4Market, outcomes_programs=K4_OUTCOME_PROGRAMS, count_programs=K4_COUNT_PROGRAMS) -> dict:
    W = market.world()
    out = {}
    for p in count_programs:
        out[("count", p)] = _k4_keyed(_k4_run(W, p, outcomes=False))
    for p in outcomes_programs:
        out[("out", p)] = _k4_keyed(_k4_run(W, p, outcomes=True))
    return out


def _k4_trim(runs: dict, cut: int) -> dict:
    """Keep what K4's comparison reads (bids placed and decisions stamped up to the cut, plus exits after it for the
    'moved before the cut' check) to keep worker results small."""
    out = {}
    for key, r in runs.items():
        x = dict(r)
        x["bids"] = r["bids"][r["bids"].t0 < cut]
        x["status"] = r["status"][r["status"].t0 < cut]
        if len(r["fills"]):
            x["fills"] = r["fills"][r["fills"].t0 < cut]
        if len(r["cap"]):
            c = r["cap"][(r["cap"].minute < cut) & (r["cap"].t0 < cut)]
            # per bid: the capacity accumulated minute by minute before the cut, summarised exactly (count, sums,
            # the last cumulative value) instead of shipping every minute between processes
            c = c.sort_values(BID_KEY + ["minute"], kind="stable")
            x["cap"] = c.groupby(BID_KEY, dropna=False).agg(n=("minute", "size"), sum_minute=("minute", "sum"),
                                                             sum_cum=("cum", "sum"), last_cum=("cum", "last"),
                                                             max_cum=("cum", "max")).reset_index()
        if len(r["outcomes"]):
            x["outcomes"] = r["outcomes"][r["outcomes"].t0 < cut]
        if len(r["bench"]):
            x["bench"] = r["bench"][r["bench"].t0 < cut]
        if len(r["twins"]):
            x["twins"] = r["twins"][(r["twins"].te < cut) & (r["twins"].t0 < cut)]
        out[key] = x
    return out


def _after_print(runs: dict, cut: int) -> dict:
    """A fingerprint of the decisions after the cut (bids placed and fills stamped after it), to show that a
    perturbation bites."""
    out = {}
    for key, r in runs.items():
        b = r["bids"][r["bids"].t0 >= cut]
        f = r["fills"]
        fa = f.t_F1[(f.t_F1 >= cut)].to_numpy(float) if len(f) and "t_F1" in f else np.zeros(0)
        out[key] = (len(b), float(np.round(b.L.sum(), 9)) if len(b) else 0.0, len(fa), float(fa.sum()))
    return out


def _k4_task(args):
    spec, cut, mode, coin, progs = args
    t = time.time()
    market = K4Market(spec, Pert(mode, int(cut), coin))
    runs = _k4_world_runs(market, *progs)
    return dict(cut=int(cut), mode=mode, coin=coin, runs=_k4_trim(runs, int(cut)), after=_after_print(runs, int(cut)),
                seconds=time.time() - t)


def _k4_syn_raw(n_cuts: int, jobs: int, spec: SynthSpec, log, programs, cache: bool) -> dict:
    """The base runs, the cuts and the perturbed runs (each trimmed at its cut) of the synthetic K4 world. With cache,
    stored in data/stinkbid/controls/ under the code that produces them, so that a crash in the comparison step does
    not recompute the perturbed worlds."""
    import pickle
    f = None
    if cache:
        key = hashlib.sha1((repr(spec) + repr(programs) + str(n_cuts) + code_hash(_K4_RAW_CODE)).encode()).hexdigest()
        f = WORK / f"k4raw_{key[:16]}.pkl"
        if f.exists():
            with open(f, "rb") as fh:
                x = pickle.load(fh)
            log(f"K4 synthetic: reusing the cached perturbed runs {f.name}")
            return x
    t0 = time.time()
    base_m = K4Market(spec)
    base = _k4_world_runs(base_m, *programs)
    t1 = time.time()
    p1 = base[("out", "P1")] if ("out", "P1") in base else base[("count", "P1")]
    F = p1["fills"]
    fm = F.t_F1.to_numpy(float) if len(F) else np.zeros(0)
    ok = np.isfinite(fm) & (fm >= 0)
    lo = _tmin(pd.Timestamp(spec.start) + pd.Timedelta(days=120))
    hi = _tmin(pd.Timestamp(spec.end) - pd.Timedelta(days=30))
    pl = _tmin(pd.date_range(pd.Timestamp(spec.start, tz="UTC") + pd.Timedelta(days=1), pd.Timestamp(spec.end, tz="UTC"),
                             freq="W-MON")) + 210
    cuts = draw_cuts(n_cuts, pl, fm[ok].astype(np.int64), lo, hi, np.random.default_rng(SEED + 4),
                     F.coin.to_numpy()[ok] if len(F) else None, base_m.coins)
    tasks = [(spec, int(r.t), mode, r.coin, programs) for r in cuts.itertuples() for mode in ("scale", "delete", "gap")]
    log(f"K4 synthetic: base runs {t1 - t0:.0f}s; {len(cuts)} cuts x 3 perturbations = {len(tasks)} perturbed worlds")
    res = _pmap(_k4_task, tasks, jobs)
    x = dict(base=base, cuts=cuts, res=res, n_tasks=len(tasks), base_seconds=t1 - t0, seconds=time.time() - t0)
    if f is not None:
        WORK.mkdir(parents=True, exist_ok=True)
        with open(f.with_suffix(".tmp"), "wb") as fh:
            pickle.dump(x, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(f.with_suffix(".tmp"), f)
    return x


def k4_synthetic(n_cuts: int = K4_CUTS, jobs: int = 4, spec: SynthSpec | None = None, log=_say,
                 programs=(K4_OUTCOME_PROGRAMS, K4_COUNT_PROGRAMS), cache: bool = False) -> dict:
    """K4 and K4b on the synthetic K4 world through the engine (every program, life and level method, F1-F5,
    capacity, exits, alerts, twins): each perturbed run against the base run at its cut. A comparison that cannot be
    made (an exception) counts as a failed comparison and is listed with its error."""
    import traceback
    spec = spec or k4_spec()
    t0 = time.time()
    raw = _k4_syn_raw(n_cuts, jobs, spec, log, programs, cache)
    base, cuts, res = raw["base"], raw["cuts"], raw["res"]
    rows, fails = [], []
    for r in res:
        for key, pr in r["runs"].items():
            bt = _k4_trim({key: base[key]}, r["cut"])[key]
            try:
                c = k4_compare(bt, pr, r["cut"], r["mode"])
            except Exception as e:
                c = dict(ok=False, compared={}, diffs={"compare_error": 1},
                         examples=[dict(kind="compare_error", example=repr(e)[:300],
                                        where=traceback.format_exc(limit=-3)[-1500:])])
            rows.append(dict(cut=r["cut"], mode=r["mode"], coin=r["coin"], run=f"{key[0]}:{key[1]}", ok=c["ok"],
                             **{f"n_{k}": v for k, v in c["compared"].items()},
                             diffs=json.dumps(c["diffs"]) if c["diffs"] else ""))
            if not c["ok"]:
                fails.append(dict(cut=r["cut"], mode=r["mode"], run=f"{key[0]}:{key[1]}", diffs=c["diffs"],
                                  examples=c["examples"]))
    T = pd.DataFrame(rows)
    # the perturbations must bite: some decision after the cut changes
    bites = {}
    for r in res:
        ba = _after_print(base, r["cut"])
        n = sum(int(ba[k] != v) for k, v in r["after"].items() if k in ba)
        bites[r["mode"]] = bites.get(r["mode"], 0) + int(n > 0)
    out = dict(bites=bites, cuts=cuts.to_dict("records"), n_cuts=len(cuts), by_why=cuts.why.value_counts().to_dict(),
               weekend=int(cuts.weekend.sum()), worlds=raw["n_tasks"], comparisons=len(T), failures=len(fails),
               failed=fails[:20], compared_totals={c: int(T[c].sum()) for c in T.columns if c.startswith("n_")},
               ok=bool(len(fails) == 0 and len(T) > 0 and all(v > 0 for v in bites.values())),
               seconds=time.time() - t0, perturbed_runs_seconds=raw["seconds"])
    out["_table"] = T
    # K5: the engine's fill audits of every K4 run (the base world and every perturbed world)
    aud = {"base": [_compact_audit(r.get("audit")) for r in base.values()]}
    for r in res:
        aud.setdefault(r["mode"], []).extend(_compact_audit(pr.get("audit")) for pr in r["runs"].values())
    out["_audits"] = [(f"synthetic K4 {k} runs", pd.concat(v_, ignore_index=True) if v_ else None)
                      for k, v in aud.items() for v_ in [[a for a in v if a is not None and len(a)]]]
    out["_bids"] = _k4_bid_tables(base)                              # K7(a): every program's levels
    return out


def _k4_bid_tables(base: dict) -> list:
    """The level tables of the K4 base world's runs, one per program (K7(a) checks every level method on them)."""
    out = []
    for (kind, prog), r in base.items():
        if kind == "out" and ("count", prog) in base:
            continue                                                 # the same program's bids
        b = r["bids"]
        if len(b):
            out.append((f"synthetic K4 {prog}", b[[c for c in ("program", "method", "L", "L_tau", "n_ticks",
                                                               "tick_str") if c in b]].copy()))
    return out


# ---- real data: universes, levels, fills and capacity (counts and inputs only; no outcome)
def _perturb_panel(a: pd.DataFrame, cut: int) -> pd.DataFrame:
    """stinkbid_data.d1_panel rows perturbed at the cut: days after the cut's day x 1.5 (prices) and x 0.5 (volumes);
    the cut's own day keeps its open and has its high and close x 1.5 and its volumes x 0.5 (the part after the cut
    is unknown at daily resolution); segment ids recomputed by stinkbid_data's rule."""
    a = a.copy()
    d = _tmin(a.day if "day" in a else a.open_time)
    cday = (cut // DAY_M) * DAY_M
    after = d > cday
    on = d == cday
    for c in ("open", "low"):
        a[c] = np.where(after, a[c].to_numpy(float) * 1.5, a[c].to_numpy(float))
    for c in ("high", "close"):
        a[c] = np.where(after | on, a[c].to_numpy(float) * 1.5, a[c].to_numpy(float))
    for c in ("volume", "quote_volume", "taker_buy_quote"):
        if c in a:
            a[c] = np.where(after | on, a[c].to_numpy(float) * 0.5, a[c].to_numpy(float))
    a = a.sort_values(["coin", "day"], kind="stable").reset_index(drop=True)
    a["seg"] = sbd._seg_ids(a)
    return a


def _uni_task(args):
    cut, months = args
    a = sbd.d1_panel().sort_values(["coin", "day"], kind="stable").reset_index(drop=True)
    a["seg"] = sbd._seg_ids(a)                     # the same segment rule as the perturbed panel's (one pipeline)
    first, last = months
    lst, uc = sbd.first_listing(), sbd.u_c_coins()
    rk0 = sbd._ranks(a, first, last)
    u0 = sbd._universes(rk0, first, last, lst, uc)
    ap = _perturb_panel(a, cut)
    rk1 = sbd._ranks(ap, first, last)
    u1 = sbd._universes(rk1, first, last, lst, uc)
    cm = pd.Timestamp(cut * MIN_NS, tz="UTC").strftime("%Y-%m")
    cols = ["month", "coin", "U_B", "U_Q1", "U_Q1_12", "U_Q1_xm", "U_C", "U_A", "rank", "rank_med12",
            "listing_age_months"]
    x0 = u0[u0.month <= cm][cols].sort_values(["month", "coin"]).reset_index(drop=True)
    x1 = u1[u1.month <= cm][cols].sort_values(["month", "coin"]).reset_index(drop=True)
    same = x0.equals(x1)
    later = u0[u0.month > cm][cols].sort_values(["month", "coin"]).reset_index(drop=True)
    later1 = u1[u1.month > cm][cols].sort_values(["month", "coin"]).reset_index(drop=True)
    return dict(cut=int(cut), month=cm, rows=int(len(x0)), same=bool(same),
                later_changed=bool(not later.equals(later1)))


def k4_real_universes(cuts: pd.DataFrame, jobs: int = 4) -> dict:
    """K4 on the real universes: the daily panel perturbed at each cut, ranks and universes rebuilt by stinkbid_data's
    own functions (_ranks, _universes) for months M-12..M+1 around the cut's month M; every universe row of a month
    that starts before the cut (months <= M: decided at the month's start) must be unchanged."""
    tasks = []
    for t in cuts.t:
        m = pd.Timestamp(int(t) * MIN_NS, tz="UTC").tz_localize(None).to_period("M")
        tasks.append((int(t), ((m - 13).strftime("%Y-%m"), (m + 1).strftime("%Y-%m"))))
    res = _pmap(_uni_task, tasks, jobs)
    return dict(cuts=len(res), rows_compared=int(sum(r["rows"] for r in res)),
                changed=[r for r in res if not r["same"]], later_changed=int(sum(r["later_changed"] for r in res)),
                ok=bool(all(r["same"] for r in res)))


REAL_LEVEL_VARIANTS = tuple(v for v in sbl.VARIANTS if v[0] not in ("M3", "M3c", "M8"))   # pooled ones: synthetic


def _real_frames(coin: str, lo: int, hi: int) -> dict:
    """Real frames of one coin restricted to [lo, hi) minutes (the levels' inputs and the 1m bars)."""
    def cut(k, col="open_time"):
        if k is None or not len(k):
            return k
        m = _tmin(k[col])
        return k[(m >= lo) & (m < hi)].reset_index(drop=True)
    fr = {"m1": cut(sbd.m1(coin, fetch=False)), "d1": cut(sbd.d1(coin)), "h1": cut(sbd.h1(coin))}
    for name, fn, col in (("metrics", sbd.metrics, "create_time"), ("mark1h", sbd.mark1h, "open_time"),
                          ("perp1h", sbd.perp1h, "open_time")):
        try:
            fr[name] = cut(fn(coin), col)
        except Exception:
            fr[name] = None
    return fr


def _perturb_real(fr: dict, cut: int, mode: str = "scale") -> dict:
    """Real frames perturbed at the cut. scale: 1m and every later bar x 1.5 / x 0.5, the daily and hourly bars that
    straddle the cut rebuilt from the perturbed minutes (their open stays), open interest x 0.5; delete / gap: every
    bar from the cut (for 3 days) removed."""
    out = {}
    for name, k in fr.items():
        if k is None or not isinstance(k, pd.DataFrame) or not len(k):
            out[name] = k
            continue
        col = "create_time" if name == "metrics" else "open_time"
        p = Pert(mode, cut, "X")
        out[name] = _pert_frame(k, p, "X", tcol=col, oi=("oi", "oi_usd") if name == "metrics" else ())
    if mode == "scale":
        m1 = out["m1"]
        for name, per in (("d1", DAY_M), ("h1", 60)):
            k = out.get(name)
            if k is None or not len(k):
                continue
            k = k.copy()
            s = (cut // per) * per
            if s == cut:
                continue
            tm = _tmin(k.open_time)
            row = np.flatnonzero(tm == s)
            if not len(row):
                continue
            mm = _tmin(m1.open_time)
            sel = (mm >= s) & (mm < s + per) & (m1.trades.to_numpy() > 0)
            if sel.any():
                r0 = row[0]
                k.loc[r0, "high"] = float(m1.high.to_numpy()[sel].max())
                k.loc[r0, "low"] = float(m1.low.to_numpy()[sel].min())
                k.loc[r0, "close"] = float(m1.close.to_numpy()[sel][-1])
                for c in ("volume", "quote_volume", "taker_buy_quote"):
                    if c in k:
                        k.loc[r0, c] = float(m1[c].to_numpy()[sel].sum())
                # the bar's own high/close were scaled by _pert_frame only when it starts after the cut
            out[name] = k
    return out


def _level_rows(coin: str, data: dict, t0s) -> pd.DataFrame:
    rows = []
    for t0 in t0s:
        I = sbl.inputs_at(coin, _ts(t0), data=data)
        base = dict(t0=int(t0), ok=I["ok"], why=I.get("why", ""), P0=I.get("P0"), sigma30=I.get("sigma30"),
                    atr_pct=I.get("atr_pct"), tick=I.get("tick_str"))
        if not I["ok"]:
            rows.append(base)
            continue
        for m, p in REAL_LEVEL_VARIANTS:
            r = sbl.level_info(m, I, **p)
            rows.append(dict(base, variant=sbl.variant_label(m, p), status=r["status"], L=r.get("L"),
                             n=r.get("n_ticks"), delta=r.get("delta")))
    return pd.DataFrame(rows)


def _real_level_task(args):
    coin, cut = args
    lo = cut - 420 * DAY_M
    hi = cut + 60 * DAY_M
    fr = _real_frames(coin, lo, hi)
    if fr["m1"] is None or not len(fr["m1"]):
        return dict(coin=coin, cut=cut, skipped="no 1m bars")
    pl = _tmin(pd.date_range(_ts(cut - 15 * DAY_M).normalize(), _ts(cut), freq="D")) + 210
    t0s = [int(t) for t in pl if t < cut and pd.Timestamp(int(t) * MIN_NS, tz="UTC").weekday() == 0]
    t0s += [int(t) - 210 + 810 for t in pl if t - 210 + 810 < cut and
            pd.Timestamp(int(t) * MIN_NS, tz="UTC").weekday() == 0]          # 13:30 placements too
    t0s = sorted(set(t0s))
    base = _level_rows(coin, dict(fr, real=False), t0s)
    pert = _level_rows(coin, dict(_perturb_real(fr, cut), real=False), t0s)
    cols = [c for c in base.columns if c in pert.columns]
    a = base[cols].astype(str).reset_index(drop=True)
    b = pert[cols].astype(str).reset_index(drop=True)
    same = a.equals(b)
    lv = pd.DataFrame(columns=["method", "L", "n_ticks", "tick_str"])
    if "status" in base:                                             # K7(a): the levels themselves (no outcome)
        ok = (base.status == "ok") & pd.to_numeric(base.L, errors="coerce").notna()
        lv = pd.DataFrame({"method": base.variant[ok].astype(str).str.split().str[0],
                           "L": base.L[ok].astype(float), "n_ticks": base.n[ok].astype(np.int64),
                           "tick_str": base.tick[ok].astype(str)})
    return dict(coin=coin, cut=int(cut), placements=len(t0s), rows=int(len(base)), same=bool(same),
                example=None if same else a.compare(b).head(3).to_dict(), levels=lv)


def k4_real_levels(cuts: pd.DataFrame, jobs: int = 4) -> dict:
    """K4 on real levels: for each cut's coin, the inputs and every per-coin level variant (M1, M2, M2a, M4 / M4f /
    M4s, M5f / M5a / M5b, M6, M7; the pooled M3 and M8 are checked on the synthetic panel) at the Monday 03:30 and
    13:30 placements of the 15 days before the cut, from the real frames and from the frames perturbed at the cut."""
    res = _pmap(_real_level_task, [(r.coin, int(r.t)) for r in cuts.itertuples()], jobs)
    done = [r for r in res if "skipped" not in r]
    lv = [x for x in (r.pop("levels", None) for r in done) if x is not None and len(x)]
    return dict(cuts=len(res), checked=len(done), skipped=[r for r in res if "skipped" in r],
                rows_compared=int(sum(r["rows"] for r in done)), placements=int(sum(r["placements"] for r in done)),
                changed=[r for r in done if not r["same"]], ok=bool(done and all(r["same"] for r in done)),
                _levels=pd.concat(lv, ignore_index=True) if lv else None)


def _real_fill_task(args):
    coin, cut, members = args
    lo = cut - 400 * DAY_M
    hi = cut + 120 * DAY_M
    fr = _real_frames(coin, lo, hi)
    if fr["m1"] is None or not len(fr["m1"]):
        return dict(coin=coin, cut=cut, skipped="no 1m bars")
    out = dict(coin=coin, cut=int(cut), runs=[])
    aud = []
    end = pd.Timestamp(min(hi, _tmin(pd.Timestamp(END_DAY) + pd.Timedelta(days=1)) - 1) * MIN_NS,
                       tz="UTC").strftime("%Y-%m-%d")
    for mode in ("scale", "delete", "gap"):
        worlds = {}
        for tag, f in (("base", fr), ("pert", _perturb_real(fr, cut, mode))):
            # daily bars and segment ids derived by the engine from the (perturbed) 1m bars in both runs, so the
            # minutes of the cut's day before the cut keep their day
            frames = {"m1": f["m1"].drop(columns=["seg"], errors="ignore")}
            worlds[tag] = {"universe": pd.DataFrame([dict(month=m, coin=coin, U_Q1=True, U_B=True) for m in members]),
                           "coins": {coin: frames}, "end": end, "tbill": 0.0}
        for prog in ("P1", "P1-90", "P1-1", "P1-lazy"):
            r = {}
            for tag, W in worlds.items():
                res = sbe.run_program(prog, "U_Q1", data=W, cfg=dict(rules=("F1", "F2"), counts_only=True,
                                                                     capacity="c1", verbose=False, audit="report",
                                                                     mw=False, usd=False))
                res["program"] = prog
                r[tag] = _k4_trim({("count", prog): _k4_keyed(res)}, int(cut))[("count", prog)]
                a = _compact_audit(res.get("audit"))
                if a is not None and len(a):
                    aud.append(a)
            c = k4_compare(r["base"], r["pert"], int(cut), mode)
            out["runs"].append(dict(mode=mode, program=prog, ok=c["ok"], compared=c["compared"], diffs=c["diffs"],
                                    examples=c["examples"][:2]))
    out["_audit"] = pd.concat(aud, ignore_index=True) if aud else None
    return out


def _pick_cuts(cuts: pd.DataFrame, n: int) -> pd.DataFrame:
    """n of K4's cuts stratified by kind (draw_cuts orders them by kind): the i-th cut of each kind in turn (round
    robin, in drawn order) until n are taken; returned in the frame's order."""
    groups = [list(cuts.index[cuts.why == k]) for k in dict.fromkeys(cuts.why)]
    pick, i = [], 0
    while len(pick) < min(n, len(cuts)):
        for g in groups:
            if i < len(g) and len(pick) < n:
                pick.append(g[i])
        i += 1
    return cuts.loc[sorted(pick)]


def k4_real_fills(cuts: pd.DataFrame, jobs: int = 4, n: int = 24) -> dict:
    """K4 / K4b on real 1m bars (counts only: bids, F1 / F2 fills, capacity): n cuts stratified by kind (_pick_cuts:
    within 24 h of a placement, fill-day crash hours, weekends, uniform), each cut's coin in a world of its real 1m
    bars from 400 days before to 120 days after the cut, base against perturbed (scale, delete, gap), for P1, P1-90,
    P1-1 and P1-lazy. Daily bars and segments are derived from the 1m bars by the engine in both runs."""
    u = sbd.universes()
    tasks = []
    pick = _pick_cuts(cuts, n)
    for r in pick.itertuples():
        mem = sorted(u.month[(u.coin == r.coin) & u.U_Q1.astype(bool)].astype(str).unique())
        if mem:
            tasks.append((r.coin, int(r.t), mem))
    res = _pmap(_real_fill_task, tasks, jobs)
    runs = [dict(coin=r["coin"], cut=r["cut"], **x) for r in res if "runs" in r for x in r["runs"]]
    bad = [x for x in runs if not x["ok"]]
    tot = {}
    for x in runs:
        for k, v in x["compared"].items():
            tot[k] = tot.get(k, 0) + v
    aud = [r["_audit"] for r in res if r.get("_audit") is not None]
    return dict(cuts=len(tasks), by_why=pick.why.value_counts().to_dict(), runs=len(runs), compared_totals=tot,
                failures=bad[:20], n_failures=len(bad),
                skipped=[{k: v for k, v in r.items() if k != "_audit"} for r in res if "skipped" in r],
                ok=bool(runs and not bad), _audit=pd.concat(aud, ignore_index=True) if aud else None)


# ============================================================================ K5: fill audit (§10.5)
def _audit_frames() -> list:
    out = []
    for name in ("p1_audit", "h4_audit"):
        f = WORK / f"{name}.parquet"
        if f.exists():
            out.append((f"real {name[:2].upper()} calendar", pd.read_parquet(f)))
    return out


def _k5_coin(args):
    """Independent re-audit of one coin's real P1 F1 fills from its 1m bars (counts only): each fill at L, in a live
    minute (trades > 0) at or after its live time and before its life end, with low <= L - tau, and the first such
    minute; a minute wholly above... a fill price outside the minute's range only for a gap-through (listed)."""
    coin, F = args
    k = sbd.m1(coin, fetch=False)
    t = _tmin(k.open_time)
    lo, hi = k.low.to_numpy(float), k.high.to_numpy(float)
    live = k.trades.to_numpy() > 0
    seg = k.seg.to_numpy() if "seg" in k else np.zeros(len(k), np.int64)
    viol, gaps, n = [], [], 0
    for r in F.itertuples():
        n += 1
        i = int(np.searchsorted(t, int(r.t_F1)))
        if i >= len(t) or t[i] != r.t_F1:
            viol.append((coin, int(r.t_F1), "fill minute missing from the 1m bars"))
            continue
        if not live[i]:
            viol.append((coin, int(r.t_F1), "fill in a minute with trades = 0"))
        if not (r.live_from <= r.t_F1 < r.life_end):
            viol.append((coin, int(r.t_F1), "fill outside the bid's life"))
        if not lo[i] <= r.L_tau:
            viol.append((coin, int(r.t_F1), "low above L - tau"))
        a = int(np.searchsorted(t, int(r.live_from)))
        w = np.flatnonzero(live[a:i] & (lo[a:i] <= r.L_tau) & (seg[a:i] == seg[i]))
        if len(w):
            viol.append((coin, int(r.t_F1), f"an earlier qualifying minute {int(t[a + w[0]])}"))
        if r.L > hi[i]:
            gaps.append((coin, int(r.t_F1), float(r.L), float(hi[i])))
    return dict(coin=coin, n=n, violations=viol, gaps=gaps)


def k5_audit(engine_records: list, jobs: int = 4, real_reaudit: bool = True) -> dict:
    """K5 (§10.5): every K5 record of the engine runs made by the controls (synthetic K1 / K2 / K4 worlds) and of the
    real counts-only calendars (P1 under F1-F5, H4), aggregated; plus an independent re-audit of every real P1 F1 fill
    from the raw 1m bars (this module's code). Violations stop the study; gap-through fills (resting orders filled at
    their limit above the minute's high) are listed and counted."""
    out = dict(sources=[], violations=0, gaps=0, checks=0)
    for name, A in list(engine_records) + _audit_frames():
        if A is None or not len(A):
            out["sources"].append(dict(source=name, violations=0, gaps=0, checks=0))
            continue
        ty = A["type"].astype(str)
        nv, ng = int((ty == "violation").sum()), int((ty == "gap").sum())
        nc = int(pd.to_numeric(A.loc[ty == "count", "n"], errors="coerce").fillna(0).sum()) if "n" in A else 0
        out["sources"].append(dict(source=name, violations=nv, gaps=ng, checks=nc,
                                   first=A[ty == "violation"].head(2).astype(str).to_dict("records") if nv else []))
        out["violations"] += nv
        out["gaps"] += ng
        out["checks"] += nc
    if real_reaudit and _cal_paths()["p1_fills"].exists():
        F = pd.read_parquet(_cal_paths()["p1_fills"])
        F = F[F.t_F1 >= 0]
        tasks = [(c, g[["t_F1", "L", "L_tau", "live_from", "life_end"]]) for c, g in F.groupby("coin")]
        res = _pmap(_k5_coin, tasks, jobs)
        v = [x for r in res for x in r["violations"]]
        g = [x for r in res for x in r["gaps"]]
        out["real_reaudit"] = dict(fills=int(sum(r["n"] for r in res)), violations=len(v), first=v[:10],
                                   gap_through=len(g), gap_list=g[:50])
        out["violations"] += len(v)
    out["passed"] = bool(out["violations"] == 0)
    return out


# ============================================================================ K6: capacity check (§10.5)
def _k6_coin(args):
    coin, rows = args
    world = sbe.World(None)
    spot, _, _ = sbe.build_spot(world, coin)
    b = rows.reset_index(drop=True)
    i_fill = np.searchsorted(spot.t, b.t_F1.to_numpy(np.int64))
    ok = (i_fill < spot.n) & (spot.t[np.minimum(i_fill, spot.n - 1)] == b.t_F1.to_numpy(np.int64))
    i_fill = np.where(ok, i_fill, -1).astype(np.int64)
    t = time.time()
    try:
        cap = sbe.capacity(world, coin, b, spot, i_fill, mode="agg")
    except Exception as e:                                          # network / archive: recorded, never filled
        return dict(coin=coin, error=repr(e)[:300], rows=[])
    cap["coin"] = coin
    cap["t_F1"] = b.t_F1.to_numpy()[cap.row.to_numpy()]
    cap["rung"] = b.rung.to_numpy()[cap.row.to_numpy()]
    return dict(coin=coin, rows=cap.to_dict("records"), seconds=time.time() - t)


def k6_capacity(n: int = K6_FILLS, jobs: int = 4, seed: int = SEED + 6) -> dict:
    """K6 (§10.5): C1, the 1-minute approximation, against aggTrades capacity (stinkbid_data.agg_capacity, streamed
    and cached) on n random real P1 F1 fills (U-Q1; counts only), on the same causal windows (engine.capacity, draft
    §8.3): the ratio C1 / aggTrades for the fill's first window and over the life, and whether a $10k order would be
    sized the same. Missing archive days are recorded."""
    F = pd.read_parquet(_cal_paths()["p1_fills"])
    F = F[F.t_F1 >= 0].reset_index(drop=True)
    rng = np.random.default_rng(seed)
    pick = F.iloc[np.sort(rng.choice(len(F), size=min(n, len(F)), replace=False))]
    cols = ["t_F1", "L", "L_tau", "sidx", "live_from", "life_end", "rung"]
    tasks = [(c, g[cols]) for c, g in pick.groupby("coin")]
    t0 = time.time()
    res = _pmap(_k6_coin, tasks, min(jobs, 4))
    rows = [x for r in res for x in r["rows"]]
    errs = [dict(coin=r["coin"], error=r["error"]) for r in res if "error" in r]
    D = pd.DataFrame(rows)
    out = dict(sampled=int(len(pick)), errors=errs, seconds=time.time() - t0)
    if len(D):
        ok = ~D.agg_missing.astype(bool) & (D.agg_first > 0)
        r1 = (D.c1_first / D.agg_first)[ok]
        okl = ~D.agg_missing.astype(bool) & (D.agg_life > 0)
        rl = (D.c1_life / D.agg_life)[okl]
        q = lambda x, p: float(np.quantile(x, p)) if len(x) else np.nan
        out.update(compared=int(ok.sum()), agg_missing=int(D.agg_missing.astype(bool).sum()),
                   ratio_first=dict(median=q(r1, 0.5), q25=q(r1, 0.25), q75=q(r1, 0.75), within_2x=float(
                       np.mean((r1 >= 0.5) & (r1 <= 2.0))) if len(r1) else np.nan),
                   ratio_life=dict(median=q(rl, 0.5), q25=q(rl, 0.25), q75=q(rl, 0.75)),
                   same_10k_sizing=float(np.mean((D.c1_life[okl] >= 1e4) == (D.agg_life[okl] >= 1e4)))
                   if okl.any() else np.nan)
        D.to_csv(OUT_DIR / "k6_fills.csv", index=False)
    out["passed"] = bool(out.get("compared", 0) >= 0.9 * min(n, len(F)))
    return out


# ============================================================================ K7: ticks and sizes (§10.5)
def _on_grid(x: float, tick: str) -> bool:
    d = Decimal(repr(float(x))) / Decimal(tick)
    return d == d.to_integral_value()


def rh_orders(coin: str, L: float, Q: float, cat: pd.Series) -> list:
    """The orders of one rung on Robinhood, this module's reference coding of the sheet's rule (stinkbid_sheet.rh_orders,
    which K7 checks): limit L on the catalog's price tick (already rounded), quantity Q / L floored to the quantity
    increment; below the minimum order size no order; above the maximum, n = ceil(q / max) near-equal orders, each a
    multiple of the increment within [min, max] (a greedy split into max-size orders can leave a remainder below the
    minimum). Raises ValueError when no split can respect [min, max]."""
    inc = Decimal(str(cat["qty_increment_str"]))
    mx = Decimal(str(cat["max_order_size_str"]))
    mn = Decimal(str(cat["min_order_size_str"]))
    units = int((Decimal(repr(float(Q))) / Decimal(repr(float(L))) / inc).to_integral_value(rounding=ROUND_FLOOR))
    qty = inc * units
    if units <= 0 or qty < mn:
        return []
    mx_units = int((mx / inc).to_integral_value(rounding=ROUND_FLOOR))
    if mx_units < 1:
        raise ValueError(f"{coin}: the maximum order size {mx} is below the quantity increment {inc}")
    n = -(-units // mx_units)
    base, extra = divmod(units, n)
    qs = [inc * (base + 1)] * extra + [inc * base] * (n - extra)
    if sum(qs) != qty or any(q < mn or q > mx for q in qs):
        raise ValueError(f"{coin}: {qty} cannot be split into orders within [{mn}, {mx}]: {qs}")
    return [dict(coin=coin, limit=float(L), qty=str(q)) for q in qs]


def k7_check_orders(orders: pd.DataFrame, cat: pd.DataFrame) -> dict:
    """K7's order check: every order on its coin's Robinhood price tick and quantity increment, within the minimum
    and maximum order size. Returns counts and the violations."""
    c = cat.set_index("coin")
    bad = []
    for r in orders.itertuples():
        x = c.loc[r.coin]
        q = Decimal(str(r.qty))
        if not _on_grid(r.limit, x.price_tick_str):
            bad.append((r.coin, r.limit, str(r.qty), "price off the tick"))
        if (q / Decimal(x.qty_increment_str)) != (q / Decimal(x.qty_increment_str)).to_integral_value():
            bad.append((r.coin, r.limit, str(r.qty), "quantity off the increment"))
        if q < Decimal(x.min_order_size_str) or q > Decimal(x.max_order_size_str):
            bad.append((r.coin, r.limit, str(r.qty), "size outside [min, max]"))
    return dict(orders=int(len(orders)), violations=bad[:50], n_violations=len(bad))


def k7_methods() -> list:
    """The level methods of the engine's programs (stinkbid_engine.PROGRAMS): every one must be tick-checked by
    K7(a)."""
    return sorted({v[0] for p in sbe.PROGRAMS.values() for v in p.variants})


def k7_levels(srcs: list, require_all: bool = True) -> dict:
    """K7(a) (§10.5 "every level is on its venue's tick"): for every source (name, frame with L, n_ticks, tick_str and,
    when present, L_tau and method), L = n tau in exact decimals and L - tau = (n - 1) tau; the methods each source
    covers; coverage = the methods of the engine's programs (k7_methods) checked by a real source, by a synthetic one,
    and by none. ok when no level is off its tick and (require_all; a quick run's reduced K4 programs cannot cover
    them, and a quick run never opens the gate) every method was checked by some source."""
    out = dict(sources={}, levels=0, off_tick=0)
    cov = {"real": set(), "synthetic": set()}
    for name, b in srcs:
        if b is None or not len(b):
            out["sources"][name] = dict(levels=0, off_tick=0, methods=[])
            continue
        L = b.L.to_numpy(float)
        n = b.n_ticks.to_numpy(np.int64)
        ts = b.tick_str.astype(str).to_numpy()
        Lt = b.L_tau.to_numpy(float) if "L_tau" in b else None
        bad = 0
        cache = {}
        for i in range(len(b)):
            tk = cache.get(ts[i])
            if tk is None:
                tk = cache[ts[i]] = Decimal(ts[i])
            if float(Decimal(int(n[i])) * tk) != L[i] or (Lt is not None and
                                                          float(Decimal(int(n[i]) - 1) * tk) != Lt[i]):
                bad += 1
        meth = sorted(set(b["method"].astype(str))) if "method" in b else []
        cov["real" if name.startswith("real") else "synthetic"].update(meth)
        out["sources"][name] = dict(levels=int(len(b)), off_tick=int(bad), methods=meth)
        out["levels"] += int(len(b))
        out["off_tick"] += int(bad)
    req = k7_methods()
    out["coverage"] = dict(required=req, real=sorted(cov["real"] & set(req)),
                           synthetic=sorted(cov["synthetic"] & set(req)),
                           missing=sorted(set(req) - cov["real"] - cov["synthetic"]),
                           not_on_real_data=sorted(set(req) - cov["real"]))
    out["ok"] = bool(out["off_tick"] == 0 and out["levels"] > 0 and not (require_all and out["coverage"]["missing"]))
    return out


def k7_sheet_orders(levels: pd.DataFrame, cat: pd.DataFrame, Qs=(1e3, 1e4, 1e5)) -> dict:
    """K7(b)'s orders: for every reference level (coin, rung, L on Robinhood's tick) and Q, the orders of the SHEET's
    own rule (stinkbid_sheet.rh_orders), which are what K7 checks (k7_check_orders); this module's reference coding
    (rh_orders) beside them. Returns {orders (the sheet's), errors (rungs the sheet's rule could not order),
    rule_mismatch (rungs where the two codings differ)}."""
    from analysis_2026 import stinkbid_sheet as sbsh                 # the sheet stage's module (imported here only)
    c = cat.set_index("coin")
    orders, errors, mism = [], [], []
    for r in levels.itertuples():
        x = c.loc[r.coin]
        for Q in Qs:
            try:
                qs, _ = sbsh.rh_orders(Decimal(repr(float(r.L))), float(Q), x)
            except Exception as e:                                   # the sheet could not order this rung: a failure
                errors.append((r.coin, float(r.rung), float(Q), repr(e)[:160]))
                continue
            orders += [dict(coin=r.coin, rung=float(r.rung), Q=float(Q), limit=float(r.L), qty=str(q)) for q in qs]
            try:
                ref = sorted(Decimal(o["qty"]) for o in rh_orders(r.coin, float(r.L), float(Q), x))
            except ValueError as e:
                ref = [repr(e)]
            if ref != sorted(Decimal(q) for q in qs):
                mism.append((r.coin, float(r.rung), float(Q), [str(q) for q in qs], [str(q) for q in ref]))
    cols = ["coin", "rung", "Q", "limit", "qty"]
    return dict(orders=pd.DataFrame(orders, columns=cols), errors=errors, rule_mismatch=mism)


def k7_ticks(extra_bids: list | None = None, real_levels: list | None = None, require_all: bool = True) -> dict:
    """K7 (§10.5): (a) every level on its venue's tick (k7_levels): the real counts-only calendars (P1 and H4 with
    its placebos), the real level rows of K4's cut coins (every per-coin method), the synthetic K1 / K2 worlds and
    K4's synthetic runs (every program: P1, k = 5 / 12, M1, M2a, M3, M8, H4-all), with every method of the engine's
    programs required; (b) every reference sheet order (the M2 rungs of every U-C coin at the last placement,
    floored to Robinhood's tick with delta recomputed, Q = $1k, $10k and $100k), produced by the sheet's own rule
    (stinkbid_sheet.rh_orders, k7_sheet_orders), is on Robinhood's tick and quantity increment and within the
    minimum and maximum order size, orders above the maximum split (k7_check_orders)."""
    out = dict(levels={}, sheet={})
    srcs = []
    P = _cal_paths()
    for name in ("p1_bids", "h4_bids"):
        if P[name].exists():
            srcs.append((f"real {name}", pd.read_parquet(P[name], columns=["method", "L", "L_tau", "n_ticks",
                                                                           "tick_str"])))
    srcs += list(real_levels or []) + list(extra_bids or [])
    lv = k7_levels(srcs, require_all)
    out["levels"], out["coverage"] = lv["sources"], lv["coverage"]
    # (b) Robinhood reference orders, by the sheet's own rule
    cat = sbd.rh_pairs()
    t0 = pd.Timestamp(END_DAY, tz="UTC").normalize()
    t0 = t0 - pd.Timedelta(days=t0.weekday()) + pd.Timedelta(hours=3, minutes=30)        # the last Monday 03:30
    refs, rounding_bad, skipped = [], [], []
    for coin in sbd.u_c_coins():
        try:
            I = sbl.inputs_at(coin, t0)
        except Exception as e:
            skipped.append((coin, repr(e)[:80]))
            continue
        if not I["ok"] or coin not in set(cat.coin):
            skipped.append((coin, I.get("why", "not in catalog")))
            continue
        x = cat.set_index("coin").loc[coin]
        for k in sbl.M2_K:
            r = sbl.level("M2", I, k=k)
            if r is None:
                continue
            L = r[0]
            Lr, dr = sbl.rh_round(coin, L, inputs=I)
            if not (_on_grid(Lr, x.price_tick_str) and Lr <= L + 1e-12 and np.isfinite(dr)):
                rounding_bad.append((coin, k, L, Lr))
            refs.append(dict(coin=coin, rung=k, L=Lr))
    so = k7_sheet_orders(pd.DataFrame(refs, columns=["coin", "rung", "L"]), cat)
    od = so["orders"]
    chk = k7_check_orders(od, cat) if len(od) else dict(orders=0, n_violations=0, violations=[])
    split = od.groupby(["coin", "rung", "Q"]).size() if len(od) else pd.Series(dtype=int)
    out["sheet"] = dict(rule="stinkbid_sheet.rh_orders", coins=int(od.coin.nunique()) if len(od) else 0,
                        orders=chk["orders"], violations=chk["violations"], n_violations=chk["n_violations"],
                        rule_errors=so["errors"][:20], n_rule_errors=len(so["errors"]),
                        reference_rule_mismatch=so["rule_mismatch"][:20],
                        n_reference_rule_mismatch=len(so["rule_mismatch"]), rounding_violations=rounding_bad,
                        split_rungs=int((split > 1).sum()), skipped=skipped, placement=str(t0))
    if len(od):
        od.to_csv(OUT_DIR / "k7_reference_orders.csv", index=False)
    out["passed"] = bool(lv["ok"] and chk["orders"] > 0 and chk["n_violations"] == 0 and not so["errors"] and
                         not rounding_bad)
    return out


# ============================================================================ K8: venue proxy (§10.5; no outcome)
def k8_venue() -> dict:
    """K8 (§10.5, no outcome): for every real P1 F1 fill, whether it also fills under F3 (index, s = 1% and 3%), F3d
    (s = 1%), F5 (perpetual) and F3 with the index in USD (hourly stablecoin proxy), whether F3 is unverifiable
    (no index minute) or the index minute is an outage, and the share each removes, overall and by event (episode)."""
    F = pd.read_parquet(_cal_paths()["p1_fills"])
    F = F[F.t_F1 >= 0].copy()
    flags = {}
    for c, nm in (("t_F3_1", "F3_1"), ("t_F3_3", "F3_3"), ("t_F3d_1", "F3d_1"), ("t_F5", "F5"),
                  ("t_F3usd_1", "F3usd_1"), ("t_F3usd_3", "F3usd_3")):
        if c in F:
            flags[nm] = F[c].to_numpy(float) >= 0
    for c in ("idx_missing", "idx_outage", "rh_outage"):
        if c in F:
            flags[c] = F[c].astype(str).isin(["True", "1", "1.0"]).to_numpy()
    D = pd.DataFrame(flags)
    D["episode"] = F.episode.to_numpy()
    D["day"] = pd.to_datetime(F.t_F1.to_numpy(np.int64) * MIN_NS, utc=True).strftime("%Y-%m-%d")
    D["rung"] = F.rung.to_numpy()
    rem = {k: float(1 - D[k].mean()) for k in ("F3_1", "F3_3", "F3d_1", "F3usd_1", "F3usd_3") if k in D}
    also = {k: float(D[k].mean()) for k in ("F5",) if k in D}
    ev = D.groupby("episode").agg(first_day=("day", "min"), last_day=("day", "max"), fills=("rung", "size"),
                                  **{f"kept_{k}": (k, "mean") for k in ("F3_1", "F3_3", "F3d_1", "F5", "F3usd_1")
                                     if k in D},
                                  **{k: (k, "mean") for k in ("idx_missing", "idx_outage", "rh_outage") if k in D})
    ev = ev.sort_values("fills", ascending=False)
    ev.to_csv(OUT_DIR / "k8_events.csv")
    by_rung = D.groupby("rung")[[k for k in ("F3_1", "F3_3", "F3d_1", "F5") if k in D]].mean()
    out = dict(fills=int(len(D)), removed_share=rem, also_filled_share=also,
               unverifiable=int(D.idx_missing.sum()) if "idx_missing" in D else None,
               index_outage=int(D.idx_outage.sum()) if "idx_outage" in D else None,
               rh_outage=int(D.rh_outage.sum()) if "rh_outage" in D else None,
               kept_by_rung={f"{k:g}": v for k, v in by_rung.to_dict("index").items()},
               events=int(len(ev)), top_events=ev.head(10).reset_index().to_dict("records"))
    out["passed"] = bool(len(D) > 0 and all(k in D for k in ("F3_1", "F3_3", "F3d_1", "F5")))
    return out


# ============================================================================ resumable control results
SOURCES = ("stinkbid_controls.py", "stinkbid_engine.py", "stinkbid_levels.py", "stinkbid_data.py", "stinkbid_stats.py")


def src_hash() -> str:
    """sha256 of the five modules' sources: a cached control result is reused only under the same code."""
    import hashlib as _h
    h = _h.sha256()
    for f in SOURCES:
        h.update((ROOT / "analysis_2026" / f).read_bytes())
    return h.hexdigest()[:16]


_K1_CODE = ("_k2_stats", "SynthSpec", "_t4", "_market_globals", "_coin_params", "_round_tick", "_tick_float", "SynthMarket",
            "_m7_frames", "_o_next_live", "_o_fills", "_o_exits", "_dec_floor_n", "_dec_val", "OracleCoin", "_clock",
            "rule_m_oracle", "_rule_m_py", "oracle_market", "oracle_engine_twins", "_pmap", "_chunks", "_oracle_task",
            "oracle_parallel", "_twin_task", "engine_twins_parallel", "k1_cfg", "_mean_se", "compare_k1", "_exact_ok",
            "fill_rates", "_k_engine", "_audit_counts", "run_k1_world", "_count_task", "oracle_rates", "rate_errors",
            "tune_k1b", "k1_specs", "_strip", "k1d_haircut", "run_k1", "compute_k1k2", "_compact_audit",
            "_k1c_table", "_cl_mean", "_usable", "k1c_report")
_K4_CODE = ("SynthSpec", "_t4", "_market_globals", "_coin_params", "_round_tick", "_tick_float", "SynthMarket",
            "_pmap", "_chunks", "Pert", "_pert_frame", "_daily_bars", "K4Market", "k4_spec", "_k4_run", "_k4_keyed",
            "_nk", "_pre", "k4_compare", "draw_cuts", "_k4_world_runs", "_k4_trim", "_after_print", "_k4_task", "k4_synthetic",
            "_k4_syn_raw", "compute_k4_synthetic", "_compact_audit", "_k4_bid_tables")
_K4_RAW_CODE = ("SynthSpec", "_t4", "_market_globals", "_coin_params", "_round_tick", "_tick_float", "SynthMarket",
                "_pmap", "_chunks", "Pert", "_pert_frame", "_daily_bars", "K4Market", "k4_spec", "_k4_run", "_k4_keyed",
                "draw_cuts", "_k4_world_runs", "_k4_trim", "_after_print", "_k4_task", "_k4_syn_raw", "_compact_audit")
_CODE_CONSTS = ("SEED", "SYN_START", "END_DAY", "K1_COINS", "K1_SE_MULT", "K1B_TOL", "K2_T", "K1B_JUMP_RATE",
                "K1B_JUMP_MEAN", "K1_EXITS", "K1C_EXITS", "EXIT_DEF", "K4_CUTS", "K4_COUNT_PROGRAMS", "K4_OUTCOME_PROGRAMS", "BID_KEY",
                "BID_COLS_CMP", "FILL_COLS_CMP", "PRICE_COLS", "VOL_COLS", "C_RH")


def _const_repr(c) -> bytes:
    if hasattr(c, "co_code"):
        return _code_sig(c)
    if isinstance(c, (frozenset, set)):                               # set order depends on the hash seed
        return b"{" + b",".join(sorted(_const_repr(x) for x in c)) + b"}"
    if isinstance(c, tuple):
        return b"(" + b",".join(_const_repr(x) for x in c) + b")"
    return repr(c).encode()


def _code_sig(co) -> bytes:
    """The compiled code of a function without its line numbers (bytecode, names, constants, nested code), the same
    in every process."""
    parts = [co.co_code, repr(co.co_names).encode(), repr(co.co_varnames).encode()]
    for c in co.co_consts:
        parts.append(_const_repr(c))
    return b"|".join(parts)


def _obj_sig(obj) -> bytes:
    obj = getattr(obj, "py_func", obj)                                # numba dispatchers
    if hasattr(obj, "__code__"):
        return _code_sig(obj.__code__)
    if isinstance(obj, type):
        parts = [obj.__name__.encode()]
        for k, v in sorted(vars(obj).items()):
            v = getattr(v, "__func__", v)
            if hasattr(v, "__code__"):
                parts.append(k.encode() + _code_sig(v.__code__))
            elif k == "__dataclass_fields__":
                parts.append(repr([(f.name, f.default) for f in v.values()]).encode())
        return b"|".join(parts)
    return repr(obj).encode()


def code_hash(names) -> str:
    """sha256 of the dependency modules' sources (engine, levels, data, stats) and of the compiled code of the named
    functions / classes of this module plus its constants: a cached control result is reused only under the same
    code; edits elsewhere in this module (run(), K5-K8, docstrings of other functions) do not invalidate it."""
    import hashlib as _h
    h = _h.sha256()
    for f in SOURCES[1:]:
        h.update((ROOT / "analysis_2026" / f).read_bytes())
    g = globals()
    for n in names:
        h.update(_obj_sig(g[n]))
    for c in _CODE_CONSTS:
        h.update(repr(g[c]).encode())
    return h.hexdigest()[:16]


def _cache_path(name: str) -> Path:
    return WORK / f"run_{name}_{code_hash(_K1_CODE if name == 'k1k2' else _K4_CODE)}.pkl"


def _cache_load(name: str, check=None):
    import pickle
    f = _cache_path(name)
    if not f.exists():
        return None
    with open(f, "rb") as fh:
        x = pickle.load(fh)
    if check is not None and not check(x):
        return None
    return x


def _cache_save(name: str, payload: dict) -> None:
    import pickle
    WORK.mkdir(parents=True, exist_ok=True)
    f = _cache_path(name)
    tmp = f.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        pickle.dump(payload, fh)
    os.replace(tmp, f)


def _compact_audit(A):
    if A is None or not len(A):
        return A
    ty = A["type"].astype(str)
    return A[ty.isin(["violation", "gap", "count"])].copy()


_K3_CODE = ("k3_setup", "_k3_load", "_k3_exit", "_k3_paths", "_k3_twins", "_k3_delta", "k3_sim", "_power_task",
            "k3_power", "run_k3", "_hour_idx", "rule_m_oracle", "_t4", "_pmap", "_chunks", "_pw_row", "_pw_decide",
            "_calib_crit")
_K6_CODE = ("_k6_coin", "k6_capacity", "_pmap", "_chunks")


def _file_hash(paths) -> str:
    h = hashlib.sha1()
    for p in paths:
        p = Path(p)
        h.update(p.read_bytes() if p.exists() else b"missing")
    return h.hexdigest()[:12]


def run_cached(name: str, codes, key_obj, fn, log=_say):
    """fn() cached in data/stinkbid/controls/ under (the code of `codes`, key_obj): a control interrupted after this
    step (a crash, a container restart) reuses it under the same code and inputs."""
    import pickle
    key = hashlib.sha1((json.dumps(_js(key_obj), sort_keys=True) + code_hash(codes)).encode()).hexdigest()[:16]
    f = WORK / f"ctl_{name}_{key}.pkl"
    if f.exists():
        with open(f, "rb") as fh:
            x = pickle.load(fh)
        log(f"{name}: reusing the cached result {f.name}")
        return x
    x = fn()
    WORK.mkdir(parents=True, exist_ok=True)
    with open(f.with_suffix(".tmp"), "wb") as fh:
        pickle.dump(x, fh)
    os.replace(f.with_suffix(".tmp"), f)
    return x


def compute_k1k2(jobs: int, target: dict | None, quick: bool = False, log=_say) -> dict:
    """K1 and K2 with everything run() needs afterwards (files, summary sections, audit records, bids), cached under
    the source hash and the target rates."""
    if not quick:
        hit = _cache_load("k1k2", lambda x: x.get("target") == target)
        if hit is not None:
            log(f"K1/K2: reusing the result computed at {hit.get('computed')} under the same code and targets")
            return hit
    specs = k1_specs() if not quick else k1_specs(n_coins=8, start="2019-11-01", end="2022-03-31")
    R = run_k1(jobs, target if not quick else None, specs, log=log)
    worlds = R.pop("_worlds")
    payload = dict(target=target, computed=pd.Timestamp.now(tz="UTC").isoformat(), R=R,
                   records=[(f"synthetic {n}", w["record"]) for n, w in worlds.items()],
                   bids=[(f"synthetic {n}", w["bids"]) for n, w in worlds.items()])
    if not quick:
        _cache_save("k1k2", payload)
    return payload


def compute_k4_synthetic(jobs: int, quick: bool = False, log=_say) -> dict:
    """K4 / K4b on the synthetic world, cached under the source hash."""
    if not quick:
        hit = _cache_load("k4syn")
        if hit is not None:
            log(f"K4 synthetic: reusing the result computed at {hit.get('computed')} under the same code")
            return hit
    syn = k4_synthetic(K4_CUTS if not quick else 3, jobs, log=log,
                       programs=(K4_OUTCOME_PROGRAMS, K4_COUNT_PROGRAMS) if not quick else (("P1",), ("P1", "P1-90")),
                       cache=not quick)
    payload = dict(computed=pd.Timestamp.now(tz="UTC").isoformat(), syn=syn)
    if not quick:
        _cache_save("k4syn", payload)
    return payload


# ============================================================================ run: every control, summary.json
CONTROLS = ("K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8")


def _txt(S: dict) -> str:
    cal = S.get("calendars") if isinstance(S.get("calendars"), dict) else {}
    L = [f"Stink-bid controls (STINKBID_PREREG.md §10.5) - {S.get('finished', '')}",
         f"all_passed: {S.get('all_passed')}   (quick: {S.get('quick')}, partial: {S.get('partial')})",
         f"real calendars: key {cal.get('key')} ({'reused' if cal.get('reused') else 'built'} "
         f"{cal.get('built', '')}); code {S.get('code', {}).get('src_hash')}", ""]
    for k in CONTROLS:
        v = S.get(k)
        if not isinstance(v, dict):
            continue
        L.append(f"{k}: {'PASSED' if v.get('passed') else 'FAILED'}" + (f" - error: {v['error']}" if v.get("error")
                                                                          else ""))
        for line in v.get("lines", []):
            L.append("    " + line)
    L += ["", "Timings (s): " + ", ".join(f"{k} {v:.0f}" for k, v in S.get("timings", {}).items())]
    return "\n".join(L) + "\n"


def _f(x, d=4):
    try:
        return f"{float(x):+.{d}f}"
    except (TypeError, ValueError):
        return "n/a"


def _k3_cache_key(args: dict, cal_key) -> dict:
    """K3's cache key: its sizes, the calendar files' hash and the calendars' key (code, configuration and data they
    were built under), the scenarios and the power grid."""
    P = _cal_paths()
    return dict(args, cal=_file_hash([P["p1_fills"], P["h4_fills"], P["h4_bids"]]), cal_key=cal_key, sc=K3_SC,
                h0=K3_H0, pg=POWER_GRID, pc=POWER_CONC, consts=[K3_SIG_M, K3_BETA, K3_TW, K3_STOP_M, K3_CRASH_COINS])


def _k6_cache_key(n: int, cal_key) -> dict:
    """K6's cache key: the sample size, the P1 calendar file's hash and the calendars' key."""
    return dict(n=n, cal=_file_hash([_cal_paths()["p1_fills"]]), cal_key=cal_key)


def run(out=None, jobs: int = 4, quick: bool = False, only=None, n_reps: int | None = None, log=_say,
        rebuild_calendars: bool = False) -> dict:
    """Every control of §10.5 at its pre-registered size (quick=True: small sizes, never a valid gate), writing
    summary.json (with all_passed), summary.txt and the per-control files to `out` (default
    analysis_2026/results_stinkbid/controls/). The real calendars are rebuilt when their key (code, configuration,
    data) changed, or always with rebuild_calendars. A crashed control counts as failed. Returns the summary."""
    global OUT_DIR
    OUT_DIR = Path(out) if out else OUT_DIR
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    only = tuple(only) if only else CONTROLS
    T0 = time.time()
    S = dict(prereg="analysis_2026/STINKBID_PREREG.md (FROZEN 2026-11-18, commit 72ac2a4) §10.5", quick=bool(quick),
             partial=only != CONTROLS, valid_gate=bool(not quick and only == CONTROLS), jobs=jobs,
             started=pd.Timestamp.now(tz="UTC").isoformat(), timings={}, code=dict(src_hash=src_hash()))
    engine_records = []
    synth_bids = []
    real_levels = []

    def guard(name, fn):
        t = time.time()
        try:
            fn()
        except Exception as e:                                      # a crashed control stops the study
            S[name] = dict(passed=False, error=repr(e)[:500], traceback=traceback.format_exc()[-3000:])
            log(f"{name} crashed: {e!r}")
        S["timings"][name] = time.time() - t

    # ---- 0. the real fill calendars (counts only)
    def cal():
        S["calendars"] = real_calendars(jobs, force=rebuild_calendars, log=log)
        S["calendar_key"] = S["calendars"].get("key")
        S["code"]["calendar_key"] = S["calendars"].get("key_parts")
        S["real_p1_rates"] = real_p1_rates()
    guard("calendars", cal)

    # ---- K1, K2
    def k12():
        target = S.get("real_p1_rates") if not quick else None
        try:
            P = compute_k1k2(jobs, target, quick, log)
        except cf.BrokenExecutor as e:                           # BrokenProcessPool: a worker was killed
            # a worker lost to the session's memory limit (a full-size world's engine, oracle or twin check with
            # `jobs` workers): retried once with half the workers; the worlds already done are reused from their
            # caches (keyed by code and spec, not by the worker count, which does not change any result)
            j2 = max(1, jobs // 2)
            log(f"K1/K2: a worker process was lost ({e!r}); retrying with {j2} workers")
            import gc
            gc.collect()
            S.setdefault("retries", []).append(dict(control="K1", error=repr(e)[:200], jobs=j2))
            P = compute_k1k2(j2, target, quick, log)
        R = P["R"]
        engine_records.extend(P["records"])
        synth_bids.extend(P["bids"])
        k1, k2 = R["K1"], R["K2"]
        _write_json(OUT_DIR / "k1.json", dict(R, K2=None))
        _write_json(OUT_DIR / "k2.json", k2)
        e = {n: k1[n]["exits"]["FLIP"] for n in ("K1a", "K1b")}
        lines = [f"{n}: {k1[n]['fills']} fills; X-FLIP r_f engine {_f(e[n]['engine_r'])} vs oracle "
                 f"{_f(e[n]['oracle_r'])} (2 SE = {2 * e[n]['se_r']:.4f}); Delta engine {_f(e[n]['engine_delta'])} vs "
                 f"oracle {_f(e[n]['oracle_delta'])} (2 SE = {2 * e[n]['se_delta']:.4f}); "
                 f"{'pass' if k1[n]['passed'] else 'FAIL'} (all K1 exits)" for n in ("K1a", "K1b")]
        if "wrong_engines" in k1:
            for fp, w in k1["wrong_engines"].items():
                lines.append(f"wrong engine (fill at the minute's {fp}): r_f {_f(w['engine_r'])}, "
                             f"{w['diff_r_se']:+.1f} SE from the oracle: {'fails (as required)' if w['fails'] else 'PASSES (bad)'}")
        if "fill_counts" in k1.get("K1b", {}):
            fc = k1["K1b"]["fill_counts"]
            lines.append("K1b fill rates vs real P1: " + ", ".join(
                f"k={k} {fc['synthetic'][k]['rate']:.2%} vs {fc['real_rates'][k]:.2%} ({v:+.0%})"
                for k, v in fc["rel_error"].items()) + f" -> {'within' if fc['within_25pct'] else 'OUTSIDE'} +-25%")
        c = k1["K1c"]
        lines.append(f"K1c (what regime timing alone produces: K1c minus its paired null K1c0, so the minute-level "
                     f"gap-through cost cancels): Delta X-FLIP {_f(c['FLIP']['engine_delta_RH'])} (SE "
                     f"{c['FLIP']['se']:.4f}), X-HOLD-90 {_f(c['HOLD90']['engine_delta_RH'])} (SE "
                     f"{c['HOLD90']['se']:.4f}) at C-RH, month-block CR1 SE (G* {c['HOLD90']['gstar']:.1f}), "
                     f"{c['HOLD90']['n']} paired X-HOLD-90 fills; oracle {_f(c['FLIP']['oracle_delta_RH'])} / "
                     f"{_f(c['HOLD90']['oracle_delta_RH'])}")
        lines.append(f"K1c diagnostics (not regime timing): K1c's total Delta {_f(c['total']['FLIP']['engine_delta_RH'])}"
                     f" / {_f(c['total']['HOLD90']['engine_delta_RH'])} (clustered SE {c['total']['FLIP']['se']:.4f} / "
                     f"{c['total']['HOLD90']['se']:.4f}); the minute-level cost alone (K1c0) "
                     f"{_f(c['minute_level']['FLIP']['engine_delta_RH'])} / "
                     f"{_f(c['minute_level']['HOLD90']['engine_delta_RH'])}; "
                     f"{c['gap_through']['share_open_below_L']:.0%} of K1c's fill minutes opened below L")
        d = k1["K1d"]["HOLD90"]
        lines.append(f"K1d: X-HOLD-90 fills closed at the delisting value {d['fills_delisted']}/{d['fills']}, twins "
                     f"{d['twins_delisted']}/{d['twins']}; every position open at the end of trading took the haircut: "
                     f"{d['conditional_ok']}; engine vs oracle twin delistings {d['diff_se']:+.2f} SE: "
                     f"{'pass' if k1['K1d']['passed'] else 'FAIL'}")
        S["K1"] = dict(passed=k1["passed"], K1a=k1["K1a"], K1b=k1["K1b"], K1c=k1["K1c"], K1d=k1["K1d"],
                       wrong_engines=k1.get("wrong_engines"), exact_diagnostics={n: v["exact_ok"] for n, v in
                                                                                 k1["diagnostics"].items()},
                       lines=lines)
        S["K2"] = dict(passed=k2["passed"], FLIP=k2["FLIP"], FLIP_bot=k2["FLIP_bot"],
                       lines=[f"{ex}: Delta (C-RH) {_f(k2[ex]['delta_RH'])}, t {k2[ex]['t']:.2f} (G* "
                              f"{k2[ex]['gstar']:.1f}), oracle match {k2[ex]['oracle_match']}"
                              for ex in ("FLIP", "FLIP_bot")])
    if "K1" in only or "K2" in only:
        guard("K1", k12)
        if "K2" not in S and "K1" in S:
            S["K2"] = dict(passed=False, error="not run: K1 crashed")

    # ---- K3
    def k3():
        reps = n_reps or (K3_REPS if not quick else 40)
        args = dict(n_reps=reps, n_power=(300 if not quick else 20), B=(sbs.B_BOOT if not quick else 199))
        key = _k3_cache_key(args, S.get("calendar_key"))
        fn = lambda: run_k3(reps, jobs, n_power=args["n_power"], B=args["B"], log=log)
        summ, calib, power, d11 = fn() if quick else run_cached("k3", _K3_CODE, key, fn, log)
        _write_json(OUT_DIR / "k3_calibration.json", calib)
        _write_json(OUT_DIR / "power.json", power)
        d11.to_parquet(OUT_DIR / "d11_null.parquet")
        lines = []
        for t_, v in summ["tests"].items():
            worst = v["by_scenario"][v["worst_scenario"]]
            fp = worst["false_pass"]
            lines.append(f"{t_}: rule {v['rule']} (worst scenario {v['worst_scenario']}: false PASS " +
                         ", ".join(f"{float(lv):.2%} -> {x['rate']:.2%} [CI up {x['ci95'][1]:.2%}]"
                                   for lv, x in fp.items()) +
                         f"; NO EDGE miss {worst['noedge_miss']['rate']:.2%})")
        for t_, d in power.get("mde", {}).items():
            rule = power.get("rule", {}).get(t_, "nominal")
            crit = next((v.get("crit_calibrated") for v in d.values() if v.get("crit_calibrated") is not None), None)
            lines.append(f"{t_} MDE ({rule} rule" + (f", critical t {crit:.2f}" if crit is not None else "") +
                         ", base / high / hetero): " + " / ".join(
                             f"{d[s]['mde_rule']:.2%}" for s in d if d[s].get("mde_rule") is not None) +
                         (" (nominal formula " + " / ".join(f"{d[s]['mde_formula']:.2%}" for s in d
                                                           if d[s].get("mde_formula") is not None) + ")"
                          if rule != "nominal" else ""))
        S["K3"] = dict(summ, calibration_file="k3_calibration.json", lines=lines)
        S["K3"]["passed"] = bool(summ["passed"])
    if "K3" in only:
        guard("K3", k3)

    # ---- K4
    def k4():
        syn = dict(compute_k4_synthetic(jobs, quick, log)["syn"])
        T = syn.pop("_table")
        engine_records.extend(syn.pop("_audits", []))                        # K5 aggregates K4's engine audits too
        synth_bids.extend(syn.pop("_bids", []))                              # K7 checks every program's levels
        T.to_csv(OUT_DIR / "k4_comparisons.csv", index=False)
        P = _cal_paths()
        rc = None
        if P["p1_fills"].exists():
            F = pd.read_parquet(P["p1_fills"])
            F = F[F.t_F1 >= 0]
            lo, hi = _tmin("2020-03-01"), _tmin("2026-10-15")
            pl = _tmin(pd.date_range("2020-01-06 03:30", "2026-11-09 03:30", freq="7D", tz="UTC"))
            u = sbd.universes()
            q1 = sorted(u.coin[u.U_Q1.astype(bool)].unique())
            rc = draw_cuts(K4_CUTS if not quick else 4, pl, F.t_F1.to_numpy(np.int64), lo, hi,
                           np.random.default_rng(SEED + 44), F.coin.to_numpy(), q1)
            # a cut away from a fill takes a coin that is a U-Q1 member in the cut's month
            rq = np.random.default_rng(SEED + 45)
            mem = u[u.U_Q1.astype(bool)].groupby("month").coin.apply(lambda x: sorted(x)).to_dict()
            for i, r in rc.iterrows():
                if r.why != "crash_hour":
                    m_ = pd.Timestamp(int(r.t) * MIN_NS, tz="UTC").strftime("%Y-%m")
                    if mem.get(m_):
                        rc.loc[i, "coin"] = str(rq.choice(mem[m_]))
            rc.to_csv(OUT_DIR / "k4_real_cuts.csv", index=False)
        ru = k4_real_universes(rc, jobs) if rc is not None else dict(ok=False, error="no real calendar")
        rl = k4_real_levels(rc, jobs) if rc is not None else dict(ok=False)
        real_levels.append(("real K4 level rows (every per-coin method at the cut coins' placements)",
                            rl.pop("_levels", None)))
        rf = k4_real_fills(rc, jobs, n=(24 if not quick else 2)) if rc is not None else dict(ok=False)
        if rf.get("_audit") is not None:
            engine_records.append(("real K4 fill runs (base and perturbed)", rf["_audit"]))
        rf.pop("_audit", None)
        k4j = dict(synthetic=syn, real_universes=ru, real_levels=rl, real_fills=rf)
        _write_json(OUT_DIR / "k4.json", k4j)
        passed = syn["ok"] and ru.get("ok") and rl.get("ok") and rf.get("ok")
        S["K4"] = dict(passed=bool(passed), synthetic=dict(ok=syn["ok"], cuts=syn["n_cuts"], by_why=syn["by_why"],
                                                           worlds=syn["worlds"], comparisons=syn["comparisons"],
                                                           failures=syn["failures"],
                                                           compared=syn["compared_totals"]),
                       real_universes=dict(ok=ru.get("ok"), rows=ru.get("rows_compared"),
                                           changed=len(ru.get("changed", []))),
                       real_levels=dict(ok=rl.get("ok"), rows=rl.get("rows_compared"),
                                        changed=len(rl.get("changed", []))),
                       real_fills=dict(ok=rf.get("ok"), runs=rf.get("runs"), failures=rf.get("n_failures"),
                                       cuts_by_why=rf.get("by_why")),
                       lines=[f"synthetic: {syn['n_cuts']} cuts ({syn['by_why']}) x scale / delete / 3-day gap, "
                              f"{syn['comparisons']} run comparisons, {syn['failures']} failing; compared "
                              f"{syn['compared_totals']}",
                              f"real universes: {ru.get('rows_compared')} rows before the cut, "
                              f"{len(ru.get('changed', []))} cuts changed",
                              f"real levels: {rl.get('rows_compared')} level rows, {len(rl.get('changed', []))} changed",
                              f"real fills and capacity: {rf.get('runs')} runs on {rf.get('cuts')} cuts "
                              f"({rf.get('by_why')}), {rf.get('n_failures')} failing"])
    if "K4" in only:
        guard("K4", k4)

    # ---- K5 .. K8
    def k5():
        r = k5_audit(engine_records, jobs, real_reaudit=not quick)
        _write_json(OUT_DIR / "k5.json", r)
        S["K5"] = dict(passed=r["passed"], violations=r["violations"], gaps=r["gaps"], checks=r["checks"],
                       real_reaudit=r.get("real_reaudit", {}).get("fills"),
                       lines=[f"{r['checks']} engine checks, {r['violations']} violations, {r['gaps']} gap-through "
                              f"fills listed; real P1 re-audit: {r.get('real_reaudit', {}).get('fills')} fills, "
                              f"{r.get('real_reaudit', {}).get('violations')} violations, "
                              f"{r.get('real_reaudit', {}).get('gap_through')} gap-through"])
    if "K5" in only:
        guard("K5", k5)

    def k6():
        n6 = K6_FILLS if not quick else 5
        fn = lambda: k6_capacity(n6, jobs)
        r = fn() if quick else run_cached("k6", _K6_CODE, _k6_cache_key(n6, S.get("calendar_key")), fn, log)
        _write_json(OUT_DIR / "k6.json", r)
        S["K6"] = dict(passed=r["passed"], **{k: r.get(k) for k in ("sampled", "compared", "agg_missing",
                                                                     "ratio_first", "ratio_life", "same_10k_sizing")},
                       lines=[f"{r.get('compared')} of {r.get('sampled')} fills compared; C1/aggTrades first window "
                              f"median {r.get('ratio_first', {}).get('median', float('nan')):.2f}, life median "
                              f"{r.get('ratio_life', {}).get('median', float('nan')):.2f}"])
    if "K6" in only:
        guard("K6", k6)

    def k7():
        r = k7_ticks(synth_bids, real_levels, require_all=not quick)
        _write_json(OUT_DIR / "k7.json", r)
        cv, sh = r["coverage"], r["sheet"]
        S["K7"] = dict(passed=r["passed"], levels=r["levels"], coverage=cv,
                       sheet={k: sh[k] for k in ("rule", "coins", "orders", "n_violations", "n_rule_errors",
                                                 "n_reference_rule_mismatch", "split_rungs")},
                       lines=[f"levels off tick: {sum(v['off_tick'] for v in r['levels'].values())} of "
                              f"{sum(v['levels'] for v in r['levels'].values())} in {len(r['levels'])} sources; "
                              f"methods checked on real levels {cv['real']}, on synthetic levels {cv['synthetic']}, "
                              f"by none {cv['missing']}",
                              f"reference Robinhood orders by the sheet's own rule ({sh['rule']}): {sh['orders']} "
                              f"({sh['coins']} coins), {sh['n_violations']} violations, {sh['n_rule_errors']} rungs "
                              f"it could not order, {sh['split_rungs']} rungs split at the maximum size; this "
                              f"module's coding of the rule differs on {sh['n_reference_rule_mismatch']}"])
    if "K7" in only:
        guard("K7", k7)

    def k8():
        r = k8_venue()
        _write_json(OUT_DIR / "k8.json", r)
        S["K8"] = dict(passed=r["passed"], fills=r["fills"], removed_share=r["removed_share"],
                       unverifiable=r["unverifiable"],
                       lines=[f"{r['fills']} P1 fills: removed by " + ", ".join(f"{k} {v:.1%}" for k, v in
                                                                              r["removed_share"].items()) +
                              f"; F5 also fills {r['also_filled_share'].get('F5', float('nan')):.1%}; "
                              f"F3-unverifiable {r['unverifiable']}"])
    if "K8" in only:
        guard("K8", k8)

    S["finished"] = pd.Timestamp.now(tz="UTC").isoformat()
    S["seconds"] = time.time() - T0
    ok = all(isinstance(S.get(k), dict) and S[k].get("passed") is True for k in only)
    ok &= not (isinstance(S.get("calendars"), dict) and S["calendars"].get("passed") is False)   # a crashed stage
    S["all_passed"] = bool(ok and not quick and only == CONTROLS)
    S["controls_passed"] = {k: bool(isinstance(S.get(k), dict) and S[k].get("passed")) for k in only}
    _write_json(OUT_DIR / "summary.json", S)
    (OUT_DIR / "summary.txt").write_text(_txt(S))
    log(_txt(S))
    return S


# ============================================================================ selftest (small sizes, synthetic only)
class _DecisionLeakMarket(K4Market):
    """Selftest only: a planted look-ahead that decides fills. When the mean close of the day after the cut, read in
    this world's own (possibly perturbed) minutes, is below thr[coin], the lows of the traded minutes of the hour
    before the cut are pulled to half that mean, which fills every resting bid above it; in the world scaled x 1.5
    from the cut the mean is above the threshold and nothing is pulled. Fill decisions stamped before the cut then
    differ in one world only, with or without capacity."""

    def __init__(self, spec: SynthSpec, pert: Pert, thr: dict):
        super().__init__(spec, pert)
        self.thr = dict(thr)

    def raw(self, coin: str) -> dict:
        fr = K4Market.raw(self, coin)
        k = fr["m1"]
        tm = _tmin(k.open_time)
        fut = k.close.to_numpy(float)[(tm >= self.pert.t) & (tm < self.pert.t + DAY_M)]
        if len(fut) and fut.mean() < self.thr.get(coin, -np.inf):
            k = k.copy()
            w = (tm >= self.pert.t - 60) & (tm < self.pert.t) & (k.trades.to_numpy() > 0)
            k["low"] = np.where(w, np.minimum(k.low.to_numpy(float), 0.5 * fut.mean()), k.low.to_numpy(float))
            fr["m1"] = k
        return fr

    def panel(self) -> dict:
        saved = dict(_PANEL)                                         # never share K4Market's panel cache
        _PANEL.clear()
        try:
            return K4Market.panel(self)
        finally:
            _PANEL.clear()
            _PANEL.update(saved)


def _st_rule_m(say):
    rng = np.random.default_rng(3)
    tm = rng.integers(_tmin("2019-01-01"), _tmin("2027-06-01"), 30000)
    edges = []
    for y in range(2019, 2028):
        for d in list(pd.date_range(f"{y}-03-05", f"{y}-03-16", freq="D")) + \
                list(pd.date_range(f"{y}-10-29", f"{y}-11-08", freq="D")):
            edges.append(np.arange(_tmin(d), _tmin(d) + DAY_M, 11))
    tm = np.r_[tm, np.concatenate(edges)]
    a = rule_m_oracle(tm)
    sub = tm[rng.choice(len(tm), 4000, replace=False)]
    assert np.array_equal(rule_m_oracle(sub), np.array([_rule_m_py(x) for x in sub])), \
        "rule M: pandas and datetime codings differ"
    assert np.array_equal(a, sbe.rule_m(tm)), "rule M: the oracle and the engine differ"
    say(f"  rule M: oracle (pandas zones) = plain datetime on 4,000 minutes = engine on {len(tm):,} minutes")


def _st_oracle_hand(say):
    """Hand-built minute arrays with known oracle answers: a trade-through fill, a gap-through fill, a marketable
    sell, a target fill one tick through, a time stop, a delisting value."""
    t = np.arange(100, dtype=np.int64)
    o = np.full(100, 10.0)
    h = np.full(100, 10.1)
    live = np.ones(100, bool)
    lo_n = np.full(100, 99, np.int64)                                    # ticks of 0.1
    lo_n[5] = 95
    live[3] = False
    lo_n[3] = 10
    f = _o_fills(t, lo_n, live, np.array([1, 1]), np.array([50, 4]), np.array([95, 95]))
    assert f.tolist() == [5, -1], f                                      # a dead minute never fills; life ends
    nxt = _o_next_live(live)
    h2 = h.copy()
    h2[20] = 10.6
    o2 = o.copy()
    o2[30] = 11.0
    k, i, px = _o_exits(t, o2, h2, nxt, np.array([10, 30, 10, 3]), np.array([40, 60, 15, 50]),
                        np.array([10.5, 10.5, 10.5, np.inf]), np.array([10.6, 10.6, 10.6, np.inf]), 99, False, 99)
    assert k.tolist() == [0, 1, 2, 2] and i.tolist() == [20, 30, 15, 50] and px.tolist() == [10.5, 11.0, 10.0, 10.0]
    k, i, px = _o_exits(t[:60], o[:60], h[:60], _o_next_live(live[:60]), np.array([10]), np.array([80]),
                        np.array([np.inf]), np.array([np.inf]), 59, True, 99)
    assert k.tolist() == [3], k                                          # trading stopped: the delisting value
    say("  oracle on hand-built minutes: trade-through fill, dead minute, life end, target one tick through, "
        "marketable open, time stop, hold, delisting value")


def _st_k1_k2(say, jobs):
    t = time.time()
    specs = k1_specs(n_coins=6, start="2019-11-01", end="2021-12-31")
    w = run_k1_world(specs["K1b"], jobs, wrong=("close", "low"))
    c = w["compare"]
    assert w["exact_ok"], ("engine and oracle differ fill by fill", c)
    assert w["engine_twins"]["n"] > 0 and w["engine_twins"]["n_mismatch"] == 0 and \
        w["engine_twins"]["n_ineligible"] == 0, w["engine_twins"]
    assert all(e["passed"] for e in c["exits"].values()), c["exits"]
    for fp in ("close", "low"):
        assert w[f"wrong_{fp}"]["fails"], (fp, w[f"wrong_{fp}"])
    e = c["exits"]["FLIP"]
    say(f"  K1b small ({c['fills']['engine']} fills on {specs['K1b'].n_coins} coins): engine = oracle fill by fill "
        f"(bids, minutes, X-FLIP / X-FLIP-bot / X-HOLD-90 returns, kinds, alert a_f; {w['engine_twins']['n']} engine "
        f"twins recomputed); mean r_f {e['engine_r']:+.4f} vs oracle {e['oracle_r']:+.4f}; wrong engines: close "
        f"{w['wrong_close']['diff_r_se']:+.1f} SE, low {w['wrong_low']['diff_r_se']:+.1f} SE -> both fail K1b "
        f"({time.time() - t:.0f}s)")
    # K1d small: delistings taken at equal rates
    t = time.time()
    sd = replace(specs["K1d"], n_coins=8, delist_n=5)
    wd = run_k1_world(sd, jobs)
    hd = k1d_haircut(sd, wd)
    assert wd["exact_ok"] and hd["HOLD90"]["conditional_ok"], hd
    say(f"  K1d small: {hd['HOLD90']['fills_delisted']} fills and {hd['HOLD90']['twins_delisted']} twins closed at "
        f"the delisting value; every position open at the end of trading took it (fills and twins); engine twin "
        f"delistings vs the oracle's {hd['HOLD90']['diff_se']:+.2f} SE ({time.time() - t:.0f}s)")
    # K2 machinery: a strongly reverting market passes, the same market without reversion does not
    t = time.time()
    s2 = replace(specs["K2"], n_coins=10, transient=0.9, jump_rate=12.0)
    w2 = run_k1_world(s2, jobs, exits=("FLIP", "FLIP_bot", "HOLD90"), twins_check=False)
    res = w2["_res"]
    O, F = res["outcomes"], res["fills"]
    ts = {}
    for ex in ("FLIP", "FLIP_bot"):
        d = O[(O.rule == "F1") & (O.exit == ex) & (O.cost == "C-RH") & O.complete.astype(bool)][["fill_id", "delta"]]
        d = d.merge(F[["fill_id", "month_block"]], on="fill_id")
        r = sbs.test_mean(d.delta.to_numpy(float), d.month_block.to_numpy(), B=999)
        ts[ex] = r
        assert r["estimate"] > 0 and r["t"] >= K2_T and w2["compare"]["exits"][ex]["passed"], (ex, r["t"])
    w0 = run_k1_world(replace(s2, transient=0.0), jobs, exits=("FLIP",), twins_check=False)
    d0 = w0["compare"]["exits"]["FLIP"]["engine_delta"]
    assert d0 < ts["FLIP"]["estimate"], (d0, ts["FLIP"]["estimate"])
    say(f"  K2 small: planted 90% reversion -> Delta (C-RH) {ts['FLIP']['estimate']:+.4f} (t {ts['FLIP']['t']:.1f}) "
        f"rule M, {ts['FLIP_bot']['estimate']:+.4f} (t {ts['FLIP_bot']['t']:.1f}) bot, engine = oracle; the same "
        f"market without reversion: Delta {d0:+.4f} ({time.time() - t:.0f}s)")
    return [("synthetic K1b small", w["_res"]["audit"]), ("synthetic K1d small", wd["_res"]["audit"])], \
        [("synthetic K1b small", w["_res"]["bids"])]


def _st_k1c(say, jobs):
    """Review finding 1: what K1c exports as "what regime timing alone produces". K1c and its null K1c0 share regime
    states, crash schedule and shocks and differ only by the deterministic regime drift (every day's increment of
    log K1c - log K1c0 has the regime's sign); the export is the paired K1c - K1c0 Delta, recomputed here; the
    minute-level gap-through cost of K1b's jumps (K1c0's own Delta) is large and absent from it (a null paired
    with itself exports exactly 0 while its Delta is that cost); the engine's paired value agrees with the oracle's."""
    t = time.time()
    specs = k1_specs(n_coins=6, start="2019-11-01", end="2021-12-31")
    c, z = specs["K1c"], specs["K1c0"]
    gc_, g0 = _market_globals(c), _market_globals(z)
    for k in ("ev_t", "ev_m", "state", "eps_m", "v_day"):
        assert np.array_equal(gc_[k], g0[k]), f"K1c and K1c0 differ in {k}"
    A, Z = SynthMarket(c).path("S00"), SynthMarket(z).path("S00")
    assert np.array_equal(A["live"], Z["live"]) and np.array_equal(A["keep"], Z["keep"]) and A["tick"] == Z["tick"]
    d = np.log(A["c"].astype(float)) - np.log(Z["c"].astype(float))
    inc = np.diff(np.r_[0.0, d[DAY_M - 1::DAY_M]])
    assert (np.sign(inc) == gc_["state"][:len(inc)]).all(), "K1c - K1c0 is not the regime drift alone"
    wc = run_k1_world(c, jobs, exits=K1C_EXITS, twins_check=False)
    w0 = run_k1_world(z, jobs, exits=K1C_EXITS, twins_check=False)
    assert wc["exact_ok"] and w0["exact_ok"], "engine and oracle differ fill by fill in K1c / K1c0"
    Tc, T0 = _k1c_table(wc), _k1c_table(w0)
    rep = k1c_report(c, Tc, T0, wc["compare"], w0["compare"])
    key = ["coin", "t0", "rung"]
    for ex in K1C_EXITS:
        m = Tc[_usable(Tc, ex)].merge(T0[_usable(T0, ex)][key + [f"dRH_{ex}"]], on=key, suffixes=("", "_n"))
        assert abs(rep[ex]["engine_delta_RH"] - float((m[f"dRH_{ex}"] - m[f"dRH_{ex}_n"]).mean())) < 1e-12
        assert rep[ex]["n_common"] == len(m) >= 0.8 * min(rep[ex]["n_K1c"], rep[ex]["n_K1c0"]), rep[ex]
        assert abs(rep[ex]["engine_delta_RH"] - rep[ex]["oracle_delta_RH"]) <= 3 * rep[ex]["se_iid"], rep[ex]
        assert np.isfinite(rep[ex]["se"]) and rep[ex]["unit"] == "month-block"
    assert rep["delta90"] == rep["HOLD90"]["engine_delta_RH"]
    ml, rg = rep["minute_level"]["FLIP"]["engine_delta_RH"], rep["FLIP"]["engine_delta_RH"]
    assert ml < -0.02 and abs(rg) < 0.5 * abs(ml), (ml, rg)
    assert rep["gap_through"]["share_open_below_L"] > 0.2 and rep["gap_through"]["mean_close_over_L"] < 0
    nul = k1c_report(z, T0, T0)
    for ex in K1C_EXITS:
        assert nul[ex]["engine_delta_RH"] == 0.0 and nul[ex]["engine_delta"] == 0.0, nul[ex]
        assert nul["total"][ex]["engine_delta_RH"] == nul["minute_level"][ex]["engine_delta_RH"] < 0
    say(f"  K1c small: K1c and K1c0 share regime states, crashes and shocks, and log K1c - log K1c0 moves with the "
        f"regime's sign on all {len(inc)} days; exported regime timing (paired, C-RH): X-FLIP {rg:+.4f}, X-HOLD-90 "
        f"{rep['delta90']:+.4f} (oracle {rep['FLIP']['oracle_delta_RH']:+.4f} / {rep['HOLD90']['oracle_delta_RH']:+.4f})"
        f"; not exported: K1c's total {rep['total']['FLIP']['engine_delta_RH']:+.4f} / "
        f"{rep['total']['HOLD90']['engine_delta_RH']:+.4f}, the minute-level cost {ml:+.4f} (X-FLIP); a null paired "
        f"with itself exports 0 ({time.time() - t:.0f}s)")


def _st_calendars(say):
    """Review finding 2: the real calendars carry a key (the code that builds them, their configuration, the stamps of
    their data inputs) and are rebuilt when it changes or when forced; a crashed build leaves no key; the K3 and K6
    caches are keyed by it; run() and the CLI can force a rebuild. A stub build on a temporary directory: no real
    data are read."""
    global WORK
    import inspect
    import shutil
    import tempfile
    old = WORK
    base_dir = Path(os.environ.get("SB_SELFTEST_DIR", str(ROOT / "data" / "stinkbid" / "controls_selftest")))
    base_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="sb_cal_selftest_", dir=str(base_dir)))
    WORK = tmp / "work"
    WORK.mkdir(parents=True)
    root, src = tmp / "data", tmp / "engine_src.py"
    (root / "m1_spot").mkdir(parents=True)
    (root / "m1_spot" / "AAA.parquet").write_bytes(b"one")
    src.write_text("x = 1\n")
    calls = []

    def build(jobs, log, venues):
        calls.append(venues)
        P = _cal_paths()
        for k in ("p1_bids", "p1_fills", "h4_bids", "h4_fills"):
            pd.DataFrame({"rung": [6.0], "t_F1": [-1]}).to_parquet(P[k])
        return {"stub": len(calls)}

    def boom(jobs, log, venues):
        raise RuntimeError("a crashed calendar build")

    kf = lambda v: calendar_key(v, root=root, sources=[str(src)], inputs=("m1_spot",))
    rc = lambda **kw: real_calendars(1, build=kw.pop("build", build), key_fn=kf, log=lambda m: None, **kw)
    try:
        m1 = rc()
        assert len(calls) == 1 and m1["key"] == kf(True)["key"] and not m1["reused"]
        assert rc()["reused"] and len(calls) == 1                                  # unchanged: reused
        (root / "m1_spot" / "AAA.parquet").write_bytes(b"two!")                     # new data: rebuilt
        m3 = rc()
        assert len(calls) == 2 and m3["key_parts"]["data"] != m1["key_parts"]["data"]
        src.write_text("x = 2  # an engine fix\n")                                  # new engine code: rebuilt
        m4 = rc()
        assert len(calls) == 3 and m4["key_parts"]["code"] != m3["key_parts"]["code"]
        assert rc(force=True)["stub"] == 4 and len(calls) == 4                      # forced
        _cal_paths()["meta"].write_text(json.dumps({"built_by": "an older engine"}))  # an old calendar, no key
        assert not rc()["reused"] and len(calls) == 5
        try:
            rc(build=boom, force=True)
            raise AssertionError("the crashed build did not raise")
        except RuntimeError:
            pass
        assert not _cal_paths()["meta"].exists()                                     # no valid key left behind
        assert not rc()["reused"] and len(calls) == 6
        assert kf(False)["cfg"] != kf(True)["cfg"]
        k_ = calendar_key()                                                          # the real inputs: stamps only
        assert len(k_["key"]) == 16 and k_ == calendar_key()
        assert _k3_cache_key({}, "a") != _k3_cache_key({}, "b") and _k6_cache_key(1, "a") != _k6_cache_key(1, "b")
        assert "rebuild_calendars" in inspect.signature(run).parameters
        assert "--rebuild-calendars" in inspect.getsource(main)
        assert "real_calendars(jobs, force=rebuild_calendars" in inspect.getsource(run)
    finally:
        WORK = old
        shutil.rmtree(tmp, ignore_errors=True)
    say("  real calendars: keyed by their code, configuration and data stamps; reused while unchanged, rebuilt after "
        "a data or engine change, when forced, when built without a key and after a crashed build (which leaves no "
        "key); the K3 and K6 cache keys carry it; run(rebuild_calendars=True) and --rebuild-calendars force it")


def _st_k4(say, jobs):
    """K4 at small size through the run's building blocks: draw_cuts' contract on 50 cuts and the stratified pick of
    the real-fill cuts, then one cut of each kind x (scale, delete, 3-day gap) through _k4_task and k4_compare (the
    run's k4_synthetic drives the same blocks on all 50 cuts); K7(a)'s coverage of every program's levels; two
    planted look-aheads: one that reaches only capacity, and one that decides fills in one world only, caught with
    capacity off (fill minutes) and on."""
    t = time.time()
    spec = replace(k4_spec(), start="2021-06-01", end="2022-06-30")
    progs = (("P1",), ("P1", "P1-90", "P1-lazy", "M3", "M8", "H4"))
    base_m = K4Market(spec)
    base = _k4_world_runs(base_m, *progs)
    F = base[("out", "P1")]["fills"]
    fm = F.t_F1.to_numpy(float)
    ok = np.isfinite(fm) & (fm >= 0)
    lo = _tmin(pd.Timestamp(spec.start) + pd.Timedelta(days=120))
    hi = _tmin(pd.Timestamp(spec.end) - pd.Timedelta(days=30))
    pl = _tmin(pd.date_range(pd.Timestamp(spec.start, tz="UTC") + pd.Timedelta(days=1), pd.Timestamp(spec.end, tz="UTC"),
                             freq="W-MON")) + 210
    cuts = draw_cuts(K4_CUTS, pl, fm[ok].astype(np.int64), lo, hi, np.random.default_rng(SEED + 4),
                     F.coin.to_numpy()[ok], base_m.coins)
    vc = cuts.why.value_counts().to_dict()
    assert len(cuts) == K4_CUTS and all(vc.get(k, 0) >= 10 for k in ("placement", "crash_hour", "weekend")), vc
    tt = cuts.t.to_numpy(np.int64)
    assert (tt % 60 != 0).all() and ((tt >= lo) & (tt < hi)).all()
    pc = cuts[cuts.why == "placement"].t.to_numpy(np.int64)
    prev = pl[np.searchsorted(pl, pc, side="right") - 1]
    assert ((pc - prev > 0) & (pc - prev < DAY_M)).all()                       # within 24 h after a placement
    fh = set(((fm[ok].astype(np.int64)) // 60).tolist())
    assert all(int(x) // 60 in fh for x in cuts[cuts.why == "crash_hour"].t)      # inside the hour of a fill
    assert cuts[cuts.why == "weekend"].weekend.all()
    pick = cuts.groupby("why", sort=True).head(1)
    tasks = [(spec, int(r.t), mode, r.coin, progs) for r in pick.itertuples() for mode in ("scale", "delete", "gap")]
    res = _pmap(_k4_task, tasks, jobs)
    n, tot, bites = 0, {}, {}
    for r in res:
        for key, pr in r["runs"].items():
            c = k4_compare(_k4_trim({key: base[key]}, r["cut"])[key], pr, r["cut"], r["mode"])
            assert c["ok"], (r["cut"], r["mode"], key, c["diffs"], c["examples"][:2])
            n += 1
            for k, v in c["compared"].items():
                tot[k] = tot.get(k, 0) + v
        ba = _after_print(base, r["cut"])
        bites[r["mode"]] = bites.get(r["mode"], 0) + int(any(ba[k] != v for k, v in r["after"].items() if k in ba))
    assert set(bites) == {"scale", "delete", "gap"} and all(v > 0 for v in bites.values()), bites   # as in the run
    say(f"  K4 small: draw_cuts' {len(cuts)} cuts ({vc}; none on the hour, placement cuts within 24 h after one, "
        f"crash-hour cuts in a fill's hour); {len(pick)} cuts (one of each kind) x scale / delete / 3-day gap = "
        f"{len(tasks)} perturbed worlds, {n} run comparisons clean (compared {tot}); worlds where a later decision "
        f"changes {bites} ({time.time() - t:.0f}s)")
    # review finding 7: the real-data fill runs take their cuts stratified by kind, not the first n of a frame that
    # draw_cuts orders by kind
    pk = _pick_cuts(cuts, 24).why.value_counts().to_dict()
    assert pk == {k: 6 for k in ("placement", "crash_hour", "weekend", "uniform")}, pk
    assert cuts.head(24).why.nunique() == 2                                   # what head(24) gave
    assert _pick_cuts(cuts, 2).why.nunique() == 2 and len(_pick_cuts(cuts, 99)) == len(cuts)
    assert "_pick_cuts(cuts, n)" in __import__("inspect").getsource(k4_real_fills)
    say(f"  K4 real-fill cuts: 24 of the 50 stratified by kind {pk} (head(24) held only placement and crash-hour "
        f"cuts)")
    # review finding 5: K7(a) checks the levels of every program, here those of the K4 world (P1 and k = 5 / 12, M1,
    # M2a, M3, M8, the four H4 methods and H4-all's other chart methods, with placebos)
    t = time.time()
    extra = _k4_world_runs(base_m, (), ("M1", "M2a", "P1-k5-12", "H4-all"))
    lv = k7_levels(_k4_bid_tables({**base, **extra}))
    assert lv["ok"] and lv["off_tick"] == 0 and not lv["coverage"]["missing"], lv["coverage"]
    part = k7_levels(_k4_bid_tables(base))                                   # without M1, M2a, M4f, ... : fails
    assert not part["ok"] and {"M1", "M2a", "M4f", "M4s", "M5f", "M5a"} <= set(part["coverage"]["missing"]), part
    say(f"  K7(a) coverage: {lv['levels']} synthetic levels of {len(lv['sources'])} programs on their tick, every "
        f"method of the engine's programs checked ({', '.join(lv['coverage']['synthetic'])}); a source set without "
        f"M1, M2a and H4-all's other chart methods fails K7 ({time.time() - t:.0f}s)")
    # planted look-ahead 1: the low of the hour before the cut pulled to half the next day's mean close in BOTH worlds
    # (x 0.5 vs x 0.75 the base mean): every bid fills in the same minute, so only C1 capacity sees it
    t = time.time()
    r = _k4_keyed(_k4_run(base_m.world(), "P1", outcomes=False))
    F = r["fills"]
    cut = int(F.t_F1[F.t_F1 >= 0].iloc[len(F) // 2]) + 7                # just after a fill, off the hour
    if cut % 60 == 0:
        cut += 1
    caught = 0
    for leak in (False, True):
        b = _k4_keyed(_k4_run(K4Market(spec, Pert("none", cut, "", leak)).world(), "P1", outcomes=False))
        p = _k4_keyed(_k4_run(K4Market(spec, Pert("scale", cut, "", leak)).world(), "P1", outcomes=False))
        c = k4_compare(_k4_trim({0: b}, cut)[0], _k4_trim({0: p}, cut)[0], cut, "scale")
        if leak:
            assert not c["ok"], "K4 missed a planted look-ahead"
            caught = dict(c["diffs"])
        else:
            assert c["ok"], c["diffs"]
    say(f"  K4 planted leak 1 (the low of the hour before the cut pulled to half the next day's mean close in both "
        f"worlds; capacity alone sees it): caught (differences by kind, counted per bid: {caught}); the same cut "
        f"without the leak is clean ({time.time() - t:.0f}s)")
    # planted look-ahead 2 (review finding 6): a leak that decides fills, in one world only; K4 must catch it with
    # capacity off (fill minutes) as well as on
    t = time.time()
    mid = pd.Timestamp(spec.start) + (pd.Timestamp(spec.end) - pd.Timestamp(spec.start)) / 2
    mon = mid.normalize() - pd.Timedelta(days=mid.weekday()) + pd.Timedelta(hours=PLACE_HM[0], minutes=PLACE_HM[1])
    cut2 = _tmin(mon) + 2 * DAY_M + 7 * 60 + 17                    # Wednesday 10:47 UTC, P1's Monday bids still live
    thr = {}
    for coin in base_m.coins:
        k = K4Market(spec).raw(coin)["m1"]
        tm = _tmin(k.open_time)
        thr[coin] = 1.25 * float(k.close.to_numpy(float)[(tm >= cut2) & (tm < cut2 + DAY_M)].mean())

    def leak_run(mode, capacity, leak=True):
        mk = _DecisionLeakMarket(spec, Pert(mode, cut2, ""), thr) if leak else K4Market(spec, Pert(mode, cut2, ""))
        res = sbe.run_program("P1", "U_Q1", data=mk.world(), cfg=dict(
            rules=sbe.RULES_ALL, counts_only=True, capacity=capacity, verbose=False, audit="report", usd=False,
            mw=False, twin_sens=False, drift=False, keep_twins=False, n_jobs=1))
        res["program"] = "P1"
        return _k4_trim({0: _k4_keyed(res)}, cut2)[0]
    bl = leak_run("none", "none")
    fl = bl["fills"].t_F1.to_numpy(float) if len(bl["fills"]) else np.zeros(0)
    n_leak = int(((fl >= cut2 - 60) & (fl < cut2)).sum())
    assert n_leak > 0, "the planted leak fills no bid before the cut (no live bid at the cut)"
    caught2 = {}
    for cap in ("none", "c1"):
        c = k4_compare(bl if cap == "none" else leak_run("none", cap), leak_run("scale", cap), cut2, "scale")
        assert not c["ok"] and any(k_.startswith("fill_") for k_ in c["diffs"]), (cap, c["diffs"])
        if cap == "c1":
            assert "capacity" in c["diffs"], c["diffs"]
        caught2[cap] = dict(c["diffs"])
    clean = k4_compare(leak_run("none", "none", leak=False), leak_run("scale", "none", leak=False), cut2, "scale")
    assert clean["ok"], clean["diffs"]
    say(f"  K4 planted leak 2 (the hour before the cut pulled below every live bid only when the next day's mean close "
        f"is low, i.e. in the base world: {n_leak} fills there): caught with capacity off {caught2['none']} and on "
        f"{caught2['c1']}; the same cut without the leak is clean ({time.time() - t:.0f}s)")
    return [("synthetic K4 small", r.get("audit"))], [("synthetic K4", r["bids"])]


def _st_k3_k5_k6_k7_k8(say, jobs, records, bids):
    global WORK
    t = time.time()
    old_work = WORK
    # the selftest's calendars, K3 cache and K8 table go to a temporary directory under data/stinkbid/ (gitignored;
    # SB_SELFTEST_DIR overrides it), removed at the end; the study's working data and outputs are never touched
    tmp = Path(os.environ.get("SB_SELFTEST_DIR", str(ROOT / "data" / "stinkbid" / "controls_selftest"))) / \
        f"sb_controls_selftest_{os.getpid()}"
    WORK = tmp
    WORK.mkdir(parents=True, exist_ok=True)
    try:
        spec = replace(k4_spec(), start="2020-09-01", end="2022-12-31")
        W = K4Market(spec).world()
        P = _cal_paths()
        r1 = sbe.run_program("P1", "U_Q1", data=W, cfg=dict(rules=("F1", "F2", "F3_1", "F3_3", "F3d_1", "F5"),
                                                             counts_only=True, capacity="c1", verbose=False,
                                                             audit="report", mw=False, usd=False))
        r4 = sbe.run_program("H4", "U_Q1", data=W, cfg=dict(rules=("F1",), counts_only=True, capacity="none",
                                                             verbose=False, audit="report", mw=False))
        for res, kb, kf in ((r1, "p1_bids", "p1_fills"), (r4, "h4_bids", "h4_fills")):
            res["bids"].to_parquet(P[kb])
            F = res["fills"].copy()
            for c in F.columns:
                if F[c].dtype == object:
                    F[c] = F[c].astype(str)
            F.to_parquet(P[kf])
        P["meta"].write_text("{}")
        # K3 on the synthetic calendar
        summ, calib, power, d11 = run_k3(24, jobs, n_power=6, B=199, log=lambda m: None, universe=W["universe"])
        assert set(calib["tests"]) == {"H1", "H2R", "H4"}, calib["tests"].keys()
        for tt, d in calib["tests"].items():
            for s_, v in d["by_scenario"].items():
                assert v["n"] == 24 and all(np.isfinite(x["rate"]) for x in v["false_pass"].values()), (tt, s_)
        assert len(d11) == 3 * 24 and np.isfinite(d11.total).all()
        pw = power["power"]["H1"]["base"]
        big = [x for x in pw if x["kind"] == "const" and x["effect"] == 0.08][0]
        nul = [x for x in pw if x["kind"] == "const" and x["effect"] == 0.0][0]
        assert big["reject_05"] >= nul["reject_05"], (big, nul)
        pc = sbs.calibrated_p("H1", 10.0, calib)
        assert 0 < pc < 0.1, pc
        say(f"  K3 small: 24 null replications x 3 scenarios on a synthetic calendar ({len(_k3_load()['p1']['coin'])} "
            f"P1 fills, {len(_k3_load()['p4']['coin'])} H4 stacked fills), B = 199: rates, bounds, calibrated p, "
            f"power (H1 +8%: {big['reject_05']:.0%} vs null {nul['reject_05']:.0%} at 5%), D11 null "
            f"({time.time() - t:.0f}s)")
        # review finding 4: a test K3 switches to the simulation-calibrated rule is powered under that rule
        t = time.time()
        cal2 = json.loads(json.dumps(_js(calib)))                           # (24 nulls: K3 fails every test)
        for t_, cal_ in (("H1", True), ("H2R", False), ("H4", True)):
            cal2["tests"][t_].update(needs_calibration=cal_, k3_pass=not cal_,
                                     rule="simulation-calibrated" if cal_ else "nominal")
        pw2 = k3_power(cal2, jobs, B=199)
        assert pw2["rule"] == {"H1": "simulation-calibrated", "H2R": "nominal", "H4": "simulation-calibrated"}, \
            pw2["rule"]
        for x in (r_ for rows in pw2["power"]["H4"].values() for r_ in rows):     # H4 under the calibrated rule
            assert x["rule"] == "simulation-calibrated" and x["reject_alpha3"] == 0.0, x
            assert x["noedge"] <= x["noedge_nominal"], x                         # the bound is widened, never narrowed
        S_ = _k3_load()
        fb = sorted(Path(os.environ["SB_K3_CACHE"]).glob("base_*.npz"))
        tt = np.array([sbs.test_mean(np.load(f)["d1"] + 0.08, S_["p1"]["mb"], B=9, seed=1)["t"] for f in fb])
        row = [x for x in pw2["power"]["H1"]["base"] if x["kind"] == "const" and x["effect"] == 0.08][0]
        for lv_, key_ in ((sbs.ALPHA / 3, "reject_alpha3"), (sbs.ALPHA, "reject_05")):
            want = float(np.mean([sbs.calibrated_p("H1", x, cal2) < lv_ for x in tt]))
            assert row["rule"] == "simulation-calibrated" and abs(row[key_] - want) < 1e-12, (key_, row, want)
        assert row["reject_alpha3"] == 0.0 < row["reject_alpha3_nominal"], row   # 24 nulls: p >= 1/25 > 0.05/3
        c05 = _calib_crit("H1", cal2, sbs.ALPHA)
        assert sbs.calibrated_p("H1", c05, cal2) >= sbs.ALPHA > sbs.calibrated_p("H1", c05 + 1e-9, cal2), c05
        assert np.isinf(_calib_crit("H1", cal2, sbs.ALPHA_B))                # unreachable at 0.05/3 with 24 nulls
        assert pw2["mde"]["H1"]["base"]["rule"] == "simulation-calibrated" and \
            pw2["mde"]["H2R"]["base"]["mde_rule"] == pw2["mde"]["H2R"]["base"]["mde_formula"]
        assert all(x["rule"] == "nominal" and "reject_alpha3_nominal" not in x for x in pw2["power"]["H2R"]["base"])
        say(f"  K3 power under the calibrated rule: H1 and H4 set to the simulation-calibrated p, H2R nominal: H1 +8% "
            f"rejected {row['reject_alpha3']:.0%} at 0.05/3 (calibrated; nominal {row['reject_alpha3_nominal']:.0%}) "
            f"and {row['reject_05']:.0%} at 0.05 (= the calibrated p recomputed on the cached nulls); critical t at "
            f"0.05 {c05:.2f}; H4's rows calibrated with widened bounds; H2R's nominal ({time.time() - t:.0f}s)")
        # K5: the engine's audits clean; a planted violation fails
        t = time.time()
        k5 = k5_audit(records + [("synthetic calendar", r1["audit"])], jobs, real_reaudit=False)
        assert k5["passed"] and k5["checks"] > 0, k5
        bad = pd.DataFrame([dict(type="violation", label="planted", coin="X", what="fill above the limit")])
        assert not k5_audit([("planted", bad)], jobs, real_reaudit=False)["passed"]
        say(f"  K5: {k5['checks']} engine checks clean, {k5['gaps']} gap-through fills listed; a planted violation "
            f"fails K5")
        # K6: aggTrades injected as the same seller flow C1 uses -> ratio 1 through the engine's capacity windows
        Wc = dict(W)

        def agg(coin, day, windows):
            k = K4Market(spec).raw(coin)["m1"]
            tm = _tmin(k.open_time)
            rows = []
            for w_ in pd.DataFrame(windows).itertuples():
                a, b = _tmin(w_.start), _tmin(w_.end)
                d0 = _tmin(pd.Timestamp(day, tz="UTC"))
                a, b = max(a, d0), min(b, d0 + DAY_M)
                sel = (tm >= a) & (tm < b) & (k.trades.to_numpy() > 0)
                hi_, lo_ = k.high.to_numpy()[sel], k.low.to_numpy()[sel]
                rg = hi_ - lo_
                f_ = np.where(rg > 0, np.clip((w_.L - lo_) / np.where(rg > 0, rg, 1), 0, 1), (lo_ < w_.L) * 1.0)
                sq = k.quote_volume.to_numpy()[sel] - k.taker_buy_quote.to_numpy()[sel]
                for m_, v_ in zip(tm[sel], sq * f_):
                    if v_ > 0:
                        rows.append(dict(wid=w_.wid, L=w_.L, start=w_.start, end=w_.end,
                                         minute=pd.Timestamp(int(m_) * MIN_NS, tz="UTC"), sell_below_usd=v_,
                                         sell_below_qty=0.0, n_trades=1))
            out = pd.DataFrame(rows, columns=["wid", "L", "start", "end", "minute", "sell_below_usd", "sell_below_qty",
                                              "n_trades"])
            out.attrs["missing"] = False
            return out
        Wc["agg"] = agg
        world = sbe.World(Wc)
        F = r1["fills"]
        F = F[F.t_F1 >= 0].head(6)
        ratios = []
        for coin, g in F.groupby("coin"):
            spot, _, _ = sbe.build_spot(world, coin)
            i_f = np.searchsorted(spot.t, g.t_F1.to_numpy(np.int64))
            cap = sbe.capacity(world, coin, g.reset_index(drop=True), spot, i_f.astype(np.int64), mode="agg")
            ratios += list((cap.c1_life / cap.agg_life).to_numpy(float))
        ratios = np.asarray(ratios)
        assert len(ratios) and np.allclose(ratios[np.isfinite(ratios)], 1.0, rtol=1e-6), ratios
        say(f"  K6: aggTrades injected as the same seller flow -> C1 / aggTrades = 1 on {len(ratios)} fills through "
            f"the engine's capacity windows ({time.time() - t:.0f}s)")
        # K7: synthetic levels on their tick; a planted off-tick level and the Robinhood order rule
        b = bids[0][1]
        bb = b[["L", "L_tau", "n_ticks", "tick_str"]].copy()
        bb.loc[bb.index[0], "L"] = bb.L.iloc[0] * (1 + 1e-9)
        cat = pd.DataFrame([dict(coin="ZZ", price_tick_str="0.01", qty_increment_str="0.001", min_order_size_str="0.01",
                                 max_order_size_str="5")])
        orders = rh_orders("ZZ", 2.37, 100.0, cat.iloc[0])
        q_ = [Decimal(o["qty"]) for o in orders]                             # 42.194 -> 2 x 4.689 + 7 x 4.688
        assert len(orders) == 9 and max(q_) <= 5 and max(q_) - min(q_) <= Decimal("0.001"), orders
        assert sum(q_) == Decimal("42.194")
        bad = pd.DataFrame([dict(coin="ZZ", limit=2.375, qty="1.0005")])
        chk = k7_check_orders(bad, cat)
        assert chk["n_violations"] == 2, chk
        good = k7_check_orders(pd.DataFrame(orders), cat)
        assert good["n_violations"] == 0, good
        # review finding 3: min 1, max 5, increment 0.1, $10.50 at 1.00 -> 10.5 units: the greedy split gave 5, 5 and
        # 0.5 (below the minimum); the even split gives 3 x 3.5, and K7(b) orders by the sheet's own rule
        cat2 = pd.DataFrame([dict(coin="ZZ", price_tick_str="0.01", qty_increment_str="0.1", min_order_size_str="1",
                                  max_order_size_str="5")])
        o2 = rh_orders("ZZ", 1.00, 10.5, cat2.iloc[0])
        assert [o["qty"] for o in o2] == ["3.5", "3.5", "3.5"] and k7_check_orders(pd.DataFrame(o2), cat2)[
            "n_violations"] == 0, o2
        from analysis_2026 import stinkbid_sheet as sbsh
        so = k7_sheet_orders(pd.DataFrame([dict(coin="ZZ", rung=8.0, L=1.00), dict(coin="ZZ", rung=6.0, L=2.37)]),
                             cat2, Qs=(10.5, 100.0, 0.5))
        want = [str(q) for L_, Q_ in ((1.00, 10.5), (1.00, 100.0), (1.00, 0.5), (2.37, 10.5), (2.37, 100.0),
                                      (2.37, 0.5)) for q in sbsh.rh_orders(Decimal(repr(L_)), Q_, cat2.iloc[0])[0]]
        got = so["orders"].sort_values(["limit", "Q"], kind="stable").qty.tolist()
        assert sorted(got) == sorted(want) and len(got) == len(want) and not so["errors"] and \
            not so["rule_mismatch"], (got, want, so)
        assert k7_check_orders(so["orders"], cat2)["n_violations"] == 0
        cat3 = cat2.assign(min_order_size_str="3")                          # max < 2 min: 5.2 cannot be split
        so3 = k7_sheet_orders(pd.DataFrame([dict(coin="ZZ", rung=8.0, L=1.00)]), cat3, Qs=(5.2,))
        assert len(so3["errors"]) == 1 and so3["orders"].empty, so3
        try:
            rh_orders("ZZ", 1.00, 5.2, cat3.iloc[0])
            raise AssertionError("rh_orders split 5.2 into pieces below the minimum of 3")
        except ValueError:
            pass
        off = 0
        for x, xt, k_, ts in zip(bb.L, bb.L_tau, bb.n_ticks, bb.tick_str):
            if float(Decimal(int(k_)) * Decimal(ts)) != x:
                off += 1
        assert off == 1
        assert k7_levels([("synthetic planted", bb)])["off_tick"] == 1
        say("  K7: synthetic levels on their tick, a planted off-tick level flagged; Robinhood orders: $100 at 2.37 -> "
            "42.194 floored to the 0.001 increment and split evenly into 9 orders under a max of 5 (2 x 4.689 + "
            "7 x 4.688); $10.50 at 1.00 under min 1 / max 5 -> 3 x 3.5 (the greedy split's 5, 5, 0.5 broke the "
            "minimum); K7(b)'s orders are the sheet's own rule (stinkbid_sheet.rh_orders) and match this module's "
            "coding; a rung no split can order (max < 2 min) is an error; an off-tick price and an off-increment "
            "quantity flagged")
        # K8: the venue table on the synthetic calendar
        globals()["OUT_DIR"] = tmp
        k8 = k8_venue()
        assert k8["passed"] and k8["fills"] > 0
        say(f"  K8: venue table on {k8['fills']} synthetic fills (removed by F3 1% {k8['removed_share']['F3_1']:.1%}, "
            f"3% {k8['removed_share']['F3_3']:.1%}, dwell {k8['removed_share']['F3d_1']:.1%})")
    finally:
        WORK = old_work
        os.environ.pop("SB_K3_CACHE", None)
        os.environ.pop("SB_K3_SETUP", None)
        _K3.clear()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def selftest(jobs: int = 4) -> None:
    """Every control at small sizes on synthetic data, with known answers and planted failures: rule M; the oracle
    on hand-built minutes; K1b (engine = oracle fill by fill; the fill-at-close and fill-at-low engines fail), K1d
    (haircuts at equal rates), K2 (a planted reverting effect passes; none without reversion); K1c (the paired
    regime component against K1c0, without the minute-level gap-through cost); the real calendars' key (stub build);
    K4 / K4b (draw_cuts' contract on 50 cuts and the stratified real-fill cuts; one cut of each kind x scale /
    delete / 3-day gap clean on 7 programs; K7(a)'s coverage of every program's levels; a planted look-ahead that
    reaches only capacity and one that decides fills in one world, caught with capacity off and on); K3
    (calibration, power under the calibrated rule, D11 on a synthetic calendar); K5 (audits; a planted violation
    fails); K6 (C1 = injected aggTrades); K7 (ticks, Robinhood orders by the sheet's rule); K8 (venue table)."""
    global OUT_DIR
    T = time.time()
    old_out = OUT_DIR
    say = _say
    say("stinkbid_controls selftest")
    try:
        _st_rule_m(say)
        _st_oracle_hand(say)
        rec, bids = _st_k1_k2(say, jobs)
        _st_k1c(say, jobs)
        _st_calendars(say)
        r4, b4 = _st_k4(say, jobs)
        _st_k3_k5_k6_k7_k8(say, jobs, rec + r4, bids + b4)
    finally:
        OUT_DIR = old_out
    say(f"selftest passed ({time.time() - T:.0f}s)")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="stinkbid_controls")
    ap.add_argument("cmd", choices=("run", "selftest", "status"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", default="")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--reps", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--rebuild-calendars", action="store_true",
                    help="rebuild the real fill calendars even when their key (code, configuration, data) is unchanged")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest(a.jobs)
        return 0
    if a.cmd == "status":
        f = (Path(a.out) if a.out else OUT_DIR) / "summary.json"
        if not f.exists():
            print(f"{f} not found")
            return 1
        S = json.loads(f.read_text())
        print(f"all_passed: {S.get('all_passed')}")
        for k in CONTROLS:
            if isinstance(S.get(k), dict):
                print(f"  {k}: {'passed' if S[k].get('passed') else 'FAILED'}")
        return 0
    only = tuple(x.strip().upper() for x in a.only.split(",") if x.strip()) or None
    S = run(out=a.out or None, jobs=a.jobs, quick=a.quick, only=only, n_reps=a.reps or None,
            rebuild_calendars=a.rebuild_calendars)
    return 0 if S.get("all_passed") else 2


if __name__ == "__main__":
    sys.exit(main())
