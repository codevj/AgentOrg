"""Backend protocol — sync org to native agent formats and execute tasks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class BackendInfo:
    """Metadata about a backend."""

    name: str
    cli: str
    installed: bool
    description: str
    agent_dir: str


class Backend(Protocol):
    """Port for AI tool backends (Claude, Copilot, Cursor, etc.)."""

    def info(self) -> BackendInfo: ...

    def sync(self, team_id: str | None = None, repo_root: Path | None = None) -> int:
        """Export org to native agent format. Returns number of agents synced.

        If repo_root is provided, agents are written there instead of the default location.
        """
        ...

    def prompt(self, text: str) -> str:
        """Send a prompt to the backend CLI and return the response. No sync, no team."""
        ...

    def execute(self, team_id: str, task: str, run_id: str) -> str:
        """Sync agents and execute a task via the backend's agent orchestration. Returns output."""
        ...
