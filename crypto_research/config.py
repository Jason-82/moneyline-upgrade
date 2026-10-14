"""A declared, hash-frozen crypto comparison family, not a trading approval.

These are historically informed research windows.  The later window has already
been visible to previous work and the cited paper; freezing now does not turn it
into a globally untouched holdout.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any


CANDIDATES = ("moneyline", "confirm2", "breakout20", "wider_exit3",
              "donchianensemble_fixed", "donchianensemble_vol25")
GROUPS = ("liquid_top20", "liquidity_next20")


@dataclass(frozen=True)
class CryptoWindow:
    name: str
    formation_date: str
    start: str
    end: str


WINDOWS = (
    CryptoWindow("development", "2019-12-31", "2020-01-01", "2022-12-31"),
    CryptoWindow("later_historical_validation", "2022-12-31", "2023-01-01", "2025-12-31"),
)


@dataclass(frozen=True)
class CryptoExperimentConfig:
    schema_version: int = 1
    candidates: tuple[str, ...] = CANDIDATES
    groups: tuple[str, ...] = GROUPS
    windows: tuple[CryptoWindow, ...] = WINDOWS
    costs_bps_per_side: tuple[float, ...] = (0.0, 10.0, 50.0, 95.0)
    attribution_cost_bps: float = 10.0
    initial_capital: float = 100000.0
    slot_capacity: int = 20
    min_warmup_bars: int = 360
    execution: str = "next_utc_daily_open"
    cash_daily_return: float = 0.0
    leverage_cap: float = 1.0
    volatility_target: float = 0.25
    volatility_days: int = 90
    volatility_rebalance_relative_threshold: float = 0.20
    volatility_standard_deviation: str = "sample_simple_returns_sqrt365"
    liquidity_days: int = 30
    min_median_quote_volume: float = 2000000.0
    min_listing_days: int = 365
    formation_frequency: str = "fixed_three_year_baskets"
    tax_policy: str = "pretax_only"
    run_illustrative_tax: bool = False
    short_term_tax_rate: float = 0.35
    long_term_tax_rate: float = 0.20
    historical_validation_is_independent_holdout: bool = False
    diagnostic_symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    spy_cost_bps_per_side: float = 3.0
    cost_95bps_role: str = "routing_sensitivity_proxy_not_verified_future_fee"
    family_selection: str = "report_all_no_qualified_winner"
    sample_status: str = "historically_informed_not_globally_untouched"
    benchmark_quote_assumption: str = "USDT_equals_USD_depeg_risk_not_modelled"

    def validate(self) -> None:
        import pandas as pd
        if not self.candidates or len(set(self.candidates)) != len(self.candidates) or any(c not in CANDIDATES for c in self.candidates):
            raise ValueError("Unknown, empty or duplicate candidate family")
        if not self.groups or len(set(self.groups)) != len(self.groups) or any(g not in GROUPS for g in self.groups):
            raise ValueError("Unknown, empty or duplicate liquidity groups")
        if not self.windows:
            raise ValueError("A declared full historical window is required")
        previous = None
        for window in self.windows:
            formation, start, end = map(pd.Timestamp, (window.formation_date, window.start, window.end))
            if not formation < start <= end or any(x.tzinfo is not None or x != x.normalize() for x in (formation, start, end)):
                raise ValueError("Window dates must be causal midnight UTC dates")
            if previous is not None and start <= previous:
                raise ValueError("Declared windows may not overlap")
            previous = end
        if not self.costs_bps_per_side or len(set(self.costs_bps_per_side)) != len(self.costs_bps_per_side) or any(not 0 <= c < 10000 for c in self.costs_bps_per_side):
            raise ValueError("Costs must be unique finite nonnegative bps below 10000")
        if self.attribution_cost_bps not in self.costs_bps_per_side:
            raise ValueError("Attribution cost must belong to declared cost scenarios")
        if not math.isfinite(self.initial_capital) or self.initial_capital <= 0 or self.slot_capacity != 20 or self.min_warmup_bars < 360:
            raise ValueError("Positive capital, twenty fixed slots, and at least 360 warmup bars are required")
        if self.execution != "next_utc_daily_open" or self.cash_daily_return != 0 or self.leverage_cap != 1:
            raise ValueError("This cash-only comparison fixes next UTC open, zero cash yield and no leverage")
        if (self.volatility_target, self.volatility_days, self.volatility_rebalance_relative_threshold, self.volatility_standard_deviation) != (0.25, 90, 0.20, "sample_simple_returns_sqrt365"):
            raise ValueError("Volatility adaptation is fixed before observing comparison results")
        if (self.liquidity_days, self.min_listing_days, self.min_median_quote_volume) != (30, 365, 2000000.0):
            raise ValueError("The universe contract fixes past-30-day median quote volume and listing age")
        if self.tax_policy != "pretax_only" or self.family_selection != "report_all_no_qualified_winner":
            raise ValueError("This comparison neither estimates personal taxes nor approves a best strategy")
        if self.historical_validation_is_independent_holdout:
            raise ValueError("Previously exposed historical years cannot be labelled an independent holdout")
        if any(not 0 <= r <= 1 for r in (self.short_term_tax_rate, self.long_term_tax_rate)):
            raise ValueError("Illustrative tax rates must be between zero and one")
        if not 0 <= self.spy_cost_bps_per_side < 10000 or len(set(self.diagnostic_symbols)) != len(self.diagnostic_symbols):
            raise ValueError("Invalid SPY cost or duplicate diagnostic symbols")
        if self.formation_frequency != "fixed_three_year_baskets" or self.sample_status != "historically_informed_not_globally_untouched":
            raise ValueError("This implementation uses historically informed fixed baskets, not the paper's monthly universes")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "CryptoExperimentConfig":
        fields = dict(raw)
        aliases = {"max_exposure": "leverage_cap", "volatility_lookback": "volatility_days",
                   "volatility_rebalance_threshold": "volatility_rebalance_relative_threshold"}
        for old, new in aliases.items():
            if old in fields:
                if new in fields:
                    raise ValueError(f"Duplicated setting aliases: {old} and {new}")
                fields[new] = fields.pop(old)
        for name in ("candidates", "groups", "costs_bps_per_side", "diagnostic_symbols"):
            if name in fields:
                fields[name] = tuple(fields[name])
        if "windows" in fields:
            fields["windows"] = tuple(CryptoWindow(name=w.get("name", "development" if str(w["start"]) < "2023" else "later_historical_validation"),
                                                   **{k: v for k, v in w.items() if k != "name"}) for w in fields["windows"])
        result = cls(**fields)
        result.validate()
        return result


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def bundle_fingerprint(path: str | Path) -> tuple[str, dict[str, str]]:
    """Hash actual complete inputs, including normalized prices and universe rows.

    A manifest's source labels cannot stand in for the content of the dataset.
    Symlinks are refused to keep the frozen input boundary unambiguous.
    """
    root = Path(path).resolve()
    if not (root / "manifest.json").is_file() or not (root / "universe.csv").is_file():
        raise ValueError("Bundle requires manifest.json and dated universe.csv")
    files = {}
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise ValueError("Frozen bundle cannot contain symlinks")
        if file.is_file():
            files[file.relative_to(root).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return sha256(files), files


def implementation_fingerprint() -> str:
    root = Path(__file__).resolve().parent.parent
    names = [f"crypto_research/{name}" for name in ("config.py", "data.py", "signals.py", "portfolio.py", "run.py")]
    if (root / "crypto_research/benchmark.py").exists():
        names.append("crypto_research/benchmark.py")
    names += ["analysis_2026/moneyline_ref.py", "research/tax.py"]
    return sha256({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names})


def _auxiliary_fingerprint(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError("Benchmark directory must exist before freezing")
    result = {}
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise ValueError("Benchmark cannot contain symlinks")
        if file.is_file():
            result[file.relative_to(root).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    if not result:
        raise ValueError("Benchmark directory is empty")
    return result


def freeze_config(config: CryptoExperimentConfig, dataset: str | Path, output: str | Path,
                  *, benchmark: str | Path | None = None) -> dict:
    config.validate()
    root, destination = Path(dataset).resolve(), Path(output).resolve()
    if destination.is_relative_to(root):
        raise ValueError("Frozen configuration must live outside its input bundle")
    digest, files = bundle_fingerprint(root)
    benchmark_files = _auxiliary_fingerprint(benchmark)
    payload = {"schema_version": 1, "frozen_at": datetime.now(timezone.utc).isoformat(),
               "experiment": config.to_dict(), "dataset_sha256": digest,
               "input_files_sha256": files, "implementation_sha256": implementation_fingerprint(),
               "benchmark_files_sha256": benchmark_files,
               "sample_status": config.sample_status,
               "freeze_role": "comparison_family_declared_before_this_run_not_untouched_holdout"}
    payload["sha256"] = sha256(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def read_frozen(path: str | Path, dataset: str | Path,
                *, benchmark: str | Path | None = None) -> tuple[CryptoExperimentConfig, dict]:
    payload = json.loads(Path(path).read_text())
    if payload.get("sha256") != sha256({k: v for k, v in payload.items() if k != "sha256"}):
        raise ValueError("Frozen comparison hash is invalid")
    if payload.get("implementation_sha256") != implementation_fingerprint():
        raise ValueError("Crypto implementation changed after freezing")
    digest, files = bundle_fingerprint(dataset)
    if payload.get("dataset_sha256") != digest or payload.get("input_files_sha256") != files:
        raise ValueError("Actual dataset changed after freezing")
    if payload.get("benchmark_files_sha256", {}) != _auxiliary_fingerprint(benchmark):
        raise ValueError("Actual benchmark changed after freezing")
    return CryptoExperimentConfig.from_dict(payload["experiment"]), payload
