"""Integration tests for FileKnowledgeStore."""

from pathlib import Path

import pytest

from agentorg.adapters.filesystem.knowledge_store import FileKnowledgeStore
from agentorg.config import Config
from agentorg.domain.models import Level


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(starters_dir=tmp_path / "starters", org_home=tmp_path / "org_home")


@pytest.fixture
def store(config: Config) -> FileKnowledgeStore:
    return FileKnowledgeStore(config)


def test_init_persona_creates_files(store: FileKnowledgeStore):
    store.init_persona("developer")
    text = store.persona_learnings("developer")
    assert text is not None
    assert "Learnings: developer" in text
    assert store.persona_level("developer") == Level.STARTER


def test_append_persona_learnings(store: FileKnowledgeStore):
    store.init_persona("developer")
    store.append_persona_learnings("developer", "\n## Reflection: 2026-04-13\n\n- Learned X\n")
    text = store.persona_learnings("developer")
    assert text is not None
    assert "- Learned X" in text


def test_set_persona_level(store: FileKnowledgeStore):
    store.init_persona("developer")
    store.set_persona_level("developer", Level.PRACTICED)
    assert store.persona_level("developer") == Level.PRACTICED


def test_persona_level_default(store: FileKnowledgeStore):
    assert store.persona_level("nonexistent") == Level.STARTER


def test_init_team(store: FileKnowledgeStore):
    store.init_team("product-delivery")
    text = store.team_learnings("product-delivery")
    assert text is not None
    assert "product-delivery" in text


def test_append_team_learnings(store: FileKnowledgeStore):
    store.init_team("product-delivery")
    store.append_team_learnings("product-delivery", "\n- Team pattern\n")
    text = store.team_learnings("product-delivery")
    assert text is not None
    assert "- Team pattern" in text


def test_init_org(store: FileKnowledgeStore):
    store.init_org()
    text = store.org_learnings()
    assert text is not None
    assert "Org-Wide" in text


def test_append_org_learnings(store: FileKnowledgeStore):
    store.init_org()
    store.append_org_learnings("\n- Org pattern\n")
    text = store.org_learnings()
    assert text is not None
    assert "- Org pattern" in text


def test_no_learnings_returns_none(store: FileKnowledgeStore):
    assert store.persona_learnings("nonexistent") is None
    assert store.team_learnings("nonexistent") is None
    assert store.org_learnings() is None
