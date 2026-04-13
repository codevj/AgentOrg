"""Subprocess-based CLI executor."""

from __future__ import annotations

import shutil
import subprocess

from agentorg.ports.executor import CommandResult


class SubprocessExecutor:
    """Runs CLI commands via subprocess."""

    def run(self, command: str, input_text: str | None = None) -> CommandResult:
        result = subprocess.run(
            command,
            shell=True,
            input=input_text,
            capture_output=True,
            text=True,
        )
        return CommandResult(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def run_interactive(self, command: str) -> int:
        """Run a command interactively — stdin/stdout/stderr pass through to the terminal.

        Returns the exit code.
        """
        return subprocess.call(command, shell=True)

    def is_installed(self, cli_name: str) -> bool:
        return shutil.which(cli_name) is not None
