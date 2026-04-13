"""Org service — status, list, inspect, history."""

from __future__ import annotations

from dataclasses import dataclass

from agentorg.domain.knowledge import has_content, strip_placeholders
from agentorg.domain.models import ItemSource, Level, Persona, Team
from agentorg.ports.knowledge_store import KnowledgeStore
from agentorg.ports.repository import PersonaRepository, SkillRepository, TeamRepository
from agentorg.ports.run_store import RunStore


@dataclass
class PersonaView:
    """Presentation model for a persona in listings."""

    id: str
    mission: str
    level: Level
    skill_count: int
    source: ItemSource
    has_knowledge: bool


@dataclass
class TeamView:
    """Presentation model for a team in listings."""

    id: str
    governance_profile: str
    persona_ids: list[str]
    source: ItemSource


@dataclass
class OrgStatus:
    """Summary of the org."""

    persona_count: int
    team_count: int
    skill_count: int
    run_count: int


class OrgService:
    def __init__(
        self,
        persona_repo: PersonaRepository,
        team_repo: TeamRepository,
        skill_repo: SkillRepository,
        knowledge_store: KnowledgeStore,
        run_store: RunStore,
    ) -> None:
        self._personas = persona_repo
        self._teams = team_repo
        self._skills = skill_repo
        self._knowledge = knowledge_store
        self._runs = run_store

    def status(self) -> OrgStatus:
        return OrgStatus(
            persona_count=len(self._personas.list_ids()),
            team_count=len(self._teams.list_ids()),
            skill_count=len(self._skills.list_ids()),
            run_count=len(self._runs.list_recent(count=9999)),
        )

    def list_personas(self) -> list[PersonaView]:
        views = []
        for pid in self._personas.list_ids():
            persona = self._personas.get(pid)
            if persona is None:
                continue
            level = self._knowledge.persona_level(pid)
            learnings = self._knowledge.persona_learnings(pid)
            views.append(PersonaView(
                id=pid,
                mission=persona.mission,
                level=level,
                skill_count=len(persona.skill_ids),
                source=self._personas.source(pid),
                has_knowledge=has_content(learnings),
            ))
        return views

    def list_teams(self) -> list[TeamView]:
        views = []
        for tid in self._teams.list_ids():
            team = self._teams.get(tid)
            if team is None:
                continue
            views.append(TeamView(
                id=tid,
                governance_profile=team.governance_profile,
                persona_ids=team.persona_ids,
                source=self._teams.source(tid),
            ))
        return views

    def inspect_persona(self, persona_id: str) -> dict | None:
        persona = self._personas.get(persona_id)
        if persona is None:
            return None
        level = self._knowledge.persona_level(persona_id)
        learnings = self._knowledge.persona_learnings(persona_id)
        source = self._personas.source(persona_id)

        # Find which teams this persona belongs to
        teams = []
        for tid in self._teams.list_ids():
            team = self._teams.get(tid)
            if team and persona_id in team.persona_ids:
                teams.append(tid)

        return {
            "id": persona_id,
            "mission": persona.mission,
            "level": level,
            "source": source,
            "skill_ids": persona.skill_ids,
            "teams": teams,
            "has_knowledge": has_content(learnings),
            "knowledge_preview": strip_placeholders(learnings) if learnings else "",
        }
