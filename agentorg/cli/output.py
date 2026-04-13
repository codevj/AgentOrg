"""Console output helpers — colors, formatting."""

from __future__ import annotations

import click

from agentorg.domain.models import ItemSource, Level


def level_color(level: Level) -> str:
    return {
        Level.EXPERT: "magenta",
        Level.EXPERIENCED: "cyan",
        Level.PRACTICED: "green",
        Level.STARTER: "white",
    }.get(level, "white")


def source_tag(source: ItemSource) -> str:
    if source == ItemSource.USER:
        return click.style(" *", fg="cyan")
    return ""


def dim(text: str) -> str:
    return click.style(text, dim=True)


def bold(text: str) -> str:
    return click.style(text, bold=True)


def success(text: str) -> str:
    return click.style(text, fg="green")


def warn(text: str) -> str:
    return click.style(text, fg="yellow")


def error(text: str) -> str:
    return click.style(text, fg="red")
