"""Integration tests for FileTeamRepository."""

from pathlib import Path

import pytest

from agentorg.adapters.filesystem.team_repo import FileTeamRepository
from agentorg.config import Config
from agentorg.domain.models import ItemSource


TEAM_YAML = """\
team_id: product-delivery
mode_default: team
personas:
  - architect
  - developer
governance_profile: quality_first
execution_profile: local_default
gates:
  reviewer_required: true
  tester_required: true
budget:
  max_calls: 10
  reflection: true
  interactions: 3
"""


@pytest.fixture
def config(tmp_path: Path) -> Config:
    starters = tmp_path / "starters"
    org_home = tmp_path / "org_home"
    (starters / "teams").mkdir(parents=True)
    (starters / "teams" / "product-delivery.yaml").write_text(TEAM_YAML)
    return Config(starters_dir=starters, org_home=org_home)


def test_get_starter_team(config: Config):
    repo = FileTeamRepository(config)
    t = repo.get("product-delivery")
    assert t is not None
    assert t.id == "product-delivery"
    assert t.persona_ids == ["architect", "developer"]
    assert t.source == ItemSource.REPO


def test_list_ids(config: Config):
    repo = FileTeamRepository(config)
    assert "product-delivery" in repo.list_ids()


def test_user_override(config: Config):
    user_teams = config.user_teams_dir
    user_teams.mkdir(parents=True)
    (user_teams / "product-delivery.yaml").write_text(
        TEAM_YAML.replace("quality_first", "speed_first")
    )
    repo = FileTeamRepository(config)
    t = repo.get("product-delivery")
    assert t is not None
    assert t.governance_profile == "speed_first"
    assert t.source == ItemSource.USER


def test_save_to_user(config: Config):
    repo = FileTeamRepository(config)
    t = repo.get("product-delivery")
    assert t is not None
    repo.save_to_user(t)
    assert repo.source("product-delivery") == ItemSource.USER
