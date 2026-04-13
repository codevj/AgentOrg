"""Parse SKILL.md content into a Skill domain model."""

from __future__ import annotations

import yaml

from agentorg.domain.models import ItemSource, Skill, SkillMetadata


def parse_skill(skill_id: str, content: str, source: ItemSource = ItemSource.REPO) -> Skill:
    """Parse a SKILL.md string (YAML frontmatter + markdown body) into a Skill model."""
    metadata, body = _split_frontmatter(content)
    return Skill(id=skill_id, metadata=metadata, body=body, source=source)


def _split_frontmatter(content: str) -> tuple[SkillMetadata, str]:
    """Split YAML frontmatter from markdown body.

    Expects content starting with --- ... --- followed by markdown.
    """
    lines = content.splitlines(keepends=True)

    if not lines or lines[0].strip() != "---":
        return _default_metadata(), content

    # Find closing ---
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return _default_metadata(), content

    frontmatter_text = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :]).strip()

    try:
        data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return _default_metadata(), content

    if not isinstance(data, dict):
        return _default_metadata(), content

    meta = data.get("metadata", {})
    if not isinstance(meta, dict):
        meta = {}

    return (
        SkillMetadata(
            name=data.get("name", ""),
            description=data.get("description", ""),
            author=meta.get("author", ""),
            version=str(meta.get("version", "1.0")),
            license=data.get("license", "Apache-2.0"),
        ),
        body,
    )


def _default_metadata() -> SkillMetadata:
    return SkillMetadata(name="", description="")
