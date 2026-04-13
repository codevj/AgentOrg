"""Knowledge content helpers — filtering, detection, formatting."""

from __future__ import annotations

import re


_PLACEHOLDER_PATTERNS = [
    r"^_No runs yet",
    r"^_Patterns will",
    r"^_When ",
    r"^_Tracks ",
    r"^_Recurring ",
    r"^How this team works",
    r"^Cross-persona patterns",
    r"^Accumulated knowledge from past runs",
]


def has_content(text: str | None) -> bool:
    """Check if a knowledge text has real content (not just placeholders)."""
    if not text:
        return False
    return bool(re.search(r"^-\s|\d+\.", text, re.MULTILINE))


def strip_placeholders(text: str) -> str:
    """Remove heading lines, placeholder lines, and blank lines from knowledge content."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if any(re.match(p, stripped) for p in _PLACEHOLDER_PATTERNS):
            continue
        lines.append(line)
    return "\n".join(lines)
