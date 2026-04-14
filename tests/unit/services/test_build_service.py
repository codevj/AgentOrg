"""Tests for BuildService."""

from unittest.mock import MagicMock

import pytest

from agentorg.domain.models import Budget, Gates, ItemSource, Persona, RunMode, Team
from agentorg.services.build_service import BuildService


@pytest.fixture
def service():
    return BuildService(
        persona_repo=MagicMock(),
        team_repo=MagicMock(),
        skill_repo=MagicMock(),
        knowledge_store=MagicMock(),
    )


def test_hire_creates_persona(service: BuildService):
    service._personas.exists.return_value = False
    p = service.hire("sales-rep")
    assert p.id == "sales-rep"
    assert p.source == ItemSource.USER
    service._personas.save_to_user.assert_called_once()
    service._knowledge.init_persona.assert_called_once_with("sales-rep")


def test_hire_duplicate_raises(service: BuildService):
    service._personas.exists.return_value = True
    with pytest.raises(ValueError, match="already exists"):
        service.hire("existing")


def test_create_team(service: BuildService):
    service._teams.exists.return_value = False
    t = service.create_team("my-team")
    assert t.id == "my-team"
    assert t.source == ItemSource.USER
    service._teams.save_to_user.assert_called_once()
    service._knowledge.init_team.assert_called_once_with("my-team")


def test_adopt_persona(service: BuildService):
    service._personas.source.return_value = ItemSource.REPO
    service._personas.get.return_value = Persona(
        id="architect", raw_content="# test", mission="Design", source=ItemSource.REPO
    )
    adopted = service.adopt_persona("architect")
    assert adopted.source == ItemSource.USER
    service._personas.save_to_user.assert_called_once()


def test_adopt_already_user_raises(service: BuildService):
    service._personas.source.return_value = ItemSource.USER
    with pytest.raises(ValueError, match="Already in your org"):
        service.adopt_persona("architect")


def test_adopt_persona_if_missing_returns_false_when_user(service: BuildService):
    service._personas.source.return_value = ItemSource.USER
    assert service.adopt_persona_if_missing("architect") is False
    service._personas.save_to_user.assert_not_called()


def test_adopt_persona_if_missing_copies_when_repo(service: BuildService):
    service._personas.source.return_value = ItemSource.REPO
    service._personas.get.return_value = Persona(
        id="architect", raw_content="# test", mission="Design", source=ItemSource.REPO
    )
    assert service.adopt_persona_if_missing("architect") is True
    service._personas.save_to_user.assert_called_once()
    service._knowledge.init_persona.assert_called_once_with("architect")


def test_adopt_persona_if_missing_returns_false_when_not_found(service: BuildService):
    service._personas.source.return_value = ItemSource.NONE
    service._personas.get.return_value = None
    assert service.adopt_persona_if_missing("ghost") is False
    service._personas.save_to_user.assert_not_called()


def test_adopt_team_if_missing_returns_false_when_user(service: BuildService):
    service._teams.source.return_value = ItemSource.USER
    assert service.adopt_team_if_missing("product-delivery") is False
    service._teams.save_to_user.assert_not_called()


def test_adopt_team_if_missing_copies_when_repo(service: BuildService):
    service._teams.source.return_value = ItemSource.REPO
    service._teams.get.return_value = Team(
        id="product-delivery",
        mode_default=RunMode.TEAM,
        persona_ids=["architect"],
        governance_profile="quality_first",
        execution_profile="local_default",
        gates=Gates(),
        budget=Budget(),
        source=ItemSource.REPO,
    )
    assert service.adopt_team_if_missing("product-delivery") is True
    service._teams.save_to_user.assert_called_once()
    service._knowledge.init_team.assert_called_once_with("product-delivery")


def test_contribute_persona(service: BuildService):
    service._personas.source.return_value = ItemSource.USER
    service._personas.get.return_value = Persona(
        id="custom", raw_content="# test", mission="X", source=ItemSource.USER
    )
    service.contribute_persona("custom")
    service._personas.save_to_repo.assert_called_once()


def test_contribute_not_user_raises(service: BuildService):
    service._personas.source.return_value = ItemSource.REPO
    with pytest.raises(ValueError, match="Not in your org"):
        service.contribute_persona("starter-only")
