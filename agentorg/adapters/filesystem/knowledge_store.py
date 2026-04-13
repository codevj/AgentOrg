"""Filesystem-backed KnowledgeStore.

All knowledge lives at ~/.agent-org/knowledge/ — outside the repo.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from agentorg.config import Config
from agentorg.domain.knowledge import has_content
from agentorg.domain.models import Level


class FileKnowledgeStore:
    def __init__(self, config: Config) -> None:
        self._base = config.knowledge_dir

    # ── Persona knowledge ──

    def persona_learnings(self, persona_id: str) -> str | None:
        path = self._persona_learnings_path(persona_id)
        if path.is_file():
            return path.read_text()
        return None

    def persona_level(self, persona_id: str) -> Level:
        path = self._persona_level_path(persona_id)
        if path.is_file():
            value = path.read_text().strip()
            try:
                return Level(value)
            except ValueError:
                return Level.STARTER
        return Level.STARTER

    def set_persona_level(self, persona_id: str, level: Level) -> None:
        path = self._persona_level_path(persona_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(level.value)

    def append_persona_learnings(self, persona_id: str, content: str) -> None:
        self.init_persona(persona_id)
        path = self._persona_learnings_path(persona_id)
        with path.open("a") as f:
            f.write(content)

    def init_persona(self, persona_id: str) -> None:
        path = self._persona_learnings_path(persona_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(
                f"# Learnings: {persona_id}\n\n"
                "Accumulated knowledge from past runs. Updated automatically after reflection.\n\n"
                "## Run History\n\n"
                "_No runs yet. Learnings will appear here after the first team execution._\n\n"
                "## Patterns Observed\n\n"
                "_Patterns will be captured as the persona gains experience._\n"
            )
        level_path = self._persona_level_path(persona_id)
        if not level_path.exists():
            level_path.write_text(Level.STARTER.value)

    def persona_reflection_count(self, persona_id: str) -> int:
        """Count ``## Reflection:`` headers in the persona's learnings file."""
        path = self._persona_learnings_path(persona_id)
        if not path.is_file():
            return 0
        text = path.read_text()
        return len(re.findall(r"^## Reflection:", text, re.MULTILINE))

    def archive_persona_reflection(self, persona_id: str, content: str) -> None:
        """Write content to knowledge/personas/{id}/archive/{date}.md."""
        archive_dir = self._base / "personas" / persona_id / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        archive_path = archive_dir / f"{today}.md"
        # Append if there's already an archive for today
        with archive_path.open("a") as f:
            f.write(content)

    def condense_persona_learnings(
        self, persona_id: str, condensed: str, changelog: str
    ) -> None:
        """Replace learnings with condensed version, archive the old one, log the changelog."""
        learnings_path = self._persona_learnings_path(persona_id)

        # Archive current learnings
        if learnings_path.is_file():
            old_content = learnings_path.read_text()
            self.archive_persona_reflection(persona_id, old_content)

        # Replace with condensed version
        learnings_path.write_text(
            f"# Learnings: {persona_id}\n\n{condensed}\n"
        )

        # Append changelog
        changelog_path = self._base / "personas" / persona_id / "changelog.md"
        today = date.today().isoformat()
        with changelog_path.open("a") as f:
            f.write(f"\n## Condensation: {today}\n\n{changelog}\n")

    # ── Team knowledge ──

    def team_learnings(self, team_id: str) -> str | None:
        path = self._team_learnings_path(team_id)
        if path.is_file():
            return path.read_text()
        return None

    def team_level(self, team_id: str) -> Level:
        path = self._team_level_path(team_id)
        if path.is_file():
            value = path.read_text().strip()
            try:
                return Level(value)
            except ValueError:
                return Level.STARTER
        return Level.STARTER

    def set_team_level(self, team_id: str, level: Level) -> None:
        path = self._team_level_path(team_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(level.value)

    def append_team_learnings(self, team_id: str, content: str) -> None:
        self.init_team(team_id)
        path = self._team_learnings_path(team_id)
        with path.open("a") as f:
            f.write(content)

    def init_team(self, team_id: str) -> None:
        path = self._team_learnings_path(team_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(
                f"# Team Learnings: {team_id}\n\n"
                "How this team works together. Updated automatically after reflection.\n"
            )
        level_path = self._team_level_path(team_id)
        if not level_path.exists():
            level_path.write_text(Level.STARTER.value)

    # ── Org knowledge ──

    def org_learnings(self) -> str | None:
        path = self._org_learnings_path()
        if path.is_file():
            return path.read_text()
        return None

    def append_org_learnings(self, content: str) -> None:
        self.init_org()
        path = self._org_learnings_path()
        with path.open("a") as f:
            f.write(content)

    def init_org(self) -> None:
        path = self._org_learnings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(
                "# Org-Wide Learnings\n\n"
                "Cross-persona patterns and process improvements observed across runs.\n"
            )

    # ── Paths ──

    def _persona_learnings_path(self, persona_id: str) -> Path:
        return self._base / "personas" / persona_id / "learnings.md"

    def _persona_level_path(self, persona_id: str) -> Path:
        return self._base / "personas" / persona_id / ".level"

    def _team_learnings_path(self, team_id: str) -> Path:
        return self._base / "teams" / team_id / "learnings.md"

    def _team_level_path(self, team_id: str) -> Path:
        return self._base / "teams" / team_id / ".level"

    def _org_learnings_path(self) -> Path:
        return self._base / "org-learnings.md"
