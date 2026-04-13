"""Filesystem-backed PersonaRepository.

Scans both starters (inside package) and user dir (~/.agent-org/personas/).
User personas take priority over starters with the same ID.
"""

from __future__ import annotations

from pathlib import Path

from agentorg.config import Config
from agentorg.domain.models import ItemSource, Persona
from agentorg.domain.persona_parser import parse_persona
from agentorg.domain.resolution import item_source, merge_id_lists

from .paths import scan_subdirs


class FilePersonaRepository:
    def __init__(self, config: Config) -> None:
        self._starter_dir = config.starter_personas_dir
        self._user_dir = config.user_personas_dir

    def get(self, persona_id: str) -> Persona | None:
        path, source = self._resolve(persona_id)
        if path is None:
            return None
        content = path.read_text()
        return parse_persona(persona_id, content, source=source)

    def list_all(self) -> list[Persona]:
        return [p for pid in self.list_ids() if (p := self.get(pid)) is not None]

    def list_ids(self) -> list[str]:
        user_ids = scan_subdirs(self._user_dir)
        starter_ids = scan_subdirs(self._starter_dir)
        return merge_id_lists(user_ids, starter_ids)

    def source(self, persona_id: str) -> ItemSource:
        return item_source(
            self._user_persona_file(persona_id).is_file(),
            self._starter_persona_file(persona_id).is_file(),
        )

    def exists(self, persona_id: str) -> bool:
        return self.source(persona_id) != ItemSource.NONE

    def save_to_user(self, persona: Persona) -> None:
        target = self._user_dir / persona.id
        target.mkdir(parents=True, exist_ok=True)
        (target / "persona.md").write_text(persona.raw_content)

    def save_to_repo(self, persona: Persona) -> None:
        target = self._starter_dir / persona.id
        target.mkdir(parents=True, exist_ok=True)
        (target / "persona.md").write_text(persona.raw_content)

    def _resolve(self, persona_id: str) -> tuple[Path | None, ItemSource]:
        user_file = self._user_persona_file(persona_id)
        if user_file.is_file():
            return user_file, ItemSource.USER
        starter_file = self._starter_persona_file(persona_id)
        if starter_file.is_file():
            return starter_file, ItemSource.REPO
        return None, ItemSource.NONE

    def _user_persona_file(self, persona_id: str) -> Path:
        return self._user_dir / persona_id / "persona.md"

    def _starter_persona_file(self, persona_id: str) -> Path:
        return self._starter_dir / persona_id / "persona.md"
