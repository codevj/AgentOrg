"""Tests for backend switching (get/set active backend)."""

from pathlib import Path

import pytest

from agentorg.config import Config, get_active_backend, set_active_backend


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    starters = tmp_path / "starters"
    org_home = tmp_path / "org_home"
    starters.mkdir()
    org_home.mkdir()
    return Config(starters_dir=starters, org_home=org_home)


class TestGetActiveBackend:
    def test_returns_default_when_no_file(self, cfg: Config) -> None:
        assert get_active_backend(cfg) == "claude"

    def test_returns_custom_default(self, tmp_path: Path) -> None:
        cfg = Config(
            starters_dir=tmp_path / "s",
            org_home=tmp_path / "o",
            default_backend="cursor",
        )
        (tmp_path / "s").mkdir()
        (tmp_path / "o").mkdir()
        assert get_active_backend(cfg) == "cursor"

    def test_reads_from_settings(self, cfg: Config) -> None:
        (cfg.org_home / "settings.yaml").write_text("active_backend: copilot\n")
        assert get_active_backend(cfg) == "copilot"

    def test_migrates_legacy_dot_file(self, cfg: Config) -> None:
        """Old .active-backend file should migrate to settings.yaml."""
        (cfg.org_home / ".active-backend").write_text("copilot\n")
        assert get_active_backend(cfg) == "copilot"
        # Legacy file cleaned up
        assert not (cfg.org_home / ".active-backend").exists()
        # Value now in settings.yaml
        import yaml
        data = yaml.safe_load((cfg.org_home / "settings.yaml").read_text())
        assert data["active_backend"] == "copilot"


class TestSetActiveBackend:
    def test_writes_settings(self, cfg: Config) -> None:
        import yaml
        set_active_backend(cfg, "cursor")
        data = yaml.safe_load((cfg.org_home / "settings.yaml").read_text())
        assert data["active_backend"] == "cursor"

    def test_creates_org_home_if_missing(self, tmp_path: Path) -> None:
        import yaml
        org_home = tmp_path / "new_home"
        cfg = Config(starters_dir=tmp_path / "s", org_home=org_home)
        set_active_backend(cfg, "copilot")
        assert org_home.is_dir()
        data = yaml.safe_load((org_home / "settings.yaml").read_text())
        assert data["active_backend"] == "copilot"

    def test_overwrites_existing(self, cfg: Config) -> None:
        set_active_backend(cfg, "copilot")
        set_active_backend(cfg, "cursor")
        assert get_active_backend(cfg) == "cursor"
