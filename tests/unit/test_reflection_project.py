"""Tests for project learning parsing and write-back."""

from pathlib import Path
from unittest.mock import MagicMock

from agentorg.domain.reflection import parse_reflection_output
from agentorg.services.reflect_service import ReflectService


REFLECTION_WITH_PROJECT = """\
===LEARNING:developer===
- Always run tests before handoff
===END===

===PROJECT_LEARNING:my-api===
- The auth module uses JWT tokens with 15-minute expiry
- Database migrations must be run with `alembic upgrade head`
===END===

===ORG_LEARNING===
- Vague tasks produce worse output
===END===

===LEVEL:developer=practiced===
"""


def test_parse_project_learning():
    result = parse_reflection_output(REFLECTION_WITH_PROJECT)
    assert len(result.project_learnings) == 1
    pl = result.project_learnings[0]
    assert pl.project_id == "my-api"
    assert "JWT tokens" in pl.content
    assert "alembic upgrade head" in pl.content


def test_parse_project_learning_empty_block():
    text = "===PROJECT_LEARNING:my-api===\n\n===END===\n"
    result = parse_reflection_output(text)
    assert result.project_learnings == []  # no bullets = skipped


def test_parse_no_project_learning():
    text = """\
===LEARNING:developer===
- Always run tests
===END===
"""
    result = parse_reflection_output(text)
    assert result.project_learnings == []


def test_parse_multiple_project_learnings():
    text = """\
===PROJECT_LEARNING:api===
- Use connection pooling
===END===

===PROJECT_LEARNING:frontend===
- Always lazy-load routes
===END===
"""
    result = parse_reflection_output(text)
    assert len(result.project_learnings) == 2
    assert result.project_learnings[0].project_id == "api"
    assert result.project_learnings[1].project_id == "frontend"


def test_write_back_project_learnings(tmp_path: Path):
    project_root = tmp_path / "my-api"
    (project_root / "knowledge").mkdir(parents=True)
    learnings_file = project_root / "knowledge" / "learnings.md"
    learnings_file.write_text("# Learnings\n")

    service = ReflectService(
        persona_repo=MagicMock(),
        knowledge_store=MagicMock(),
        run_store=MagicMock(),
        renderer=MagicMock(),
    )

    result = service.write_back(REFLECTION_WITH_PROJECT, project_root=project_root)

    assert len(result.project_learnings) == 1
    content = learnings_file.read_text()
    assert "JWT tokens" in content
    assert "alembic upgrade head" in content
    assert "Reflection:" in content


def test_write_back_project_learnings_no_project_root():
    """When no project_root, project learnings are parsed but not written."""
    service = ReflectService(
        persona_repo=MagicMock(),
        knowledge_store=MagicMock(),
        run_store=MagicMock(),
        renderer=MagicMock(),
    )

    result = service.write_back(REFLECTION_WITH_PROJECT)

    # Learnings are parsed
    assert len(result.project_learnings) == 1
    # But nothing crashes — write is simply skipped
