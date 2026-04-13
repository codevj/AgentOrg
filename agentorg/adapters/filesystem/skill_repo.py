"""Filesystem-backed SkillRepository.

Scans both starters and user dir. User skills take priority.
"""

from __future__ import annotations

from pathlib import Path

from agentorg.config import Config
from agentorg.domain.models import ItemSource, Skill
from agentorg.domain.resolution import item_source, merge_id_lists
from agentorg.domain.skill_parser import parse_skill

from .paths import scan_subdirs


class FileSkillRepository:
    def __init__(self, config: Config) -> None:
        self._starter_dir = config.starter_skills_dir
        self._user_dir = config.user_skills_dir

    def get(self, skill_id: str) -> Skill | None:
        path, source = self._resolve(skill_id)
        if path is None:
            return None
        content = path.read_text()
        return parse_skill(skill_id, content, source=source)

    def list_all(self) -> list[Skill]:
        return [s for sid in self.list_ids() if (s := self.get(sid)) is not None]

    def list_ids(self) -> list[str]:
        user_ids = scan_subdirs(self._user_dir)
        starter_ids = scan_subdirs(self._starter_dir)
        return merge_id_lists(user_ids, starter_ids)

    def source(self, skill_id: str) -> ItemSource:
        return item_source(
            self._user_skill_file(skill_id).is_file(),
            self._starter_skill_file(skill_id).is_file(),
        )

    def exists(self, skill_id: str) -> bool:
        return self.source(skill_id) != ItemSource.NONE

    def save_to_user(self, skill: Skill) -> None:
        target = self._user_dir / skill.id
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(self._serialize(skill))

    def save_to_repo(self, skill: Skill) -> None:
        target = self._starter_dir / skill.id
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(self._serialize(skill))

    def _resolve(self, skill_id: str) -> tuple[Path | None, ItemSource]:
        user_file = self._user_skill_file(skill_id)
        if user_file.is_file():
            return user_file, ItemSource.USER
        starter_file = self._starter_skill_file(skill_id)
        if starter_file.is_file():
            return starter_file, ItemSource.REPO
        return None, ItemSource.NONE

    def _user_skill_file(self, skill_id: str) -> Path:
        return self._user_dir / skill_id / "SKILL.md"

    def _starter_skill_file(self, skill_id: str) -> Path:
        return self._starter_dir / skill_id / "SKILL.md"

    @staticmethod
    def _serialize(skill: Skill) -> str:
        frontmatter = (
            f"---\n"
            f"name: {skill.metadata.name}\n"
            f"description: {skill.metadata.description}\n"
            f"license: {skill.metadata.license}\n"
            f"metadata:\n"
            f"  author: {skill.metadata.author}\n"
            f"  version: \"{skill.metadata.version}\"\n"
            f"---\n\n"
        )
        return frontmatter + skill.body
