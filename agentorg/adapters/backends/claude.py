"""Claude Code backend — sync to ~/.claude/agents/, execute via claude --print."""

from __future__ import annotations

from pathlib import Path

from agentorg.domain.knowledge import has_content, strip_placeholders
from agentorg.ports.backend import BackendInfo
from agentorg.ports.executor import CLIExecutor
from agentorg.ports.knowledge_store import KnowledgeStore
from agentorg.ports.renderer import TemplateRenderer
from agentorg.ports.repository import PersonaRepository, SkillRepository, TeamRepository


class ClaudeBackend:
    def __init__(
        self,
        *,
        org_name: str | None,
        persona_repo: PersonaRepository,
        team_repo: TeamRepository,
        skill_repo: SkillRepository,
        knowledge_store: KnowledgeStore,
        renderer: TemplateRenderer,
        executor: CLIExecutor,
        contracts_dir: Path,
    ) -> None:
        self._agent_dir = Path.home() / ".claude" / "agents"
        self._org_name = org_name
        self._personas = persona_repo
        self._teams = team_repo
        self._skills = skill_repo
        self._knowledge = knowledge_store
        self._renderer = renderer
        self._executor = executor
        self._contracts_dir = contracts_dir

    def _prefix(self) -> str:
        """'fleet-{org}-' — every org must be named."""
        if not self._org_name:
            raise RuntimeError(
                "No active org. Run 'fleet init' to create one."
            )
        return f"fleet-{self._org_name}-"

    def _agent_filename(self, persona_id: str) -> str:
        return f"{self._prefix()}{persona_id}.md"

    def _lead_filename(self, team_id: str) -> str:
        return f"{self._prefix()}{team_id}-lead.md"

    def _cleanup_stale(self, keep: set[str]) -> None:
        """Remove old fleet agents for this org that are no longer needed."""
        prefix = self._prefix()
        if not self._agent_dir.is_dir():
            return
        for f in self._agent_dir.iterdir():
            if f.name.startswith(prefix) and f.name.endswith(".md") and f.name not in keep:
                f.unlink()

    def info(self) -> BackendInfo:
        return BackendInfo(
            name="claude",
            cli="claude",
            installed=self._executor.is_installed("claude"),
            description="Claude Code — native agent teams",
            agent_dir=str(self._agent_dir),
        )

    def sync(self, team_id: str | None = None, **kwargs) -> int:
        self._agent_dir.mkdir(parents=True, exist_ok=True)
        synced = 0
        keep: set[str] = set()

        # Determine which personas to sync
        if team_id:
            team = self._teams.get(team_id)
            if team is None:
                raise ValueError(f"Team not found: {team_id}")
            persona_ids = team.persona_ids
        else:
            persona_ids = self._personas.list_ids()

        # Read handoff contract
        contract_file = self._contracts_dir / "handoff-schema.md"
        handoff_contract = contract_file.read_text() if contract_file.is_file() else ""

        # Generate agent definitions
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

        # Generate lead(s). If team_id is given, generate only that team's
        # lead; otherwise generate leads for all teams so switching teams
        # works without re-syncing.
        if team_id:
            team = self._teams.get(team_id)
            if team:
                self._generate_lead(team)
                keep.add(self._lead_filename(team.id))
                synced += 1
        else:
            for tid in self._teams.list_ids():
                team = self._teams.get(tid)
                if team:
                    self._generate_lead(team)
                    keep.add(self._lead_filename(team.id))
                    synced += 1

        # Generate fleet-helper (always present, not org-namespaced)
        helper_content = self._renderer.render("claude_helper.md.j2", {})
        (self._agent_dir / "fleet-fleethelper.md").write_text(helper_content)
        keep.add("fleet-fleethelper.md")
        synced += 1

        # Clean up stale agents from this org
        self._cleanup_stale(keep)

        return synced

    def prompt(self, text: str) -> str:
        """Raw LLM call — no sync, no agent. Used by fleet ask."""
        if not self._executor.is_installed("claude"):
            raise RuntimeError("'claude' CLI not found")
        result = self._executor.run("claude -p", input_text=text)
        if not result.success:
            raise RuntimeError(f"Claude execution failed: {result.stderr}")
        return result.stdout

    def execute(self, team_id: str, task: str, run_id: str, cwd: Path | None = None) -> str:
        """Sync agents and launch Claude Code's main session with orchestration instructions.

        The lead template is rendered as the main prompt (not as a subagent) so
        Claude Code's main session can create an agent team — subagents can't
        create teams, only the main session can.

        Hands off control to Claude Code interactively. Returns empty string.
        """
        self.sync(team_id)
        if not self._executor.is_installed("claude"):
            raise RuntimeError("'claude' CLI not found")

        # Render the lead template as the orchestration instructions.
        lead_path = self._agent_dir / self._lead_filename(team_id)
        if not lead_path.is_file():
            raise RuntimeError(f"Lead template not found: {lead_path}")
        lead_content = lead_path.read_text()
        # Strip the YAML frontmatter — we want the body only as instructions.
        body = _strip_frontmatter(lead_content)

        # Combine orchestration + task into one prompt.
        full_prompt = f"{body}\n\n---\n\n## Your Task\n\n{task}\n"

        # Write to a temp file and pipe it in, to avoid shell escaping issues.
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, dir=cwd if cwd else None,
        ) as f:
            f.write(full_prompt)
            prompt_file = f.name

        try:
            exit_code = self._executor.run_interactive(
                f'cat "{prompt_file}" | claude',
                cwd=cwd,
            )
        finally:
            import os
            try:
                os.unlink(prompt_file)
            except OSError:
                pass

        if exit_code != 0:
            raise RuntimeError(f"Claude Code exited with code {exit_code}")
        return ""

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")

    def _generate_lead(self, team) -> None:
        # Build role info with dependency data
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

        content = self._renderer.render("claude_lead.md.j2", {
            "team_id": team.id,
            "governance_profile": team.governance_profile,
            "governance_rules": [],
            "roles": roles,
            "stages": team.execution_stages(),
            "team_learnings": team_text,
            "org_learnings": org_text,
            "org_name_with_dash": f"{self._org_name}-" if self._org_name else "",
        })

        (self._agent_dir / self._lead_filename(team.id)).write_text(content)


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter (between --- markers at the top) from markdown."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return content
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1:]).lstrip()
    return content
