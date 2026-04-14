"""Copilot backend — sync to ~/.squad/, execute via copilot CLI.

Copilot CLI has a native `/fleet` command for parallel multi-agent
execution. We generate an orchestration prompt that tells the main
copilot session to use /fleet for parallel stages and read role
charters from ~/.squad/agents/{role}/charter.md.
"""

from __future__ import annotations

from pathlib import Path

from agentorg.domain.knowledge import has_content, strip_placeholders
from agentorg.ports.backend import BackendInfo
from agentorg.ports.executor import CLIExecutor
from agentorg.ports.knowledge_store import KnowledgeStore
from agentorg.ports.renderer import TemplateRenderer
from agentorg.ports.repository import PersonaRepository, SkillRepository, TeamRepository


class CopilotBackend:
    def __init__(
        self,
        *,
        org_name: str | None,
        persona_repo: PersonaRepository,
        team_repo: TeamRepository,
        skill_repo: SkillRepository,
        knowledge_store: KnowledgeStore,
        executor: CLIExecutor,
        contracts_dir: Path,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        self._squad_dir = Path.home() / ".squad"
        self._org_name = org_name
        self._personas = persona_repo
        self._teams = team_repo
        self._skills = skill_repo
        self._knowledge = knowledge_store
        self._executor = executor
        self._contracts_dir = contracts_dir
        self._renderer = renderer

    def info(self) -> BackendInfo:
        return BackendInfo(
            name="copilot",
            cli="copilot",
            installed=self._executor.is_installed("copilot"),
            description="Microsoft Copilot — Squad for team orchestration",
            agent_dir=str(self._squad_dir),
        )

    def sync(self, team_id: str | None = None, **kwargs) -> int:
        self._squad_dir.mkdir(parents=True, exist_ok=True)
        (self._squad_dir / "agents").mkdir(exist_ok=True)
        (self._squad_dir / "skills").mkdir(exist_ok=True)
        synced = 0

        if team_id:
            team = self._teams.get(team_id)
            if team is None:
                raise ValueError(f"Team not found: {team_id}")
            persona_ids = team.persona_ids
        else:
            persona_ids = self._personas.list_ids()

        # team.md
        lines = ["# Team Roster\n\n## Agents\n"]
        for pid in persona_ids:
            persona = self._personas.get(pid)
            if persona:
                lines.append(f"- **{pid}**: {persona.mission}")
        lines.append("\n## Execution Order\n")
        for i, pid in enumerate(persona_ids, 1):
            lines.append(f"{i}. {pid}")
        (self._squad_dir / "team.md").write_text("\n".join(lines) + "\n")

        # directives.md
        contract_file = self._contracts_dir / "handoff-schema.md"
        contract = contract_file.read_text() if contract_file.is_file() else ""
        (self._squad_dir / "directives.md").write_text(f"# Directives\n\n{contract}\n")

        # decisions.md (from learnings)
        org_raw = self._knowledge.org_learnings()
        org_text = strip_placeholders(org_raw) if has_content(org_raw) else ""
        decisions = "# Decisions\n\nAccumulated knowledge from previous runs.\n"
        if org_text:
            decisions += f"\n## Org-Wide\n\n{org_text}\n"
        if team_id:
            team_raw = self._knowledge.team_learnings(team_id)
            if has_content(team_raw):
                decisions += f"\n## Team: {team_id}\n\n{strip_placeholders(team_raw)}\n"
        (self._squad_dir / "decisions.md").write_text(decisions)

        # Skills
        for sid in self._skills.list_ids():
            skill = self._skills.get(sid)
            if skill:
                (self._squad_dir / "skills" / f"{sid}.md").write_text(skill.body)

        # Agent charters
        for pid in persona_ids:
            persona = self._personas.get(pid)
            if persona is None:
                continue
            agent_dir = self._squad_dir / "agents" / pid
            agent_dir.mkdir(parents=True, exist_ok=True)

            learnings = self._knowledge.persona_learnings(pid)
            knowledge_text = strip_placeholders(learnings) if has_content(learnings) else ""

            charter = persona.raw_content
            if knowledge_text:
                charter += f"\n\n## Accumulated Knowledge\n\n{knowledge_text}\n"
            charter += f"\n\n## Handoff Contract\n\n{contract}\n"

            (agent_dir / "charter.md").write_text(charter)
            synced += 1

        return synced

    def _resolve_cli(self) -> str:
        if self._executor.is_installed("squad"):
            return "squad run"
        elif self._executor.is_installed("copilot"):
            return "copilot -p"
        raise RuntimeError("Neither 'squad' nor 'copilot' CLI found")

    def prompt(self, text: str) -> str:
        result = self._executor.run(self._resolve_cli(), input_text=text)
        if not result.success:
            raise RuntimeError(f"Copilot execution failed: {result.stderr}")
        return result.stdout

    def execute(self, team_id: str, task: str, run_id: str, cwd: Path | None = None) -> str:
        """Launch Copilot CLI interactively with orchestration instructions.

        The prompt tells the main copilot session to use /fleet for
        parallel stages and read role charters from ~/.squad/agents/.
        """
        self.sync(team_id)
        if not (self._executor.is_installed("copilot") or self._executor.is_installed("squad")):
            raise RuntimeError("Neither 'copilot' nor 'squad' CLI found")

        # Render the lead prompt from the template
        if self._renderer is None:
            raise RuntimeError("Copilot backend missing renderer — can't build orchestration prompt")

        team = self._teams.get(team_id)
        if team is None:
            raise ValueError(f"Team not found: {team_id}")

        specs_by_id = {rs.id: rs for rs in team.role_specs}
        roles = []
        for pid in team.persona_ids:
            persona = self._personas.get(pid)
            if persona:
                spec = specs_by_id.get(pid)
                roles.append({
                    "id": pid,
                    "mission": persona.mission,
                    "depends_on": spec.depends_on if spec else [],
                })

        org_raw = self._knowledge.org_learnings()
        org_text = strip_placeholders(org_raw) if has_content(org_raw) else ""
        team_raw = self._knowledge.team_learnings(team.id)
        team_text = strip_placeholders(team_raw) if has_content(team_raw) else ""

        body = self._renderer.render("copilot_lead.md.j2", {
            "team_id": team.id,
            "roles": roles,
            "stages": team.execution_stages(),
            "team_learnings": team_text,
            "org_learnings": org_text,
        })

        full_prompt = f"{body}\n\n---\n\n## Your Task\n\n{task}\n"

        # Use interactive mode so the user sees /fleet progress live.
        # Copilot CLI accepts prompts via arg with -p flag, but interactive
        # mode (no -p) shows live multi-agent output better.
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, dir=cwd if cwd else None,
        ) as f:
            f.write(full_prompt)
            prompt_file = f.name

        cli = "copilot" if self._executor.is_installed("copilot") else "squad"
        try:
            exit_code = self._executor.run_interactive(
                f'{cli} -p "$(cat {prompt_file})" --allow-all-tools',
                cwd=cwd,
            )
        finally:
            import os
            try:
                os.unlink(prompt_file)
            except OSError:
                pass

        if exit_code != 0:
            raise RuntimeError(f"Copilot exited with code {exit_code}")
        return ""
