"""Jinja2-based template renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2


class JinjaRenderer:
    """Renders .j2 templates from the templates directory.

    Supports dual-source resolution: if a ``user_dir`` is provided and exists,
    templates found there override those shipped with the package.
    """

    def __init__(
        self,
        templates_dir: Path | None = None,
        user_dir: Path | None = None,
    ) -> None:
        package_dir = templates_dir if templates_dir is not None else Path(__file__).parent / "templates"
        loaders: list[jinja2.BaseLoader] = []
        if user_dir is not None and Path(user_dir).is_dir():
            loaders.append(jinja2.FileSystemLoader(str(user_dir)))
        loaders.append(jinja2.FileSystemLoader(str(package_dir)))
        self._env = jinja2.Environment(
            loader=jinja2.ChoiceLoader(loaders) if len(loaders) > 1 else loaders[0],
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        template = self._env.get_template(template_name)
        return template.render(**context)
