"""Filesystem-backed TeamRepository.

Scans both starters and user dir. User teams take priority.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agentorg.config import Config
from agentorg.domain.models import ItemSource, Team
from agentorg.domain.resolution import item_source, merge_id_lists
from agentorg.domain.team_parser import parse_team

from .paths import scan_yaml_files


class FileTeamRepository:
    def __init__(self, config: Config) -> None:
        self._starter_dir = config.starter_teams_dir
        self._user_dir = config.user_teams_dir

    def get(self, team_id: str) -> Team | None:
        path, source = self._resolve(team_id)
        if path is None:
            return None
        content = path.read_text()
        team = parse_team(content, source=source)
        return team

    def list_all(self) -> list[Team]:
        return [t for tid in self.list_ids() if (t := self.get(tid)) is not None]

    def list_ids(self) -> list[str]:
        user_ids = scan_yaml_files(self._user_dir)
        starter_ids = scan_yaml_files(self._starter_dir)
        return merge_id_lists(user_ids, starter_ids)

    def source(self, team_id: str) -> ItemSource:
        return item_source(
            self._user_team_file(team_id).is_file(),
            self._starter_team_file(team_id).is_file(),
        )

    def exists(self, team_id: str) -> bool:
        return self.source(team_id) != ItemSource.NONE

    def save_to_user(self, team: Team) -> None:
        self._user_dir.mkdir(parents=True, exist_ok=True)
        path = self._user_team_file(team.id)
        path.write_text(self._serialize(team))

    def save_to_repo(self, team: Team) -> None:
        self._starter_dir.mkdir(parents=True, exist_ok=True)
        path = self._starter_team_file(team.id)
        path.write_text(self._serialize(team))

    def _resolve(self, team_id: str) -> tuple[Path | None, ItemSource]:
        user_file = self._user_team_file(team_id)
        if user_file.is_file():
            return user_file, ItemSource.USER
        starter_file = self._starter_team_file(team_id)
        if starter_file.is_file():
            return starter_file, ItemSource.REPO
        return None, ItemSource.NONE

    def _user_team_file(self, team_id: str) -> Path:
        return self._user_dir / f"{team_id}.yaml"

    def _starter_team_file(self, team_id: str) -> Path:
        return self._starter_dir / f"{team_id}.yaml"

    @staticmethod
    def _serialize(team: Team) -> str:
        data = {
            "team_id": team.id,
            "mode_default": team.mode_default.value,
        }
        # Prefer the graph format (roles: with depends_on) to preserve
        # parallelism. Fall back to flat personas: when no dependencies.
        has_deps = any(rs.depends_on for rs in team.role_specs)
        if team.role_specs and has_deps:
            roles_data = []
            for rs in team.role_specs:
                entry: dict = {"id": rs.id}
                if rs.depends_on:
                    entry["depends_on"] = list(rs.depends_on)
                roles_data.append(entry)
            data["roles"] = roles_data
        else:
            data["personas"] = team.persona_ids

        data.update({
            "governance_profile": team.governance_profile,
            "execution_profile": team.execution_profile,
            "gates": {
                "reviewer_required": team.gates.reviewer_required,
                "tester_required": team.gates.tester_required,
            },
            "budget": {
                "max_calls": team.budget.max_calls,
                "reflection": team.budget.reflection,
                "interactions": team.budget.interactions,
            },
        })
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
