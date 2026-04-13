"""Template renderer protocol."""

from __future__ import annotations

from typing import Any, Protocol


class TemplateRenderer(Protocol):
    """Port for rendering Jinja2 (or other) templates."""

    def render(self, template_name: str, context: dict[str, Any]) -> str: ...
