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

    def test_reads_from_file(self, cfg: Config) -> None:
        (cfg.org_home / ".active-backend").write_text("copilot\n")
        assert get_active_backend(cfg) == "copilot"

    def test_ignores_empty_file(self, cfg: Config) -> None:
        (cfg.org_home / ".active-backend").write_text("  \n")
        assert get_active_backend(cfg) == "claude"


class TestSetActiveBackend:
    def test_writes_file(self, cfg: Config) -> None:
        set_active_backend(cfg, "cursor")
        content = (cfg.org_home / ".active-backend").read_text()
        assert content.strip() == "cursor"

    def test_creates_org_home_if_missing(self, tmp_path: Path) -> None:
        org_home = tmp_path / "new_home"
        cfg = Config(starters_dir=tmp_path / "s", org_home=org_home)
        set_active_backend(cfg, "copilot")
        assert org_home.is_dir()
        assert (org_home / ".active-backend").read_text().strip() == "copilot"

    def test_overwrites_existing(self, cfg: Config) -> None:
        set_active_backend(cfg, "copilot")
        set_active_backend(cfg, "cursor")
        assert get_active_backend(cfg) == "cursor"
