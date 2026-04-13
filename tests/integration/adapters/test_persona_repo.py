"""Integration tests for FilePersonaRepository."""

from pathlib import Path

import pytest

from agentorg.adapters.filesystem.persona_repo import FilePersonaRepository
from agentorg.config import Config
from agentorg.domain.models import ItemSource


@pytest.fixture
def config(tmp_path: Path) -> Config:
    starters = tmp_path / "starters"
    org_home = tmp_path / "org_home"
    # Create a starter persona
    (starters / "personas" / "architect").mkdir(parents=True)
    (starters / "personas" / "architect" / "persona.md").write_text(
        "# Persona: Architect\n\n## Mission\n\nDesign systems.\n"
    )
    (starters / "personas" / "developer").mkdir(parents=True)
    (starters / "personas" / "developer" / "persona.md").write_text(
        "# Persona: Developer\n\n## Mission\n\nWrite code.\n"
    )
    return Config(starters_dir=starters, org_home=org_home)


def test_list_ids_starters_only(config: Config):
    repo = FilePersonaRepository(config)
    ids = repo.list_ids()
    assert "architect" in ids
    assert "developer" in ids


def test_get_starter_persona(config: Config):
    repo = FilePersonaRepository(config)
    p = repo.get("architect")
    assert p is not None
    assert p.mission == "Design systems."
    assert p.source == ItemSource.REPO


def test_get_nonexistent(config: Config):
    repo = FilePersonaRepository(config)
    assert repo.get("nonexistent") is None


def test_user_overrides_starter(config: Config):
    # Create user persona with same ID
    user_dir = config.user_personas_dir / "architect"
    user_dir.mkdir(parents=True)
    (user_dir / "persona.md").write_text(
        "# Persona: Architect\n\n## Mission\n\nDesign better systems.\n"
    )
    repo = FilePersonaRepository(config)
    p = repo.get("architect")
    assert p is not None
    assert p.mission == "Design better systems."
    assert p.source == ItemSource.USER


def test_user_only_persona(config: Config):
    user_dir = config.user_personas_dir / "custom-role"
    user_dir.mkdir(parents=True)
    (user_dir / "persona.md").write_text(
        "# Persona: Custom\n\n## Mission\n\nDo custom things.\n"
    )
    repo = FilePersonaRepository(config)
    p = repo.get("custom-role")
    assert p is not None
    assert p.source == ItemSource.USER
    # Should appear in list
    assert "custom-role" in repo.list_ids()


def test_list_ids_merge(config: Config):
    user_dir = config.user_personas_dir / "custom-role"
    user_dir.mkdir(parents=True)
    (user_dir / "persona.md").write_text("# Persona\n\n## Mission\n\nX.\n")
    repo = FilePersonaRepository(config)
    ids = repo.list_ids()
    # User IDs first, then starters
    assert ids[0] == "custom-role"
    assert "architect" in ids
    assert "developer" in ids


def test_source(config: Config):
    repo = FilePersonaRepository(config)
    assert repo.source("architect") == ItemSource.REPO
    assert repo.source("nonexistent") == ItemSource.NONE


def test_save_to_user(config: Config):
    repo = FilePersonaRepository(config)
    p = repo.get("architect")
    assert p is not None
    repo.save_to_user(p)
    # Now it should resolve from user dir
    assert repo.source("architect") == ItemSource.USER


def test_exists(config: Config):
    repo = FilePersonaRepository(config)
    assert repo.exists("architect") is True
    assert repo.exists("nonexistent") is False
