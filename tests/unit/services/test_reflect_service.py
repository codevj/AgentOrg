"""Tests for ReflectService."""

from unittest.mock import MagicMock

from agentorg.domain.models import Level
from agentorg.services.reflect_service import ReflectService


REFLECTION_OUTPUT = """\
===LEARNING:developer===
- Always run tests before handoff
===END===

===TEAM_LEARNING:product-delivery===
- Handoffs improved with explicit file scope
===END===

===ORG_LEARNING===
- Vague tasks produce worse output
===END===

===LEVEL:developer=practiced===
"""


def test_write_back_persona_learnings():
    service = ReflectService(
        persona_repo=MagicMock(),
        knowledge_store=MagicMock(),
        run_store=MagicMock(),
        renderer=MagicMock(),
    )

    result = service.write_back(REFLECTION_OUTPUT)

    assert len(result.persona_learnings) == 1
    assert result.persona_learnings[0].persona_id == "developer"
    service._knowledge.append_persona_learnings.assert_called_once()
    call_args = service._knowledge.append_persona_learnings.call_args
    assert "developer" == call_args[0][0]
    assert "Always run tests" in call_args[0][1]


def test_write_back_team_learnings():
    service = ReflectService(
        persona_repo=MagicMock(),
        knowledge_store=MagicMock(),
        run_store=MagicMock(),
        renderer=MagicMock(),
    )

    result = service.write_back(REFLECTION_OUTPUT)

    assert len(result.team_learnings) == 1
    service._knowledge.append_team_learnings.assert_called_once()


def test_write_back_org_learnings():
    service = ReflectService(
        persona_repo=MagicMock(),
        knowledge_store=MagicMock(),
        run_store=MagicMock(),
        renderer=MagicMock(),
    )

    result = service.write_back(REFLECTION_OUTPUT)

    assert len(result.org_learnings) == 1
    service._knowledge.append_org_learnings.assert_called_once()


def test_write_back_levels():
    service = ReflectService(
        persona_repo=MagicMock(),
        knowledge_store=MagicMock(),
        run_store=MagicMock(),
        renderer=MagicMock(),
    )

    result = service.write_back(REFLECTION_OUTPUT)

    assert len(result.level_assessments) == 1
    service._knowledge.set_persona_level.assert_called_once_with("developer", Level.PRACTICED)
