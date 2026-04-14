"""Filesystem-backed RunStore.

Runs stored at ~/.agent-org/runs/ as markdown + budget files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agentorg.config import Config
from agentorg.domain.budget import BudgetState
from agentorg.domain.models import Run, RunMode, RunStatus


class FileRunStore:
    def __init__(self, config: Config) -> None:
        self._runs_dir = config.runs_dir

    def save(self, run: Run) -> None:
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        path = self._runs_dir / f"{run.id}.md"
        path.write_text(self._serialize_run(run))

    def list_recent(self, count: int = 10) -> list[Run]:
        if not self._runs_dir.is_dir():
            return []
        files = sorted(
            (f for f in self._runs_dir.iterdir() if f.suffix == ".md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        runs = []
        for f in files[:count]:
            run = self._parse_run_file(f)
            if run:
                runs.append(run)
        return runs

    def get(self, run_id: str) -> Run | None:
        path = self._runs_dir / f"{run_id}.md"
        if not path.is_file():
            return None
        return self._parse_run_file(path)

    def save_budget(self, run_id: str, budget: BudgetState) -> None:
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        path = self._runs_dir / f"{run_id}.budget"
        path.write_text(json.dumps(budget.to_dict()))

    def load_budget(self, run_id: str) -> BudgetState | None:
        path = self._runs_dir / f"{run_id}.budget"
        if not path.is_file():
            return None
        data = json.loads(path.read_text())
        return BudgetState.from_dict(data)

    @staticmethod
    def _serialize_run(run: Run) -> str:
        lines = [
            f"# Run: {run.id}",
            "",
            "## Task",
            "",
            run.task,
            "",
            "## Context",
            "",
            f"- **Date**: {run.date.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"- **Mode**: {run.mode.value}",
            f"- **Status**: {run.status.value}",
        ]
        if run.team_id:
            lines.append(f"- **Team**: {run.team_id}")
        if run.backend:
            lines.append(f"- **Backend**: {run.backend}")
        if run.org_name:
            lines.append(f"- **Org**: {run.org_name}")
        if run.project_id:
            lines.append(f"- **Project**: {run.project_id}")
        if run.workdir:
            lines.append(f"- **Workdir**: `{run.workdir}`")
        if run.reflection_mode:
            lines.append(f"- **Reflection mode**: {run.reflection_mode}")

        # Team composition and stages
        if run.roles:
            lines.extend(["", "## Team", "", f"Roles: {', '.join(run.roles)}"])
        if run.stages:
            lines.append("")
            lines.append("### Execution stages")
            lines.append("")
            for i, stage in enumerate(run.stages, 1):
                marker = " (parallel)" if len(stage) > 1 else ""
                lines.append(f"- Stage {i}{marker}: {', '.join(stage)}")

        # Budget
        if run.budget_summary:
            lines.extend(["", "## Budget", "", run.budget_summary])

        # Output
        if run.output:
            lines.extend(["", "## Output", "", run.output])

        return "\n".join(lines) + "\n"

    @staticmethod
    def _parse_run_file(path: Path) -> Run | None:
        """Best-effort parse of a run markdown file."""
        content = path.read_text()
        run_id = path.stem

        def _extract(key: str) -> str:
            for line in content.splitlines():
                if f"**{key}**:" in line:
                    return line.split(f"**{key}**:", 1)[1].strip()
            return ""

        mode_str = _extract("Mode")
        try:
            mode = RunMode(mode_str)
        except ValueError:
            mode = RunMode.TEAM

        status_str = _extract("Status")
        try:
            status = RunStatus(status_str)
        except ValueError:
            status = RunStatus.PENDING

        return Run(
            id=run_id,
            mode=mode,
            team_id=_extract("Team") or None,
            task=_extract("Task"),
            date=datetime.utcnow(),  # approximate — precise parsing not critical
            status=status,
            backend=_extract("Backend"),
            budget_summary=_extract("Budget"),
        )
