"""Parse persona.md content into a Persona domain model."""

from __future__ import annotations

import re

from agentorg.domain.models import ItemSource, Persona


def parse_persona(persona_id: str, content: str, source: ItemSource = ItemSource.REPO) -> Persona:
    """Parse a persona.md string into a Persona model.

    Extracts mission, required inputs, exit criteria, non-goals, and skill references
    from markdown section headers.
    """
    return Persona(
        id=persona_id,
        raw_content=content,
        mission=_extract_mission(content),
        required_inputs=_extract_list_section(content, "Required inputs"),
        exit_criteria=_extract_list_section(content, "Exit criteria"),
        non_goals=_extract_list_section(content, "Non-goals"),
        skill_ids=_extract_list_section(content, "Skills"),
        source=source,
    )


def _extract_mission(content: str) -> str:
    """Extract the first non-empty line after ## Mission."""
    match = re.search(r"^##\s+Mission\s*\n+(.+)", content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_list_section(content: str, section_name: str) -> list[str]:
    """Extract bullet items from a markdown section (## Section Name).

    Stops at the next ## heading or end of content.
    """
    pattern = rf"^##\s+{re.escape(section_name)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return []

    items = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items
