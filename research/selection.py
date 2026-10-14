"""Causal stock formation scores; no eligibility decision reads a test-window bar.

Timing skill is a selection hypothesis, not an estimator of tax-adjusted portfolio
alpha. Its conditional permutation test therefore has that narrower interpretation.
The exact fixed Moneyline indicator remains in analysis_2026.moneyline_ref.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from analysis_2026.moneyline_ref import moneyline
from research.config import ExperimentConfig, Window
from screener.data import quality_filter


@dataclass
class FormationResult:
    window: Window
    metrics: pd.DataFrame
    excluded: dict[str, str]
    flags: tuple[str, ...]


def daily_returns(df: pd.DataFrame, cost: float = 0.0003,
                  dividends: pd.Series | None = None) -> pd.DataFrame:
    """Price + explicit-dividend returns, with close signal -> next-open fills.

    A position held before an ex-date gets that day's distribution even when sold
    at the open. A position first bought at the ex-date open does not. Cash earns
    zero in this diagnostic score, avoiding retrospective annual yield tables.
    Actual cash accrual and portfolio taxes belong to the continuous engine.
    """
    if df.empty:
        return pd.DataFrame(columns=["strat", "bh", "held"], index=df.index)
    o, c = df.open.to_numpy(float), df.close.to_numpy(float)
    g = moneyline(df).green.to_numpy(bool)
    h = np.r_[False, g[:-1]]
    hp = np.r_[False, h[:-1]]
    previous_close = np.r_[np.nan, c[:-1]]
    div = np.zeros(len(df)) if dividends is None else dividends.reindex(df.index).fillna(0).to_numpy(float)
    cc = np.ones(len(df))
    cc[1:] = (c[1:] + div[1:]) / c[:-1]
    returns = np.zeros(len(df))
    hold, entry, exit_ = h & hp, h & ~hp, ~h & hp
    returns[hold] = cc[hold] - 1
    returns[entry] = (1 - cost) * c[entry] / o[entry] - 1
    returns[exit_] = ((1 - cost) * o[exit_] + div[exit_]) / previous_close[exit_] - 1
    return pd.DataFrame({"strat": returns, "bh": cc - 1, "held": h}, index=df.index)


def window_metrics(series: pd.DataFrame, start, end, test: bool = False,
                   calendar: pd.DatetimeIndex | None = None) -> dict | None:
    """Diagnostic scores over the declared horizon, including cash padding in tests.

    Test padding is explicit exploratory bookkeeping, never eligibility. Missing
    terminal proceeds require separate engine/data flags and block deployment.
    Formation scoring never pads missing price history to satisfy coverage.
    """
    w = series.loc[start:end]
    if w.empty:
        if not test:
            return None
        index = calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))] if calendar is not None else pd.bdate_range(start, end)
        w = pd.DataFrame({"strat": 0.0, "bh": 0.0, "held": False}, index=index)
    elif test:
        index = calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))] if calendar is not None else pd.bdate_range(start, end)
        w = w.reindex(index).fillna({"strat": 0.0, "bh": 0.0, "held": False})
    if w.empty:
        return None
    years = max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 1 / 365.25)
    r, b, held = w.strat.to_numpy(float), w.bh.to_numpy(float), w.held.to_numpy(bool)
    if np.any(r <= -1) or np.any(b <= -1):
        return None  # undefined log skill is not a sortable, finite positive score
    eq, bh = np.cumprod(1 + r), np.cumprod(1 + b)
    sc, bc = (eq[-1] ** (1 / years) - 1) * 100, (bh[-1] ** (1 / years) - 1) * 100
    log_s, log_b = float(np.log1p(r).sum()), float(np.log1p(b).sum())
    exposure = float(held.mean())
    trades, cur = [], None
    for j in range(len(w)):
        if held[j]:
            cur = (1.0 if cur is None else cur) * (1 + r[j])
        elif cur is not None:
            cur *= 1 + r[j]
            trades.append(cur - 1)
            cur = None
    t = np.asarray(trades)
    wins, losses = t[t > 0].sum(), abs(t[t <= 0].sum())
    log_r = np.log1p(b)
    long_r = pd.Series(log_r).rolling(20).sum().dropna().to_numpy()[::20]
    vr = np.var(long_r) / (20 * np.var(log_r)) if np.var(log_r) > 0 and len(long_r) > 5 else np.nan
    without_best = ((eq[-1] / (1 + t.max())) ** (1 / years) - 1) * 100 - bc if len(t) else np.nan
    return {"skill": (log_s - exposure * log_b) / years * 100,
            "edge": sc - bc, "sig_cagr": sc, "bh_cagr": bc, "exposure": exposure,
            "pf": wins / losses if losses > 0 else np.nan, "trades": len(t),
            "sig_dd": max_drawdown(eq), "bh_dd": max_drawdown(bh),
            "vol": float(np.std(b) * np.sqrt(252) * 100), "vr20": vr,
            "edge_ex_best": without_best}


def max_drawdown(path) -> float:
    p = np.r_[1.0, np.asarray(path, float)]
    return float(np.min(p / np.maximum.accumulate(p)) - 1) * 100


def _membership_frame(members) -> pd.DataFrame | None:
    if members is None:
        return None
    if isinstance(members, pd.DataFrame):
        frame = members.copy()
    else:
        frame = pd.DataFrame([asdict(x) if is_dataclass(x) else dict(x) for x in members])
    if frame.empty:
        return frame
    if "security_id" not in frame and "symbol" in frame:
        frame = frame.rename(columns={"symbol": "security_id"})
    for col in ("start", "end", "known_at", "end_known_at"):
        if col in frame:
            frame[col] = pd.to_datetime(frame[col])
    return frame


def active_ids(members, asof) -> set[str] | None:
    """Only membership facts observable by formation close are used.

    An eventual removal is ignored until its end_known_at date. For legacy spells
    with no knowledge timestamps, dates are treated as effective contemporaneously
    and the dataset is exploratory. This assumption never grants validated status.
    """
    frame = _membership_frame(members)
    if frame is None:
        return None
    if frame.empty:
        return set()
    date = pd.Timestamp(asof)
    start_known = frame.start <= date
    if "known_at" in frame:
        start_known &= frame.known_at.isna() | (frame.known_at <= date)
    removed = frame.end.notna() & (frame.end < date)
    if "end_known_at" in frame:
        removed &= frame.end_known_at.isna() | (frame.end_known_at <= date)
    return set(frame.loc[start_known & ~removed, "security_id"].astype(str))


def formation_scores(data: Mapping[str, pd.DataFrame], members, window: Window,
                     config: ExperimentConfig, *, calendar: pd.DatetimeIndex | None = None,
                     dividends: Mapping[str, pd.Series] | None = None,
                     symbols: Mapping[str, str] | None = None,
                     price_basis: str = "split_only") -> FormationResult:
    """Evaluate *only* prefixes ending at formation_end, never future survival.

    Indicator warmup, quality screening, membership, stale checks, trade counts,
    and rank tie breaks are therefore unchanged by adding/removing future bars.
    """
    config.validate()
    end = pd.Timestamp(window.formation_end)
    start = pd.Timestamp(window.formation_start)
    expected = None if calendar is None else calendar[(calendar >= start) & (calendar <= end)]
    latest_expected = end if expected is None or expected.empty else expected[-1]
    allowed = active_ids(members, end)
    flags = []
    if members is None:
        flags.append("No point-in-time membership; the stock pool is exploratory")
    if price_basis != "split_only":
        flags.append("Dividend-adjusted/unknown signal prices; exact split-only strategy is unvalidated")
    excluded, rows = {}, []
    for security_id in sorted(data):
        symbol = (symbols or {}).get(security_id, security_id)
        if symbol in config.excluded_symbols:
            excluded[security_id] = "benchmark or excluded ETF"
            continue
        if allowed is not None and security_id not in allowed:
            excluded[security_id] = "not an observed member at formation end"
            continue
        prefix = data[security_id].loc[:end]
        formation = prefix.loc[start:end]
        if len(formation) < config.min_formation_bars:
            excluded[security_id] = "insufficient formation bars"
            continue
        span = (end - start).days
        if (formation.index[-1] - formation.index[0]).days < config.min_formation_coverage * span:
            excluded[security_id] = "insufficient formation history span"
            continue
        if expected is not None and len(formation.index.intersection(expected)) < config.min_formation_coverage * len(expected):
            excluded[security_id] = "insufficient formation session coverage"
            continue
        # Timestamp arithmetic is deliberately based on the already-past calendar.
        if expected is not None and len(expected):
            tolerated = expected[max(0, len(expected) - 1 - config.stale_formation_sessions)]
        else:
            tolerated = latest_expected - pd.Timedelta(days=7)
        if formation.index[-1] < tolerated:
            excluded[security_id] = "stale at formation end"
            continue
        keep, bad = quality_filter({security_id: prefix})
        if security_id not in keep:
            excluded[security_id] = "formation-only quality: " + bad[security_id]
            continue
        before = int((prefix.index < formation.index[0]).sum())
        if before < config.warmup_bars:
            excluded[security_id] = "insufficient pre-formation indicator warmup"
            continue
        series = daily_returns(prefix, config.cost_bps_per_side / 10000,
                               (dividends or {}).get(security_id))
        m = window_metrics(series, start, end)
        if m is None or m["trades"] < config.min_closed_trades:
            excluded[security_id] = "insufficient closed formation trades"
            continue
        rows.append({"security_id": security_id, "symbol": symbol, **m})
    metrics = pd.DataFrame(rows)
    if metrics.empty:
        metrics = pd.DataFrame(columns=["symbol", "skill", "edge", "vol", "pf", "edge_ex_best", "trades"])
        metrics.index.name = "security_id"
    else:
        metrics = metrics.set_index("security_id")
    return FormationResult(window, metrics, excluded, tuple(flags))


def scores_for(metrics: pd.DataFrame, criterion: str, seed: int = 0) -> pd.Series:
    if metrics.empty:
        return pd.Series(dtype=float)
    if criterion in ("skill", "edge", "vol", "pf", "vr20"):
        return metrics[criterion].astype(float)
    if criterion == "gate":
        pass_gate = (metrics.edge > 0) & (metrics.pf >= 2) & (metrics.edge_ex_best > 0)
        return metrics.skill.where(pass_gate, -np.inf)
    if criterion == "bh_dd":
        return -metrics.bh_dd
    if criterion == "random":
        rng = np.random.default_rng(seed)
        return pd.Series(rng.random(len(metrics)), index=metrics.index)
    raise ValueError(criterion)


def pick(scores: pd.Series, level: str) -> list[str]:
    # Stable symbol/ID tie breaking prevents dict insertion order from choosing names.
    finite = scores[np.isfinite(scores)].sort_index().sort_values(ascending=False, kind="stable")
    if level == "all":
        return sorted(scores.index.tolist())
    if level.startswith("top") and level.endswith("%"):
        size = max(1, int(round(float(level[3:-1]) / 100 * len(scores))))
        return finite.index[:size].tolist()
    if level.startswith("top"):
        return finite.index[:int(level[3:])].tolist()
    if level.startswith(">"):
        return finite.index[finite > float(level[1:])].tolist()
    raise ValueError(level)


def holm_adjust(pvalues: Mapping) -> dict:
    """Holm family-wise correction over every tried formula/strictness choice."""
    ordered = sorted(pvalues, key=lambda key: (pvalues[key], str(key)))
    answer, running = {}, 0.0
    for j, key in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - j) * float(pvalues[key])))
        answer[key] = running
    return answer


def permutation_selection_test(formations: Sequence[FormationResult], outcomes: Sequence[pd.Series],
                               config: ExperimentConfig) -> dict[tuple[str, str], dict]:
    """Conditional timing-skill persistence, corrected across the entire search.

    The same global random priority for each immutable ID is used in every window,
    inducing correlated within-window score permutations for repeated securities.
    Every declared window remains in the statistic. Empty baskets have zero
    diagnostic skill, rather than disappearing. This tests exchangeability under
    the null, not the claim that the continuous portfolio beats SPY after taxes.
    """
    if len(formations) != len(outcomes):
        raise ValueError("Every formation window needs an outcome series")
    family = [(c, l) for c in config.criteria for l in config.levels if l != "all"]
    universe = sorted(set().union(*(set(f.metrics.index) for f in formations)))
    if not family or not universe or config.permutations == 0:
        return {}
    missing_outcomes = sum(int(outcome.reindex(f.metrics.index).isna().sum())
                           for f, outcome in zip(formations, outcomes))
    if missing_outcomes:
        # Changing eligibility to keep only future survivors would leak. Ignoring
        # a selected security's unknown payoff would create a different basket.
        # Keep the experiment and disclose unidentified inference instead.
        return {key: {"p_raw": np.nan, "p_holm": np.nan, "statistic": np.nan,
                      "target": config.permutation_target, "family_size": len(family),
                      "missing_outcomes": missing_outcomes,
                      "status": "UNIDENTIFIED_OUTCOMES_NO_PERMUTATION_CLAIM"} for key in family}
    score_tables = [{c: scores_for(f.metrics, c, config.random_seed + i) for c in config.criteria}
                    for i, f in enumerate(formations)]

    def statistic(priority=None):
        values = {key: [] for key in family}
        for scores, outcome in zip(score_tables, outcomes):
            # Outcomes never determine the candidate pool. Only an actually empty
            # universe gets zero; unknown security outcomes are rejected above.
            eligible = sorted(next(iter(scores.values())).index)
            aligned = outcome.reindex(eligible)
            baseline = float(aligned.mean()) if len(aligned) else 0.0
            for criterion, table in scores.items():
                table = table.reindex(eligible)
                if priority is not None:
                    shuffled = sorted(eligible, key=lambda security_id: priority[security_id])
                    table = pd.Series(table.reindex(shuffled).to_numpy(), index=eligible)
                for key in family:
                    if key[0] != criterion:
                        continue
                    chosen = pick(table, key[1])
                    selected = float(aligned.reindex(chosen).mean()) if chosen else 0.0
                    values[key].append(selected - baseline)
        return {key: float(np.mean(value)) for key, value in values.items()}

    observed = statistic()
    rng = np.random.default_rng(config.random_seed + 999)
    exceed = {key: 0 for key in family}
    for _ in range(config.permutations):
        priority = dict(zip(universe, rng.random(len(universe))))
        null = statistic(priority)
        for key in family:
            exceed[key] += null[key] >= observed[key]
    raw = {key: (1 + exceed[key]) / (1 + config.permutations) for key in family}
    corrected = holm_adjust(raw)
    return {key: {"p_raw": raw[key], "p_holm": corrected[key], "statistic": observed[key],
                  "target": config.permutation_target, "family_size": len(family)} for key in family}


def synthetic(kind: str, n=300, years=20, seed=1) -> dict[str, pd.DataFrame]:
    """Synthetic-only harness; never a substitute for a complete historical universe."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2003-01-01", periods=252 * years)
    out = {}
    for i in range(n):
        volatility = rng.uniform(0.15, 0.80) / np.sqrt(252)
        if kind == "random_walk":
            r = rng.normal(rng.normal(0.08, 0.08) / 252, volatility, len(days))
        elif kind == "regime":
            stay, amplitude = rng.uniform(0.95, 0.997), rng.uniform(0.0, 1.2) / 252
            state, direction = np.empty(len(days)), 1
            for j in range(len(days)):
                if rng.random() > stay:
                    direction = -direction
                state[j] = direction
            r = 0.06 / 252 + amplitude * state + rng.normal(0, volatility, len(days))
        else:
            raise ValueError(kind)
        close = 50 * np.exp(np.cumsum(r))
        open_ = np.r_[50, close[:-1]] * np.exp(rng.normal(0, 0.2 * volatility, len(days)))
        high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 0.5 * volatility, len(days))))
        low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 0.5 * volatility, len(days))))
        out[f"S{i:03d}"] = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=days)
    return out
