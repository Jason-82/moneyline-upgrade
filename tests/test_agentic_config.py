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


def test_entry_rise_cap_default_is_050():
    """Default max_join_rise_frac 0.50 (agentic/README.md section 9): filled when the key or the block is missing,
    an explicit null (the earlier example's value) keeps the cap off, and an asset may set its own."""
    assert config.DEFAULT_ENTRY["max_join_rise_frac"] == 0.50
    assert config.validate(example())["entry"]["max_join_rise_frac"] == 0.50
    raw = example()
    del raw["entry"]
    assert config.validate(raw)["entry"]["max_join_rise_frac"] == 0.50
    raw["entry"] = {"policy": "join_recent", "max_join_rise_frac": None}
    assert config.validate(raw)["entry"]["max_join_rise_frac"] is None
    raw["assets"][0]["entry"] = {"max_join_rise_frac": 0.3}
    assert config.validate(raw)["assets"][0]["entry"] == {"max_join_rise_frac": 0.3}
    for bad in (-0.5, "50%", True, float("inf")):
        raw["entry"] = {"max_join_rise_frac": bad}
        with pytest.raises(config.ConfigError, match="max_join_rise_frac"):
            config.validate(raw)


def test_json_saved_with_a_utf8_bom_is_read(tmp_path):
    """Regression: Windows Notepad's "UTF-8 with BOM" made load_config (and the hook's reads) raise JSONDecodeError,
    so every command failed and the hook blocked previews and places. The BOM is now skipped; the content is checked
    exactly as before."""
    from agentic import hooks, ledger
    raw = example()
    f = tmp_path / "config.json"
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps(raw).encode("utf-8"))
    assert config.load_config(f) == config.validate(raw)
    assert hooks.read_json(f) == raw == ledger.read_json(f, None)
    raw["live"] = "false"                                          # validation is unchanged
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps(raw).encode("utf-8"))
    with pytest.raises(config.ConfigError, match="true or false"):
        config.load_config(f)
    f.write_bytes(b"\xef\xbb\xbf{not json")
    with pytest.raises(ValueError):
        config.load_config(f)
