"""Tests for agentic/config.py: strict booleans, sleeve_initial_qty, the state dir."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agentic import config  # noqa: E402


def example():
    return json.loads(config.EXAMPLE.read_text())


@pytest.mark.parametrize("path, value", [
    (("live",), "false"), (("live",), "no"), (("live",), 0), (("account", "approvals_required"), "false"),
    (("assets", 1, "enabled"), "false"), (("assets", 0, "vehicle", "fractional"), "true"),
])
def test_booleans_must_be_json_booleans(path, value):
    """Regression: "live": "false" (quoted) validated to live=True and "enabled": "false" enabled an asset."""
    raw = example()
    d = raw
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value
    with pytest.raises(config.ConfigError, match="true or false"):
        config.validate(raw)


def test_valid_example_and_defaults():
    c = config.validate(example())
    assert c["live"] is False and c["account"]["approvals_required"] is True and c["sleeve_initial_qty"] == {}
    raw = example()
    del raw["live"], raw["account"]["approvals_required"]
    raw["sleeve_initial_qty"] = {"etha": 9, "sol-usd": "0.5", "_note": "x"}
    c = config.validate(raw)
    assert c["live"] is False and c["account"]["approvals_required"] is True
    assert c["sleeve_initial_qty"] == {"ETHA": 9.0, "SOL-USD": 0.5}
    for bad in ({"ETHA": -1}, {"ETHA": "lots"}, {"ETHA": True}, ["ETHA"]):
        raw["sleeve_initial_qty"] = bad
        with pytest.raises(config.ConfigError):
            config.validate(raw)


def test_state_dir_relative_resolves_against_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_STATE_DIR", "private/agentic_test_x")
    monkeypatch.chdir(tmp_path)
    assert config.state_dir() == (REPO / "private" / "agentic_test_x").resolve()
    monkeypatch.setenv("AGENTIC_STATE_DIR", str(tmp_path / "abs"))
    assert config.state_dir() == tmp_path / "abs"
    monkeypatch.delenv("AGENTIC_STATE_DIR")
    assert config.state_dir() == REPO / "private" / "agentic"
