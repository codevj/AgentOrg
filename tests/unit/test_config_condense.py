"""Tests for condense_after config helpers."""

from pathlib import Path

import yaml

from agentorg.config import (
    Config,
    get_condense_after,
    set_condense_after,
)


def _make_config(tmp_path: Path) -> Config:
    org_home = tmp_path / "org"
    org_home.mkdir()
    return Config(starters_dir=tmp_path / "starters", org_home=org_home)


def test_get_condense_after_default(tmp_path):
    """Returns 5 when no settings file exists."""
    config = _make_config(tmp_path)
    assert get_condense_after(config) == 5


def test_get_condense_after_from_file(tmp_path):
    """Reads value from settings.yaml."""
    config = _make_config(tmp_path)
    settings_file = config.org_home / "settings.yaml"
    settings_file.write_text(yaml.dump({"condense_after": 10}))
    assert get_condense_after(config) == 10


def test_get_condense_after_invalid_value(tmp_path):
    """Returns default for non-integer values."""
    config = _make_config(tmp_path)
    settings_file = config.org_home / "settings.yaml"
    settings_file.write_text(yaml.dump({"condense_after": "not-a-number"}))
    assert get_condense_after(config) == 5


def test_set_condense_after(tmp_path):
    """Writes to settings.yaml and preserves other keys."""
    config = _make_config(tmp_path)
    settings_file = config.org_home / "settings.yaml"
    settings_file.write_text(yaml.dump({"default_team": "my-team"}))

    set_condense_after(config, 8)

    data = yaml.safe_load(settings_file.read_text())
    assert data["condense_after"] == 8
    assert data["default_team"] == "my-team"  # preserved


def test_set_condense_after_creates_directory(tmp_path):
    """Creates org_home if it doesn't exist yet."""
    org_home = tmp_path / "new_org"
    config = Config(starters_dir=tmp_path / "starters", org_home=org_home)

    set_condense_after(config, 3)

    settings_file = org_home / "settings.yaml"
    assert settings_file.is_file()
    data = yaml.safe_load(settings_file.read_text())
    assert data["condense_after"] == 3


def test_set_condense_after_zero(tmp_path):
    """Can set to 0 to disable condensation."""
    config = _make_config(tmp_path)
    set_condense_after(config, 0)
    assert get_condense_after(config) == 0


def test_condense_after_in_default_settings():
    """condense_after is in the default settings dict."""
    from agentorg.config import _DEFAULT_SETTINGS
    assert "condense_after" in _DEFAULT_SETTINGS
    assert _DEFAULT_SETTINGS["condense_after"] == 5
