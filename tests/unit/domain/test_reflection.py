"""Tests for reflection output parsing."""

from agentorg.domain.reflection import parse_reflection_output
from agentorg.domain.models import Level


REFLECTION_OUTPUT = """\
Here is my analysis of the run:

===LEARNING:architect===
- Always include rollback plan in design handoffs
- Specify file boundaries explicitly for the developer
===END===

===LEARNING:developer===
- Validate inputs before processing, reviewer flagged this twice
===END===

===TEAM_LEARNING:product-delivery===
- Architect-developer handoff works better when file scope is explicit
- Review loops averaged 1.2 iterations
===END===

===ORG_LEARNING===
- Cross-role: handoff quality degrades when task scope is vague
===END===

===LEVEL:architect=practiced===
===LEVEL:developer=practiced===
===LEVEL:tester=starter===
"""


def test_parse_persona_learnings():
    result = parse_reflection_output(REFLECTION_OUTPUT)
    assert len(result.persona_learnings) == 2
    arch = result.persona_learnings[0]
    assert arch.persona_id == "architect"
    assert "rollback plan" in arch.content
    assert "file boundaries" in arch.content
    dev = result.persona_learnings[1]
    assert dev.persona_id == "developer"
    assert "Validate inputs" in dev.content


def test_parse_team_learnings():
    result = parse_reflection_output(REFLECTION_OUTPUT)
    assert len(result.team_learnings) == 1
    tl = result.team_learnings[0]
    assert tl.team_id == "product-delivery"
    assert "file scope" in tl.content


def test_parse_org_learnings():
    result = parse_reflection_output(REFLECTION_OUTPUT)
    assert len(result.org_learnings) == 1
    assert "scope is vague" in result.org_learnings[0].content


def test_parse_levels():
    result = parse_reflection_output(REFLECTION_OUTPUT)
    assert len(result.level_assessments) == 3
    levels = {la.persona_id: la.level for la in result.level_assessments}
    assert levels["architect"] == Level.PRACTICED
    assert levels["developer"] == Level.PRACTICED
    assert levels["tester"] == Level.STARTER


def test_empty_input():
    result = parse_reflection_output("")
    assert result.persona_learnings == []
    assert result.team_learnings == []
    assert result.org_learnings == []
    assert result.level_assessments == []


def test_skip_empty_blocks():
    text = "===LEARNING:architect===\n\n===END===\n"
    result = parse_reflection_output(text)
    assert result.persona_learnings == []  # no bullets = skipped


def test_invalid_level_ignored():
    text = "===LEVEL:architect=invalid===\n"
    result = parse_reflection_output(text)
    assert result.level_assessments == []
