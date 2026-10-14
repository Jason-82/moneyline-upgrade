"""Input freezing, causal universes and complete-horizon failure regressions."""
from dataclasses import replace
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from crypto_research.config import (CryptoExperimentConfig, CryptoWindow, freeze_config,
                                   read_frozen, sha256)
from crypto_research.data import load_bundle
from crypto_research.run import (paired_variant_results, require_formation_history,
                                run_experiment, save_result, selected_symbols)


@pytest.fixture
def experiment(tmp_path):
    root = tmp_path / "bundle"
    (root / "prices").mkdir(parents=True)
    dates = pd.date_range("2018-01-01", "2020-01-04", freq="D")
    securities = []
    for symbol, scale in (("BTCUSDT", 100.0), ("ETHUSDT", 10.0)):
        close = scale * np.exp(np.arange(len(dates)) * .001)
        frame = pd.DataFrame({"Date": dates, "Open": close * .9998,
                              "High": close * 1.002, "Low": close * .998,
                              "Close": close, "Volume": 100000., "QuoteVolume": 10000000.})
        file = root / "prices" / f"{symbol}.csv"
        frame.to_csv(file, index=False)
        securities.append({"symbol": symbol, "price_file": f"prices/{symbol}.csv",
                           "price_sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    (root / "manifest.json").write_text(json.dumps({"securities": securities,
                                                    "quality_flags": ["venue-only exploratory history"]}))
    pd.DataFrame([{"formation_date": "2019-12-31", "group": "liquid_top20", "rank": rank,
                   "symbol": symbol, "median_quote_volume": 10000000.}
                  for rank, symbol in enumerate(("BTCUSDT", "ETHUSDT"), 1)]).to_csv(root / "universe.csv", index=False)
    config = CryptoExperimentConfig(candidates=("moneyline", "confirm2"), groups=("liquid_top20",),
                                    windows=(CryptoWindow("test", "2019-12-31", "2020-01-01", "2020-01-04"),),
                                    costs_bps_per_side=(10.,), diagnostic_symbols=("BTCUSDT",))
    frozen_path = tmp_path / "frozen.json"
    frozen = freeze_config(config, root, frozen_path)
    return root, config, frozen_path, frozen


def test_root_configuration_aliases_and_prior_exposure():
    raw = {"windows": [{"formation_date": "2019-12-31", "start": "2020-01-01", "end": "2022-12-31"}],
           "max_exposure": 1.0, "volatility_lookback": 90, "volatility_rebalance_threshold": .20,
           "historical_validation_is_independent_holdout": False}
    config = CryptoExperimentConfig.from_dict(raw)
    assert config.windows[0].name == "development"
    assert config.leverage_cap == 1.0
    with pytest.raises(ValueError, match="Previously exposed"):
        CryptoExperimentConfig.from_dict(dict(raw, historical_validation_is_independent_holdout=True))


def test_freeze_covers_actual_prices_not_only_manifest(experiment):
    root, config, frozen_path, frozen = experiment
    checked, artifact = read_frozen(frozen_path, root)
    assert checked == config
    assert "prices/BTCUSDT.csv" in artifact["input_files_sha256"]
    price_file = root / "prices/BTCUSDT.csv"
    price_file.write_text(price_file.read_text() + "\n")
    with pytest.raises(ValueError, match="dataset changed"):
        read_frozen(frozen_path, root)


def test_freeze_is_exclusive_and_outside_inputs(experiment):
    root, config, frozen_path, _ = experiment
    with pytest.raises(FileExistsError):
        freeze_config(config, root, frozen_path)
    with pytest.raises(ValueError, match="outside"):
        freeze_config(config, root, root / "frozen.json")


def test_universe_change_is_frozen_even_when_manifest_unchanged(experiment):
    root, _, frozen_path, _ = experiment
    universe = pd.read_csv(root / "universe.csv")
    universe.loc[0, "symbol"] = "IMAGINARYUSDT"
    universe.to_csv(root / "universe.csv", index=False)
    with pytest.raises(ValueError, match="dataset changed"):
        read_frozen(frozen_path, root)


def test_auxiliary_benchmark_is_frozen(experiment, tmp_path):
    root, config, _, _ = experiment
    benchmark = tmp_path / "benchmark"
    benchmark.mkdir()
    (benchmark / "SPY.csv").write_text("Date,Close\n2020-01-02,300\n")
    frozen_path = tmp_path / "with-benchmark.json"
    freeze_config(config, root, frozen_path, benchmark=benchmark)
    read_frozen(frozen_path, root, benchmark=benchmark)
    (benchmark / "SPY.csv").write_text("Date,Close\n2020-01-02,301\n")
    with pytest.raises(ValueError, match="benchmark changed"):
        read_frozen(frozen_path, root, benchmark=benchmark)


def test_tampered_artifact_hash_is_refused(experiment):
    root, _, frozen_path, _ = experiment
    artifact = json.loads(frozen_path.read_text())
    artifact["experiment"]["initial_capital"] *= 2
    frozen_path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError, match="hash is invalid"):
        read_frozen(frozen_path, root)


def test_future_data_cannot_change_preformation_warmup(experiment):
    root, config, _, _ = experiment
    data = load_bundle(root)
    window = config.windows[0]
    picks = selected_symbols(data, window, "liquid_top20", config)
    require_formation_history(data.prices, picks, window.formation_date, 360)
    data.prices["BTCUSDT"] = data.prices["BTCUSDT"].loc[:"2019-12-31"]
    assert selected_symbols(data, window, "liquid_top20", config) == picks
    require_formation_history(data.prices, picks, window.formation_date, 360)


def test_warmup_gap_is_not_repaired_with_future_observations(experiment):
    root, config, _, _ = experiment
    data = load_bundle(root)
    data.prices["BTCUSDT"] = data.prices["BTCUSDT"].drop(pd.Timestamp("2019-12-01"))
    with pytest.raises(ValueError, match="preformation"):
        require_formation_history(data.prices, ("BTCUSDT",), "2019-12-31", 360)


def test_full_family_run_keeps_missing_spy_and_unused_cash_slots(experiment):
    root, config, _, artifact = experiment
    result = run_experiment(load_bundle(root), config, frozen=artifact)
    baskets = result.summary.loc[result.summary.group == "liquid_top20"]
    assert len(baskets) == len(config.candidates) + 1
    assert baskets.status.eq("IDENTIFIED_EXPLORATORY").all()
    assert baskets.selected_count.eq(2).all()
    assert result.report["formations"][0]["fixed_cash_slots"] == 18
    spy = result.summary.loc[result.summary.candidate == "SPY_total_return_buy_hold"].iloc[0]
    assert spy.status == "UNIDENTIFIED" and np.isnan(spy.cagr)
    assert result.report["qualified_candidates"] == []
    assert result.report["deployment_blocked"] is True
    assert result.report["independent_holdout"] is False
    assert len(result.paired_variants) == 4  # Two coins x confirmation/holding.
    for _, group in result.paths.groupby(["window", "group", "candidate", "cost_bps"]):
        assert len(group) == 4


def test_missing_selected_future_bar_keeps_all_failed_candidates(experiment):
    root, config, _, artifact = experiment
    data = load_bundle(root)
    data.prices["BTCUSDT"] = data.prices["BTCUSDT"].drop(pd.Timestamp("2020-01-03"))
    result = run_experiment(data, config, frozen=artifact)
    baskets = result.summary.loc[result.summary.group == "liquid_top20"]
    assert len(baskets) == len(config.candidates) + 1
    assert baskets.status.eq("UNIDENTIFIED").all()
    assert baskets.cagr.isna().all()
    assert baskets.selected_count.eq(2).all()
    btc = result.coin_results.loc[result.coin_results.symbol == "BTCUSDT"]
    eth = result.coin_results.loc[result.coin_results.symbol == "ETHUSDT"]
    assert len(btc) == 3 and btc.cagr.isna().all()
    assert eth.status.eq("IDENTIFIED_EXPLORATORY").all()
    assert not result.paired_variants.loc[result.paired_variants.symbol == "BTCUSDT", "paired_identified"].any()


def test_save_exclusive_standard_json_and_artifact_checksums(experiment, tmp_path):
    root, config, _, artifact = experiment
    result = run_experiment(load_bundle(root), config, frozen=artifact)
    output = tmp_path / "run"
    report = save_result(result, output)
    text = (output / "report.json").read_text()
    assert "NaN" not in text and "Infinity" not in text
    parsed = json.loads(text)
    spy = next(r for r in parsed["summary"] if r["candidate"] == "SPY_total_return_buy_hold")
    assert spy["cagr"] is None
    assert parsed["report_sha256"] == sha256({k: v for k, v in parsed.items() if k != "report_sha256"})
    for name, digest in report["artifacts_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    with pytest.raises(FileExistsError):
        save_result(result, output)


def test_run_requires_frozen_matching_settings(experiment):
    root, config, _, artifact = experiment
    data = load_bundle(root)
    with pytest.raises(ValueError, match="requires"):
        run_experiment(data, config)
    with pytest.raises(ValueError, match="differ"):
        run_experiment(data, replace(config, initial_capital=200000), frozen=artifact)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 10000.0])
def test_invalid_cost_is_refused(bad):
    with pytest.raises(ValueError, match="Costs"):
        replace(CryptoExperimentConfig(), costs_bps_per_side=(bad,)).validate()
