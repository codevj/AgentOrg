"""Cursor backend — sync to ~/.cursor/agents/, execute via cursor --chat."""

from __future__ import annotations

from pathlib import Path

from agentorg.domain.knowledge import has_content, strip_placeholders
from agentorg.ports.backend import BackendInfo
from agentorg.ports.executor import CLIExecutor
from agentorg.ports.knowledge_store import KnowledgeStore
from agentorg.ports.renderer import TemplateRenderer
from agentorg.ports.repository import PersonaRepository, SkillRepository, TeamRepository


class CursorBackend:
    def __init__(
        self,
        *,
        org_name: str,
        persona_repo: PersonaRepository,
        team_repo: TeamRepository,
        skill_repo: SkillRepository,
        knowledge_store: KnowledgeStore,
        renderer: TemplateRenderer,
        executor: CLIExecutor,
        contracts_dir: Path,
    ) -> None:
        self._agent_dir = Path.home() / ".cursor" / "agents"
        self._org_name = org_name
        self._personas = persona_repo
        self._teams = team_repo
        self._skills = skill_repo
        self._knowledge = knowledge_store
        self._renderer = renderer
        self._executor = executor
        self._contracts_dir = contracts_dir

    def _prefix(self) -> str:
        """'fleet-{org}-' — every org is named, so every agent file is prefixed."""
        return f"fleet-{self._org_name}-"

    def _agent_filename(self, persona_id: str) -> str:
        return f"{self._prefix()}{persona_id}.md"

    def _cleanup_stale(self, keep: set[str]) -> None:
        prefix = self._prefix()
        if not self._agent_dir.is_dir():
            return
        for f in self._agent_dir.iterdir():
            if f.name.startswith(prefix) and f.name.endswith(".md") and f.name not in keep:
                f.unlink()

    def info(self) -> BackendInfo:
        return BackendInfo(
            name="cursor",
            cli="cursor",
            installed=self._executor.is_installed("cursor"),
            description="Cursor — native subagent support",
            agent_dir=str(self._agent_dir),
        )

    def sync(self, team_id: str | None = None, **kwargs) -> int:
        self._agent_dir.mkdir(parents=True, exist_ok=True)
        synced = 0
        keep: set[str] = set()

        if team_id:
            team = self._teams.get(team_id)
            if team is None:
                raise ValueError(f"Team not found: {team_id}")
            persona_ids = team.persona_ids
        else:
            persona_ids = self._personas.list_ids()

        contract_file = self._contracts_dir / "handoff-schema.md"
        handoff_contract = contract_file.read_text() if contract_file.is_file() else ""

        for pid in persona_ids:
            persona = self._personas.get(pid)
            if persona is None:
                continue

            learnings = self._knowledge.persona_learnings(pid)
            knowledge_text = strip_placeholders(learnings) if has_content(learnings) else ""

            skill_texts = []
            for sid in persona.skill_ids:
                skill = self._skills.get(sid)
                if skill:
                    skill_texts.append(skill.body)

            content = self._renderer.render("claude_agent.md.j2", {
                "persona_id": pid,
                "mission": persona.mission,
                "persona_content": persona.raw_content,
                "knowledge": knowledge_text,
                "skills": "\n\n".join(skill_texts),
                "handoff_contract": handoff_contract,
            })

            filename = self._agent_filename(pid)
            (self._agent_dir / filename).write_text(content)
            keep.add(filename)
            synced += 1

        self._cleanup_stale(keep)
        return synced

    def prompt(self, text: str) -> str:
        if not self._executor.is_installed("cursor"):
            raise RuntimeError("'cursor' CLI not found")
        result = self._executor.run("cursor --chat", input_text=text)
        if not result.success:
            raise RuntimeError(f"Cursor execution failed: {result.stderr}")
        return result.stdout

    def execute(self, team_id: str, task: str, run_id: str, cwd: Path | None = None) -> str:
        self.sync(team_id)
        return self.prompt(task)
