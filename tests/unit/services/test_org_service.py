"""Tests for OrgService."""

from unittest.mock import MagicMock

from agentorg.domain.models import ItemSource, Level, Persona
from agentorg.services.org_service import OrgService


def test_list_personas():
    persona_repo = MagicMock()
    persona_repo.list_ids.return_value = ["architect", "developer"]
    persona_repo.get.side_effect = [
        Persona(id="architect", raw_content="", mission="Design systems.", skill_ids=["risk-assessment"]),
        Persona(id="developer", raw_content="", mission="Write code."),
    ]
    persona_repo.source.side_effect = [ItemSource.REPO, ItemSource.REPO]

    knowledge = MagicMock()
    knowledge.persona_level.return_value = Level.STARTER
    knowledge.persona_learnings.return_value = None

    service = OrgService(
        persona_repo=persona_repo,
        team_repo=MagicMock(),
        skill_repo=MagicMock(),
        knowledge_store=knowledge,
        run_store=MagicMock(),
    )

    views = service.list_personas()
    assert len(views) == 2
    assert views[0].id == "architect"
    assert views[0].skill_count == 1
    assert views[1].id == "developer"


def test_status():
    service = OrgService(
        persona_repo=MagicMock(list_ids=MagicMock(return_value=["a", "b"])),
        team_repo=MagicMock(list_ids=MagicMock(return_value=["t1"])),
        skill_repo=MagicMock(list_ids=MagicMock(return_value=["s1", "s2"])),
        knowledge_store=MagicMock(),
        run_store=MagicMock(list_recent=MagicMock(return_value=[])),
    )
    status = service.status()
    assert status.persona_count == 2
    assert status.team_count == 1
    assert status.skill_count == 2
