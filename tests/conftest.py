"""Shared test fixtures."""

import pytest

from agentorg.config import Config
from pathlib import Path


@pytest.fixture
def tmp_config(tmp_path: Path) -> Config:
    """Config pointing to temp directories for testing."""
    starters = tmp_path / "starters"
    org_home = tmp_path / "org_home"
    starters.mkdir()
    org_home.mkdir()
    return Config(starters_dir=starters, org_home=org_home)
