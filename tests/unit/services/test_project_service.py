"""Tests for ProjectService."""

from __future__ import annotations

import pytest

from agentorg.config import Config
from agentorg.services.project_service import ProjectService


@pytest.fixture
def config(tmp_path):
    return Config(starters_dir=tmp_path / "starters", org_home=tmp_path / "org")


@pytest.fixture
def service(config):
    return ProjectService(config)


def test_create_project(service):
    p = service.create("my-api")
    assert p.id == "my-api"
    assert p.root.is_dir()
    assert (p.root / "context").is_dir()
    assert (p.root / "commands").is_dir()
    assert (p.root / "runbooks").is_dir()
    assert (p.root / "skills").is_dir()
    assert (p.root / "knowledge").is_dir()
    assert (p.root / "tasks").is_dir()
    # Starter files
    assert (p.root / "context" / "architecture.md").is_file()
    assert (p.root / "context" / "domain-glossary.md").is_file()
    assert (p.root / "commands" / "build-test-lint.md").is_file()
    assert (p.root / "runbooks" / "common-failures.md").is_file()
    assert (p.root / "knowledge" / "learnings.md").is_file()


def test_create_duplicate_raises(service):
    service.create("dup")
    with pytest.raises(ValueError, match="already exists"):
        service.create("dup")


def test_list_projects(service):
    assert service.list_projects() == []
    service.create("alpha")
    service.create("beta")
    projects = service.list_projects()
    assert [p.id for p in projects] == ["alpha", "beta"]


def test_get_existing(service):
    service.create("web-app")
    p = service.get("web-app")
    assert p is not None
    assert p.id == "web-app"


def test_get_nonexistent(service):
    assert service.get("nope") is None


def test_activate_and_get_active(service):
    service.create("my-proj")
    service.activate("my-proj")
    active = service.get_active()
    assert active is not None
    assert active.id == "my-proj"


def test_deactivate(service):
    service.create("tmp")
    service.activate("tmp")
    assert service.get_active() is not None
    service.deactivate()
    assert service.get_active() is None


def test_get_active_when_none(service):
    assert service.get_active() is None


def test_activate_nonexistent_raises(service):
    with pytest.raises(ValueError, match="not found"):
        service.activate("ghost")
