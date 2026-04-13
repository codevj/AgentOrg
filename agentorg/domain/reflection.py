"""Reflection output parsing — extract structured learnings from LLM response.

The reflection LLM outputs delimited blocks:
  ===LEARNING:<role-id>===
  - bullet points
  ===END===

  ===TEAM_LEARNING:<team-id>===
  - bullet points
  ===END===

  ===ORG_LEARNING===
  - bullet points
  ===END===

  ===LEVEL:<role-id>=<starter|practiced|experienced|expert>===

This module parses that output into domain models. Zero I/O.
"""

from __future__ import annotations

import re

from agentorg.domain.models import (
    Level,
    LevelAssessment,
    OrgLearning,
    PersonaLearning,
    ProjectLearning,
    ReflectionResult,
    TeamLearning,
)


def parse_reflection_output(text: str) -> ReflectionResult:
    """Parse delimited reflection output into structured learnings."""
    persona_learnings = _extract_blocks(text, r"===LEARNING:([a-zA-Z0-9_-]+)===")
    team_learnings = _extract_blocks(text, r"===TEAM_LEARNING:([a-zA-Z0-9_-]+)===")
    project_learnings = _extract_blocks(text, r"===PROJECT_LEARNING:([a-zA-Z0-9_-]+)===")
    org_learnings = _extract_org_blocks(text)
    level_assessments = _extract_levels(text)

    return ReflectionResult(
        persona_learnings=[
            PersonaLearning(persona_id=pid, content=content)
            for pid, content in persona_learnings
            if _has_bullets(content)
        ],
        team_learnings=[
            TeamLearning(team_id=tid, content=content)
            for tid, content in team_learnings
            if _has_bullets(content)
        ],
        org_learnings=[
            OrgLearning(content=content)
            for content in org_learnings
            if _has_bullets(content)
        ],
        level_assessments=level_assessments,
        project_learnings=[
            ProjectLearning(project_id=pid, content=content)
            for pid, content in project_learnings
            if _has_bullets(content)
        ],
    )


def _extract_blocks(text: str, start_pattern: str) -> list[tuple[str, str]]:
    """Extract ID + content for blocks matching start_pattern ... ===END===."""
    results = []
    lines = text.splitlines()
    current_id: str | None = None
    content_lines: list[str] = []

    for line in lines:
        # Check for start
        match = re.match(start_pattern, line.strip())
        if match:
            current_id = match.group(1)
            content_lines = []
            continue

        # Check for end
        if line.strip() == "===END===" and current_id is not None:
            results.append((current_id, "\n".join(content_lines)))
            current_id = None
            content_lines = []
            continue

        # Accumulate
        if current_id is not None:
            content_lines.append(line)

    return results


def _extract_org_blocks(text: str) -> list[str]:
    """Extract org learning blocks (no ID)."""
    results = []
    lines = text.splitlines()
    in_block = False
    content_lines: list[str] = []

    for line in lines:
        if line.strip() == "===ORG_LEARNING===":
            in_block = True
            content_lines = []
            continue
        if line.strip() == "===END===" and in_block:
            results.append("\n".join(content_lines))
            in_block = False
            content_lines = []
            continue
        if in_block:
            content_lines.append(line)

    return results


def _extract_levels(text: str) -> list[LevelAssessment]:
    """Extract ===LEVEL:<role-id>=<level>=== lines."""
    results = []
    for line in text.splitlines():
        match = re.match(r"===LEVEL:([a-zA-Z0-9_-]+)=([a-z]+)===", line.strip())
        if match:
            role_id = match.group(1)
            level_str = match.group(2)
            try:
                level = Level(level_str)
                results.append(LevelAssessment(persona_id=role_id, level=level))
            except ValueError:
                pass  # skip invalid levels
    return results


def _has_bullets(content: str) -> bool:
    """Check if content has actual bullet points (not just whitespace)."""
    return bool(re.search(r"^\s*-\s", content, re.MULTILINE))
