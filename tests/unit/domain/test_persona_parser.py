"""Tests for persona_parser — parse persona.md strings into Persona models."""

from agentorg.domain.persona_parser import parse_persona
from agentorg.domain.models import ItemSource


ARCHITECT_MD = """\
# Persona: Architect

## Mission

Produce a minimal, safe implementation design.

## Required inputs

- PM handoff
- Existing code constraints
- Build/test/lint commands

## Output format

Must follow the handoff schema.

## Exit criteria

- File-level design plan
- Risk and rollback notes
- Clear boundaries for what developer may change

## Non-goals

- Writing final production code
- Expanding scope beyond PM-approved requirements

## Skills

- risk-assessment
"""


def test_parse_mission():
    p = parse_persona("architect", ARCHITECT_MD)
    assert p.mission == "Produce a minimal, safe implementation design."


def test_parse_id():
    p = parse_persona("architect", ARCHITECT_MD)
    assert p.id == "architect"


def test_parse_required_inputs():
    p = parse_persona("architect", ARCHITECT_MD)
    assert p.required_inputs == [
        "PM handoff",
        "Existing code constraints",
        "Build/test/lint commands",
    ]


def test_parse_exit_criteria():
    p = parse_persona("architect", ARCHITECT_MD)
    assert p.exit_criteria == [
        "File-level design plan",
        "Risk and rollback notes",
        "Clear boundaries for what developer may change",
    ]


def test_parse_non_goals():
    p = parse_persona("architect", ARCHITECT_MD)
    assert p.non_goals == [
        "Writing final production code",
        "Expanding scope beyond PM-approved requirements",
    ]


def test_parse_skills():
    p = parse_persona("architect", ARCHITECT_MD)
    assert p.skill_ids == ["risk-assessment"]


def test_parse_source():
    p = parse_persona("architect", ARCHITECT_MD, source=ItemSource.USER)
    assert p.source == ItemSource.USER


def test_parse_raw_content_preserved():
    p = parse_persona("architect", ARCHITECT_MD)
    assert p.raw_content == ARCHITECT_MD


def test_parse_minimal_persona():
    content = "# Persona: Minimal\n\n## Mission\n\nDo something.\n"
    p = parse_persona("minimal", content)
    assert p.mission == "Do something."
    assert p.required_inputs == []
    assert p.skill_ids == []


def test_parse_empty_content():
    p = parse_persona("empty", "")
    assert p.mission == ""
    assert p.required_inputs == []
