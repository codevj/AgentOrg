"""Tests for ReflectionMode config helpers."""

from pathlib import Path

import yaml

from agentorg.config import (
    Config,
    ReflectionMode,
    get_reflection_mode,
    set_reflection_mode,
)


def _make_config(tmp_path: Path) -> Config:
    org_home = tmp_path / "org"
    org_home.mkdir()
    return Config(starters_dir=tmp_path / "starters", org_home=org_home)


def test_get_reflection_mode_default(tmp_path):
    """Returns AUTO when no settings file exists."""
    config = _make_config(tmp_path)
    assert get_reflection_mode(config) == ReflectionMode.AUTO


def test_get_reflection_mode_from_config(tmp_path):
    """Reads mode from the config's reflection field."""
    config = Config(
        starters_dir=tmp_path / "starters",
        org_home=tmp_path / "org",
        reflection="review",
    )
    assert get_reflection_mode(config) == ReflectionMode.REVIEW


def test_get_reflection_mode_off(tmp_path):
    config = Config(
        starters_dir=tmp_path / "starters",
        org_home=tmp_path / "org",
        reflection="off",
    )
    assert get_reflection_mode(config) == ReflectionMode.OFF


def test_invalid_mode_falls_back(tmp_path):
    """Returns AUTO for an invalid reflection value."""
    config = Config(
        starters_dir=tmp_path / "starters",
        org_home=tmp_path / "org",
        reflection="bogus",
    )
    assert get_reflection_mode(config) == ReflectionMode.AUTO


def test_set_reflection_mode(tmp_path):
    """Writes to settings.yaml and preserves other keys."""
    config = _make_config(tmp_path)
    settings_file = config.org_home / "settings.yaml"

    # Pre-seed with another setting
    settings_file.write_text(yaml.dump({"default_team": "my-team"}))

    set_reflection_mode(config, ReflectionMode.REVIEW)

    data = yaml.safe_load(settings_file.read_text())
    assert data["reflection"] == "review"
    assert data["default_team"] == "my-team"  # preserved


def test_set_reflection_mode_creates_directory(tmp_path):
    """Creates org_home if it doesn't exist yet."""
    org_home = tmp_path / "new_org"
    config = Config(starters_dir=tmp_path / "starters", org_home=org_home)

    set_reflection_mode(config, ReflectionMode.OFF)

    settings_file = org_home / "settings.yaml"
    assert settings_file.is_file()
    data = yaml.safe_load(settings_file.read_text())
    assert data["reflection"] == "off"


def test_set_reflection_mode_removes_legacy_key(tmp_path):
    """Removes the old auto_reflect key when setting reflection mode."""
    config = _make_config(tmp_path)
    settings_file = config.org_home / "settings.yaml"
    settings_file.write_text(yaml.dump({"auto_reflect": True}))

    set_reflection_mode(config, ReflectionMode.AUTO)

    data = yaml.safe_load(settings_file.read_text())
    assert "auto_reflect" not in data
    assert data["reflection"] == "auto"


def test_reflection_mode_enum_values():
    """All three modes have the expected string values."""
    assert ReflectionMode.AUTO.value == "auto"
    assert ReflectionMode.REVIEW.value == "review"
    assert ReflectionMode.OFF.value == "off"
