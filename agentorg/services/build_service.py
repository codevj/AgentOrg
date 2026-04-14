"""Build service — hire, team, adopt, contribute, skill management."""

from __future__ import annotations

from agentorg.domain.models import (
    Budget,
    Gates,
    ItemSource,
    Persona,
    RunMode,
    Skill,
    SkillMetadata,
    Team,
)
from agentorg.ports.knowledge_store import KnowledgeStore
from agentorg.ports.repository import PersonaRepository, SkillRepository, TeamRepository


_PERSONA_TEMPLATE = """\
# Persona: {id}

## Mission

Describe this persona's responsibility in one sentence.

## Required inputs

- What this role needs to start its work
- Handoffs from upstream roles
- Relevant context or data

## Output format

Must follow the handoff schema with:

- `input_digest`: what was received and understood
- `decision`: what was decided or produced
- `rationale`: why — key tradeoffs or reasoning
- `artifacts`: what was produced
- `risks`: what could go wrong
- `exit_status`: `pass` when deliverables are complete and quality criteria met

## Exit criteria

- Deliverables completed
- Risks documented
- Quality standards met

## Non-goals

- List responsibilities this persona should NOT perform
"""


class BuildService:
    def __init__(
        self,
        persona_repo: PersonaRepository,
        team_repo: TeamRepository,
        skill_repo: SkillRepository,
        knowledge_store: KnowledgeStore,
    ) -> None:
        self._personas = persona_repo
        self._teams = team_repo
        self._skills = skill_repo
        self._knowledge = knowledge_store

    # ── Hire ──

    def hire(self, persona_id: str) -> Persona:
        """Create a new persona in the user's org."""
        if self._personas.exists(persona_id):
            raise ValueError(f"Role already exists: {persona_id}")

        content = _PERSONA_TEMPLATE.format(id=persona_id)
        persona = Persona(
            id=persona_id,
            raw_content=content,
            mission="Describe this persona's responsibility in one sentence.",
            source=ItemSource.USER,
        )
        self._personas.save_to_user(persona)
        self._knowledge.init_persona(persona_id)
        return persona

    def hire_interactive(
        self,
        persona_id: str,
        *,
        mission: str = "",
        required_inputs: list[str] | None = None,
        exit_criteria: list[str] | None = None,
        non_goals: list[str] | None = None,
    ) -> Persona:
        """Create a new persona with user-supplied content instead of placeholders."""
        if self._personas.exists(persona_id):
            raise ValueError(f"Role already exists: {persona_id}")

        mission_text = mission or "Describe this persona's responsibility in one sentence."

        inputs_items = required_inputs or []
        if inputs_items:
            inputs_block = "\n".join(f"- {item}" for item in inputs_items)
        else:
            inputs_block = (
                "- What this role needs to start its work\n"
                "- Handoffs from upstream roles\n"
                "- Relevant context or data"
            )

        exit_items = exit_criteria or []
        if exit_items:
            exit_block = "\n".join(f"- {item}" for item in exit_items)
        else:
            exit_block = (
                "- Deliverables completed\n"
                "- Risks documented\n"
                "- Quality standards met"
            )

        non_goal_items = non_goals or []
        if non_goal_items:
            non_goals_block = "\n".join(f"- {item}" for item in non_goal_items)
        else:
            non_goals_block = "- List responsibilities this persona should NOT perform"

        content = (
            f"# Persona: {persona_id}\n\n"
            f"## Mission\n\n{mission_text}\n\n"
            f"## Required inputs\n\n{inputs_block}\n\n"
            "## Output format\n\n"
            "Must follow the handoff schema with:\n\n"
            "- `input_digest`: what was received and understood\n"
            "- `decision`: what was decided or produced\n"
            "- `rationale`: why — key tradeoffs or reasoning\n"
            "- `artifacts`: what was produced\n"
            "- `risks`: what could go wrong\n"
            "- `exit_status`: `pass` when deliverables are complete and quality criteria met\n\n"
            f"## Exit criteria\n\n{exit_block}\n\n"
            f"## Non-goals\n\n{non_goals_block}\n"
        )

        persona = Persona(
            id=persona_id,
            raw_content=content,
            mission=mission_text,
            required_inputs=required_inputs or [],
            exit_criteria=exit_criteria or [],
            non_goals=non_goals or [],
            source=ItemSource.USER,
        )
        self._personas.save_to_user(persona)
        self._knowledge.init_persona(persona_id)
        return persona

    # ── Team ──

    def create_team(self, team_id: str) -> Team:
        """Create a new team in the user's org."""
        if self._teams.exists(team_id):
            raise ValueError(f"Team already exists: {team_id}")

        team = Team(
            id=team_id,
            mode_default=RunMode.TEAM,
            persona_ids=["program-manager", "architect", "developer", "tester", "code-reviewer"],
            governance_profile="quality_first",
            execution_profile="local_default",
            gates=Gates(),
            budget=Budget(max_calls=12, reflection=True, interactions=3),
            source=ItemSource.USER,
        )
        self._teams.save_to_user(team)
        self._knowledge.init_team(team_id)
        return team

    # ── Adopt (copy starter to user org for customization) ──

    def adopt_persona(self, persona_id: str) -> Persona:
        if self._personas.source(persona_id) == ItemSource.USER:
            raise ValueError(f"Already in your org: {persona_id}")
        persona = self._personas.get(persona_id)
        if persona is None:
            raise ValueError(f"Starter not found: {persona_id}")
        adopted = Persona(
            id=persona.id,
            raw_content=persona.raw_content,
            mission=persona.mission,
            required_inputs=persona.required_inputs,
            exit_criteria=persona.exit_criteria,
            non_goals=persona.non_goals,
            skill_ids=persona.skill_ids,
            source=ItemSource.USER,
        )
        self._personas.save_to_user(adopted)
        self._knowledge.init_persona(persona_id)
        return adopted

    def adopt_persona_if_missing(self, persona_id: str) -> bool:
        """Adopt a persona if it's not already in the user's org.

        Returns True if a copy was made, False if the persona was already a
        user item or could not be resolved.
        """
        if self._personas.source(persona_id) == ItemSource.USER:
            return False
        persona = self._personas.get(persona_id)
        if persona is None:
            return False
        adopted = Persona(
            id=persona.id,
            raw_content=persona.raw_content,
            mission=persona.mission,
            required_inputs=persona.required_inputs,
            exit_criteria=persona.exit_criteria,
            non_goals=persona.non_goals,
            skill_ids=persona.skill_ids,
            source=ItemSource.USER,
        )
        self._personas.save_to_user(adopted)
        self._knowledge.init_persona(persona_id)
        return True

    def adopt_team_if_missing(self, team_id: str) -> bool:
        """Adopt a team if it's not already in the user's org.

        Returns True if a copy was made, False if the team was already a user
        item or could not be resolved.
        """
        if self._teams.source(team_id) == ItemSource.USER:
            return False
        team = self._teams.get(team_id)
        if team is None:
            return False
        adopted = Team(
            id=team.id,
            mode_default=team.mode_default,
            persona_ids=team.persona_ids,
            role_specs=team.role_specs,
            governance_profile=team.governance_profile,
            execution_profile=team.execution_profile,
            gates=team.gates,
            budget=team.budget,
            source=ItemSource.USER,
        )
        self._teams.save_to_user(adopted)
        self._knowledge.init_team(team_id)
        return True

    def adopt_team(self, team_id: str) -> Team:
        if self._teams.source(team_id) == ItemSource.USER:
            raise ValueError(f"Already in your org: {team_id}")
        team = self._teams.get(team_id)
        if team is None:
            raise ValueError(f"Starter not found: {team_id}")
        adopted = Team(
            id=team.id,
            mode_default=team.mode_default,
            persona_ids=team.persona_ids,
            governance_profile=team.governance_profile,
            execution_profile=team.execution_profile,
            gates=team.gates,
            budget=team.budget,
            source=ItemSource.USER,
        )
        self._teams.save_to_user(adopted)
        self._knowledge.init_team(team_id)
        return adopted

    # ── Contribute (copy from user org to repo for sharing) ──

    def contribute_persona(self, persona_id: str) -> None:
        if self._personas.source(persona_id) != ItemSource.USER:
            raise ValueError(f"Not in your org: {persona_id}")
        persona = self._personas.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona not found: {persona_id}")
        self._personas.save_to_repo(persona)

    def contribute_team(self, team_id: str) -> None:
        if self._teams.source(team_id) != ItemSource.USER:
            raise ValueError(f"Not in your org: {team_id}")
        team = self._teams.get(team_id)
        if team is None:
            raise ValueError(f"Team not found: {team_id}")
        self._teams.save_to_repo(team)

    def contribute_skill(self, skill_id: str) -> None:
        if self._skills.source(skill_id) != ItemSource.USER:
            raise ValueError(f"Not in your org: {skill_id}")
        skill = self._skills.get(skill_id)
        if skill is None:
            raise ValueError(f"Skill not found: {skill_id}")
        self._skills.save_to_repo(skill)

    # ── Skills ──

    def add_skill_to_persona(self, persona_id: str, skill_id: str) -> None:
        if not self._skills.exists(skill_id):
            raise ValueError(f"Skill not found: {skill_id}")
        persona = self._personas.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona not found: {persona_id}")
        if skill_id in persona.skill_ids:
            return  # already has it
        # Append skill to persona.md content
        updated_content = persona.raw_content.rstrip() + f"\n- {skill_id}\n"
        if "## Skills" not in persona.raw_content:
            updated_content = persona.raw_content.rstrip() + f"\n\n## Skills\n\n- {skill_id}\n"
        updated = Persona(
            id=persona.id,
            raw_content=updated_content,
            mission=persona.mission,
            required_inputs=persona.required_inputs,
            exit_criteria=persona.exit_criteria,
            non_goals=persona.non_goals,
            skill_ids=[*persona.skill_ids, skill_id],
            source=persona.source,
        )
        if persona.source == ItemSource.USER:
            self._personas.save_to_user(updated)
        else:
            self._personas.save_to_repo(updated)

    def remove_skill_from_persona(self, persona_id: str, skill_id: str) -> None:
        persona = self._personas.get(persona_id)
        if persona is None:
            raise ValueError(f"Persona not found: {persona_id}")
        if skill_id not in persona.skill_ids:
            raise ValueError(f"Persona '{persona_id}' does not have skill '{skill_id}'")

        # Remove skill_id from the list
        new_skill_ids = [s for s in persona.skill_ids if s != skill_id]

        # Remove the `- skill_id` line from the ## Skills section in raw_content
        import re
        updated_content = re.sub(
            r"\n- " + re.escape(skill_id) + r"\s*", "\n", persona.raw_content
        )
        # Clean up empty Skills section (header with no items)
        updated_content = re.sub(
            r"\n## Skills\n\s*\n*(?=\n##|\Z)", "", updated_content
        )

        updated = Persona(
            id=persona.id,
            raw_content=updated_content,
            mission=persona.mission,
            required_inputs=persona.required_inputs,
            exit_criteria=persona.exit_criteria,
            non_goals=persona.non_goals,
            skill_ids=new_skill_ids,
            source=persona.source,
        )
        if persona.source == ItemSource.USER:
            self._personas.save_to_user(updated)
        else:
            self._personas.save_to_repo(updated)

    def create_skill(self, skill_id: str) -> Skill:
        if self._skills.exists(skill_id):
            raise ValueError(f"Skill already exists: {skill_id}")
        title = skill_id.replace("-", " ").title()
        body = (
            f"# {title}\n\n"
            "## When to use this skill\n\n"
            "Describe when an agent should apply this skill.\n\n"
            "## Process\n\n"
            "1. Step one\n"
            "2. Step two\n"
            "3. Step three\n\n"
            "## What to avoid\n\n"
            "- Things this skill should NOT be used for\n"
        )
        skill = Skill(
            id=skill_id,
            metadata=SkillMetadata(
                name=skill_id,
                description="Describe what this skill does.",
            ),
            body=body,
            source=ItemSource.USER,
        )
        self._skills.save_to_user(skill)
        return skill
