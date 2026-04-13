"""CLI executor protocol — run shell commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    """Result of a CLI command execution."""

    stdout: str
    stderr: str
    returncode: int

    @property
    def success(self) -> bool:
        return self.returncode == 0


class CLIExecutor(Protocol):
    """Port for executing shell commands (subprocess wrapper)."""

    def run(self, command: str, input_text: str | None = None) -> CommandResult: ...

    def is_installed(self, cli_name: str) -> bool: ...
