"""Tests for team_parser — parse team YAML strings into Team models."""

import pytest

from agentorg.domain.team_parser import parse_team
from agentorg.domain.models import RunMode


PRODUCT_DELIVERY_YAML = """\
team_id: product-delivery
mode_default: team
personas:
  - program-manager
  - architect
  - developer
  - tester
  - code-reviewer
governance_profile: quality_first
execution_profile: local_default
gates:
  reviewer_required: true
  tester_required: true
budget:
  max_calls: 12
  reflection: true
  interactions: 3
"""


def test_parse_team_id():
    t = parse_team(PRODUCT_DELIVERY_YAML)
    assert t.id == "product-delivery"


def test_parse_personas_ordered():
    t = parse_team(PRODUCT_DELIVERY_YAML)
    assert t.persona_ids == [
        "program-manager", "architect", "developer", "tester", "code-reviewer"
    ]


def test_parse_governance():
    t = parse_team(PRODUCT_DELIVERY_YAML)
    assert t.governance_profile == "quality_first"


def test_parse_gates():
    t = parse_team(PRODUCT_DELIVERY_YAML)
    assert t.gates.reviewer_required is True
    assert t.gates.tester_required is True


def test_parse_budget():
    t = parse_team(PRODUCT_DELIVERY_YAML)
    assert t.budget.max_calls == 12
    assert t.budget.reflection is True
    assert t.budget.interactions == 3


def test_parse_mode():
    t = parse_team(PRODUCT_DELIVERY_YAML)
    assert t.mode_default == RunMode.TEAM


def test_parse_defaults_when_missing():
    minimal = "team_id: minimal\npersonas:\n  - developer\n"
    t = parse_team(minimal)
    assert t.budget.max_calls == 15
    assert t.gates.reviewer_required is True
    assert t.governance_profile == "quality_first"


def test_parse_missing_team_id_raises():
    with pytest.raises(ValueError, match="team_id"):
        parse_team("personas:\n  - dev\n")


def test_parse_invalid_yaml_raises():
    with pytest.raises(ValueError):
        parse_team("not: [valid: yaml: {{")


# ── Graph format tests ──

GRAPH_YAML = """\
team_id: product-delivery
roles:
  - id: program-manager
  - id: architect
    depends_on: [program-manager]
  - id: developer
    depends_on: [architect]
  - id: tester
    depends_on: [developer]
  - id: code-reviewer
    depends_on: [developer]
gates:
  reviewer_required: true
"""


def test_parse_graph_format_persona_ids():
    t = parse_team(GRAPH_YAML)
    assert t.persona_ids == [
        "program-manager", "architect", "developer", "tester", "code-reviewer"
    ]


def test_parse_graph_format_role_specs():
    t = parse_team(GRAPH_YAML)
    assert len(t.role_specs) == 5
    assert t.role_specs[0].id == "program-manager"
    assert t.role_specs[0].depends_on == []
    assert t.role_specs[1].id == "architect"
    assert t.role_specs[1].depends_on == ["program-manager"]
    assert t.role_specs[3].id == "tester"
    assert t.role_specs[3].depends_on == ["developer"]
    assert t.role_specs[4].id == "code-reviewer"
    assert t.role_specs[4].depends_on == ["developer"]


def test_execution_stages_parallel():
    t = parse_team(GRAPH_YAML)
    stages = t.execution_stages()
    # Stage 1: PM (no deps)
    # Stage 2: architect (depends on PM)
    # Stage 3: developer (depends on architect)
    # Stage 4: tester + code-reviewer (both depend on developer — parallel!)
    assert stages == [
        ["program-manager"],
        ["architect"],
        ["developer"],
        ["code-reviewer", "tester"],  # sorted alphabetically
    ]


def test_execution_stages_flat_format_is_sequential():
    """Flat persona list produces one-per-stage (sequential)."""
    t = parse_team(PRODUCT_DELIVERY_YAML)
    stages = t.execution_stages()
    assert stages == [
        ["program-manager"],
        ["architect"],
        ["developer"],
        ["tester"],
        ["code-reviewer"],
    ]


def test_parse_graph_diamond_dependency():
    """Diamond: A → B, A → C, B+C → D."""
    diamond = """\
team_id: diamond
roles:
  - id: a
  - id: b
    depends_on: [a]
  - id: c
    depends_on: [a]
  - id: d
    depends_on: [b, c]
"""
    t = parse_team(diamond)
    stages = t.execution_stages()
    assert stages == [["a"], ["b", "c"], ["d"]]
