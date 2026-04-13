"""Run service — execute tasks through teams or solo."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentorg.config import ReflectionMode
from agentorg.domain.budget import BudgetState
from agentorg.domain.knowledge import has_content, strip_placeholders
from agentorg.domain.models import BudgetActivity, Run, RunMode, RunStatus
from agentorg.ports.backend import Backend
from agentorg.ports.knowledge_store import KnowledgeStore
from agentorg.ports.repository import PersonaRepository, PolicyRepository, SkillRepository, TeamRepository
from agentorg.ports.renderer import TemplateRenderer
from agentorg.ports.run_store import RunStore
from agentorg.services.reflect_service import ReflectService


def _read_project_files(project_root: Path) -> dict:
    """Read all project context files and return as template variables."""
    result = {
        "project_context": "",
        "project_commands": "",
        "project_runbooks": "",
        "project_knowledge": "",
        "project_skills": "",
    }

    # Context
    context_dir = project_root / "context"
    if context_dir.is_dir():
        parts = []
        for f in sorted(context_dir.glob("*.md")):
            parts.append(f.read_text())
        result["project_context"] = "\n\n".join(parts)

    # Commands
    commands_dir = project_root / "commands"
    if commands_dir.is_dir():
        parts = []
        for f in sorted(commands_dir.glob("*.md")):
            parts.append(f.read_text())
        result["project_commands"] = "\n\n".join(parts)

    # Runbooks
    runbooks_dir = project_root / "runbooks"
    if runbooks_dir.is_dir():
        parts = []
        for f in sorted(runbooks_dir.glob("*.md")):
            parts.append(f.read_text())
        result["project_runbooks"] = "\n\n".join(parts)

    # Knowledge
    learnings = project_root / "knowledge" / "learnings.md"
    if learnings.is_file():
        content = learnings.read_text()
        if has_content(content):
            result["project_knowledge"] = strip_placeholders(content)

    # Skills
    skills_dir = project_root / "skills"
    if skills_dir.is_dir():
        parts = []
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.is_file():
                # Strip YAML frontmatter
                text = skill_file.read_text()
                in_fm = False
                past_fm = False
                lines = []
                for line in text.splitlines():
                    if line.strip() == "---" and not past_fm:
                        if not in_fm:
                            in_fm = True
                        else:
                            past_fm = True
                        continue
                    if past_fm:
                        lines.append(line)
                if lines:
                    parts.append("\n".join(lines))
                elif not in_fm:
                    parts.append(text)
        result["project_skills"] = "\n\n".join(parts)

    return result


_EMPTY_PROJECT_VARS = {
    "project_context": "",
    "project_commands": "",
    "project_runbooks": "",
    "project_knowledge": "",
    "project_skills": "",
}


class RunService:
    def __init__(
        self,
        persona_repo: PersonaRepository,
        team_repo: TeamRepository,
        skill_repo: SkillRepository,
        policy_repo: PolicyRepository,
        knowledge_store: KnowledgeStore,
        run_store: RunStore,
        renderer: TemplateRenderer,
        reflect_service: ReflectService,
    ) -> None:
        self._personas = persona_repo
        self._teams = team_repo
        self._skills = skill_repo
        self._policies = policy_repo
        self._knowledge = knowledge_store
        self._runs = run_store
        self._renderer = renderer
        self._reflect = reflect_service

    def build_team_prompt(self, team_id: str, task: str, *, project_root: Path | None = None) -> str:
        """Build a team execution prompt (for clipboard/non-exec mode)."""
        team = self._teams.get(team_id)
        if team is None:
            raise ValueError(f"Team not found: {team_id}")
        return self._assemble_team_prompt(team, task, project_root=project_root)

    def build_solo_prompt(self, task: str, *, project_root: Path | None = None) -> str:
        """Build a solo execution prompt."""
        project_vars = _read_project_files(project_root) if project_root else _EMPTY_PROJECT_VARS
        return self._renderer.render("solo_prompt.md.j2", {"task": task, **project_vars})

    def build_summon_prompt(self, persona_id: str, task: str, *, project_root: Path | None = None) -> str:
        """Build a summon prompt for a single persona."""
        persona = self._personas.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona not found: {persona_id}")

        learnings = self._knowledge.persona_learnings(persona_id)
        knowledge_text = strip_placeholders(learnings) if has_content(learnings) else ""

        project_vars = _read_project_files(project_root) if project_root else _EMPTY_PROJECT_VARS

        title = persona_id.replace("-", " ").title()
        return self._renderer.render("summon_prompt.md.j2", {
            "role_title": title,
            "mission": persona.mission,
            "knowledge": knowledge_text,
            "task": task,
            **project_vars,
        })

    def execute(
        self,
        *,
        backend: Backend,
        team_id: str | None = None,
        task: str,
        solo: bool = False,
        reflection_mode: ReflectionMode = ReflectionMode.AUTO,
        project_root: Path | None = None,
        project_id: str | None = None,
        condense_after: int = 0,
    ) -> Run:
        """Execute a task via a backend. Returns the Run record."""
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        mode = RunMode.SOLO if solo else RunMode.TEAM

        if not solo and team_id is None:
            raise ValueError("No team specified. Set a default with: fleet config set default_team <id>")

        # Init budget
        team = self._teams.get(team_id) if team_id else None
        budget = BudgetState.from_budget(team.budget) if team else BudgetState()

        if not budget.check(BudgetActivity.EXEC):
            raise RuntimeError(f"Budget exceeded: {budget.summary()}")

        # Build prompt
        if solo:
            prompt = self.build_solo_prompt(task, project_root=project_root)
        else:
            prompt = self.build_team_prompt(team_id, task, project_root=project_root)  # type: ignore[arg-type]

        # Execute via backend's agent orchestration
        output = backend.execute(team_id or "solo", task, run_id)
        budget.record(BudgetActivity.EXEC)

        run = Run(
            id=run_id,
            mode=mode,
            team_id=team_id,
            task=task,
            date=datetime.now(timezone.utc),
            status=RunStatus.COMPLETED,
            output=output,
            backend=backend.info().name,
            budget_summary=budget.summary(),
        )
        self._runs.save(run)
        self._runs.save_budget(run_id, budget)

        # Auto-reflect if mode allows and budget permits
        if reflection_mode == ReflectionMode.AUTO and budget.check(BudgetActivity.REFLECT):
            try:
                reflection_prompt = self._reflect.generate_prompt(
                    run_content=output,
                    project_root=project_root,
                    project_id=project_id,
                )
                reflection_output = backend.prompt(reflection_prompt)
                budget.record(BudgetActivity.REFLECT)
                self._reflect.write_back(reflection_output, project_root=project_root)
                self._runs.save_budget(run_id, budget)

                # Condense if threshold reached
                if condense_after > 0:
                    try:
                        self._reflect.maybe_condense(
                            backend=backend,
                            condense_after=condense_after,
                        )
                    except Exception:
                        pass  # condensation failure is non-fatal
            except Exception:
                pass  # reflection failure is non-fatal

        return run

    def _assemble_team_prompt(self, team, task: str, *, project_root: Path | None = None) -> str:
        """Assemble a full team prompt with personas, knowledge, skills."""
        roles = []
        for pid in team.persona_ids:
            persona = self._personas.get(pid)
            if persona is None:
                continue

            learnings = self._knowledge.persona_learnings(pid)
            knowledge_text = strip_placeholders(learnings) if has_content(learnings) else ""

            # Gather skill bodies
            skill_texts = []
            for sid in persona.skill_ids:
                skill = self._skills.get(sid)
                if skill:
                    skill_texts.append(skill.body)

            title = pid.replace("-", " ").title()
            roles.append({
                "title": title,
                "content": persona.raw_content,
                "knowledge": knowledge_text,
                "skills": "\n\n".join(skill_texts),
            })

        # Org + team learnings
        org_raw = self._knowledge.org_learnings()
        org_text = strip_placeholders(org_raw) if has_content(org_raw) else ""

        team_raw = self._knowledge.team_learnings(team.id)
        team_text = strip_placeholders(team_raw) if has_content(team_raw) else ""

        # Read governance rules
        gov_policy = self._policies.get_governance(team.governance_profile)
        gov_rules = gov_policy.rules if gov_policy else []

        # Project context
        project_vars = _read_project_files(project_root) if project_root else _EMPTY_PROJECT_VARS

        return self._renderer.render("team_prompt.md.j2", {
            "governance_profile": team.governance_profile,
            "gates": {
                "reviewer_required": team.gates.reviewer_required,
                "tester_required": team.gates.tester_required,
            },
            "governance_rules": gov_rules,
            "interaction_budget": team.budget.interactions,
            "org_learnings": org_text,
            "team_learnings": team_text,
            "roles": roles,
            "task": task,
            "team_id": team.id,
            **project_vars,
        })
