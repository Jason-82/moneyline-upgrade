"""Declared experiment settings and a tamper-evident, single-use holdout gate.

Freezing a configuration is a local research action, not evidence that a strategy
works.  In particular, exploratory data cannot create a deployable candidate.
The reserved window is fixed; neither an incomplete data source nor a CLI option
is allowed to turn 2023--2025 into a shorter, convenient test.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any


HOLDOUT_START = "2023-01-01"
HOLDOUT_END = "2025-12-31"
DEVELOPMENT_END = "2022-12-31"
FIXED_SIGNAL = {"period": 10, "factor": 2.0, "atr_type": "rma", "src": "hl2", "variant": "reset"}


@dataclass(frozen=True)
class Window:
    formation_start: str
    formation_end: str
    test_start: str
    test_end: str


DEVELOPMENT_WINDOWS = tuple(
    Window(f"{year - 5}-01-01", f"{year - 1}-12-31", f"{year}-01-01", f"{year + 2}-12-31")
    for year in range(2005, 2023, 3)
)
HOLDOUT_WINDOW = Window("2018-01-01", "2022-12-31", HOLDOUT_START, HOLDOUT_END)


@dataclass(frozen=True)
class ExperimentConfig:
    schema_version: int = 2
    signal: dict = field(default_factory=lambda: dict(FIXED_SIGNAL))
    timeframe: str = "daily"
    execution: str = "next_open"
    initial_entry: str = "prior_close_green"
    parking: str = "cash"
    criteria: tuple[str, ...] = ("skill",)
    levels: tuple[str, ...] = ("top5", "top10", "top20", "top30", "top40", ">10", "all")
    development_windows: tuple[Window, ...] = DEVELOPMENT_WINDOWS
    holdout_window: Window = HOLDOUT_WINDOW
    min_formation_bars: int = 200
    min_formation_coverage: float = 0.8
    min_closed_trades: int = 8
    warmup_bars: int = 100
    stale_formation_sessions: int = 0
    cost_bps_per_side: float = 3.0
    short_term_tax_rate: float = 0.35
    long_term_tax_rate: float = 0.20
    tax_enabled: bool = True
    qualified_dividend_fraction: float = 0.0
    dividend_reinvestment: str = "next_open"
    cash_rate_policy: str = "zero_unless_observed_daily_series"
    cash_rates_sha256: str | None = None
    initial_capital: float = 100000.0
    membership_asof: str = "formation_end"
    excluded_symbols: tuple[str, ...] = ("SPY", "QQQ", "IWM", "DIA", "VOO", "IVV")
    sector_guard: bool = False
    correlation_guard: bool = False
    random_seed: int = 0
    permutations: int = 1000
    multiple_testing: str = "holm_across_all_criteria_and_levels"
    permutation_target: str = "future_timing_skill_not_portfolio_profit"
    qualifying_cagr_tolerance_pp: float = 2.0
    qualifying_drawdown_improvement_pp: float = 15.0
    qualifying_window_fraction: float = 2.0 / 3.0
    choice_within_best_pp: float = 1.0
    chosen_criterion: str | None = None
    chosen_level: str | None = None
    candidate_role: str = "unselected"

    def validate(self) -> None:
        if self.signal != FIXED_SIGNAL or self.timeframe != "daily" or self.execution != "next_open":
            raise ValueError("The research contract fixes daily ATR(10) x 2 reset signals and next-open execution")
        if self.initial_entry != "prior_close_green":
            raise ValueError("At a selection date a prior-close green stock enters at the next open")
        if self.parking != "cash":
            raise ValueError("Only the declared cash-parking primary strategy is enabled")
        if self.dividend_reinvestment != "next_open":
            raise ValueError("All controls use declared next-open dividend reinvestment")
        if self.holdout_window != HOLDOUT_WINDOW:
            raise ValueError("Reserved holdout must be 2018--2022 formation -> full 2023--2025 test")
        previous_end = None
        import pandas as pd
        for w in self.development_windows:
            fs, fe, ts, te = map(pd.Timestamp, (w.formation_start, w.formation_end, w.test_start, w.test_end))
            if not fs <= fe < ts <= te or te > pd.Timestamp(DEVELOPMENT_END):
                raise ValueError("Development windows must be causal and end before the reserved holdout")
            if previous_end is not None and ts <= previous_end:
                raise ValueError("Development test windows may not overlap")
            if previous_end is not None and ts > previous_end + pd.Timedelta(days=7):
                raise ValueError("Development windows must cover a continuous test horizon")
            previous_end = te
        if not self.development_windows:
            raise ValueError("At least one development window is required")
        if not self.criteria or any(c not in ("skill", "edge", "gate", "vol", "random") for c in self.criteria):
            raise ValueError("Unknown or empty criterion family")
        if len(self.criteria) != len(set(self.criteria)) or len(self.levels) != len(set(self.levels)):
            raise ValueError("Experiment choices must be unique")
        if any(l not in ("top5", "top10", "top20", "top30", "top40", ">10", "all") for l in self.levels):
            raise ValueError("Unknown strictness level")
        if self.membership_asof != "formation_end":
            raise ValueError("Membership must be observed as of formation end")
        if self.sector_guard or self.correlation_guard:
            raise ValueError("Sector/correlation guards are undeveloped hypotheses; leave them off")
        if not 0 <= self.min_formation_coverage <= 1 or self.min_closed_trades < 0 or self.permutations < 0:
            raise ValueError("Invalid eligibility or permutation setting")
        if any(not 0 <= x <= 1 for x in (self.short_term_tax_rate, self.long_term_tax_rate, self.qualified_dividend_fraction)):
            raise ValueError("Tax rates and qualified dividend fraction must be in [0,1]")
        if self.cost_bps_per_side < 0 or self.initial_capital <= 0:
            raise ValueError("Invalid cost/capital setting")
        if (self.chosen_criterion is None) != (self.chosen_level is None):
            raise ValueError("A holdout candidate needs both criterion and level")
        if self.chosen_criterion is not None and (self.chosen_criterion not in self.criteria or self.chosen_level not in self.levels):
            raise ValueError("Candidate must belong to the frozen experiment family")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "ExperimentConfig":
        d = dict(raw)
        for key in ("criteria", "levels", "excluded_symbols"):
            if key in d:
                d[key] = tuple(d[key])
        if "development_windows" in d:
            d["development_windows"] = tuple(Window(**w) for w in d["development_windows"])
        if "holdout_window" in d:
            d["holdout_window"] = Window(**d["holdout_window"])
        obj = cls(**d)
        obj.validate()
        return obj


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def implementation_fingerprint() -> str:
    """Freeze research semantics as well as numbers/settings before reserved data."""
    root = Path(__file__).resolve().parent.parent
    files = ("research/config.py", "research/run.py", "research/selection.py",
             "research/portfolio.py", "research/tax.py", "research/data_contract.py",
             "research/calendar.py", "screener/data.py", "analysis_2026/moneyline_ref.py")
    return sha256({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files})


def freeze_config(config: ExperimentConfig, path: str | Path, *, dataset_manifest_sha256: str,
                  development_report_sha256: str | None = None) -> dict:
    """Write an exclusive, immutable-by-contract artifact; never silently overwrite."""
    config.validate()
    payload = {"schema_version": 1, "frozen_at": datetime.now(timezone.utc).isoformat(),
               "experiment": config.to_dict(), "dataset_manifest_sha256": dataset_manifest_sha256,
               "development_report_sha256": development_report_sha256,
               "implementation_sha256": implementation_fingerprint(),
               "holdout_use": "one_attempt_report_failure_or_success_without_retuning"}
    payload["sha256"] = sha256(payload)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def read_frozen(path: str | Path) -> tuple[ExperimentConfig, dict]:
    raw = json.loads(Path(path).read_text())
    expected = raw.get("sha256")
    if not expected or expected != sha256({k: v for k, v in raw.items() if k != "sha256"}):
        raise ValueError("Frozen experiment hash is invalid; holdout will not be read")
    config = ExperimentConfig.from_dict(raw["experiment"])
    if config.chosen_level is None:
        raise ValueError("No candidate was selected before freezing; holdout will not be read")
    if raw.get("implementation_sha256") != implementation_fingerprint():
        raise ValueError("Research implementation changed after freezing; holdout will not be read")
    return config, raw


def claim_holdout(path: str | Path, artifact: dict) -> Path:
    """Claim once before reading holdout rows, even if loading/testing later fails.

    This is a transparent local guard, not an unbypassable security boundary. A
    manifest fingerprint mismatch is checked before this function is called.
    """
    marker = Path(str(path) + ".holdout-consumed.json")
    payload = {"artifact_sha256": artifact["sha256"],
               "claimed_at": datetime.now(timezone.utc).isoformat(),
               "status": "started", "reserved_test_end": HOLDOUT_END}
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return marker


def finish_holdout(marker: str | Path, *, status: str, report_sha256: str | None = None,
                   error: str | None = None) -> None:
    p = Path(marker)
    raw = json.loads(p.read_text())
    raw.update(status=status, finished_at=datetime.now(timezone.utc).isoformat(),
               report_sha256=report_sha256, error=error)
    p.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")
