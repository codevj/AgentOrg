"""Tests for skill_parser — parse SKILL.md strings into Skill models."""

from agentorg.domain.skill_parser import parse_skill


SKILL_MD = """\
---
name: code-review
description: Review code for correctness, security, and maintainability.
license: Apache-2.0
metadata:
  author: vijayra
  version: "1.0"
---

# Code Review

## When to use this skill

When reviewing diffs, PRs, or implementation handoffs.

## Process

1. Check correctness
2. Check security
3. Check edge cases
"""


def test_parse_skill_id():
    s = parse_skill("code-review", SKILL_MD)
    assert s.id == "code-review"


def test_parse_metadata():
    s = parse_skill("code-review", SKILL_MD)
    assert s.metadata.name == "code-review"
    assert s.metadata.description == "Review code for correctness, security, and maintainability."
    assert s.metadata.author == "vijayra"
    assert s.metadata.version == "1.0"
    assert s.metadata.license == "Apache-2.0"


def test_parse_body():
    s = parse_skill("code-review", SKILL_MD)
    assert "# Code Review" in s.body
    assert "Check correctness" in s.body


def test_parse_no_frontmatter():
    content = "# Just markdown\n\nSome content."
    s = parse_skill("plain", content)
    assert s.body == content
    assert s.metadata.name == ""


def test_parse_empty():
    s = parse_skill("empty", "")
    assert s.body == ""
