"""Domain models — all value objects and entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Level(Enum):
    """Persona/team maturity level, assessed by LLM during reflection."""

    STARTER = "starter"
    PRACTICED = "practiced"
    EXPERIENCED = "experienced"
    EXPERT = "expert"


class ItemSource(Enum):
    """Where an item was resolved from."""

    REPO = "repo"
    USER = "user"
    NONE = "none"


class GovernanceProfile(Enum):
    QUALITY_FIRST = "quality_first"
    SPEED_FIRST = "speed_first"
    SECURITY_FIRST = "security_first"
    COST_FIRST = "cost_first"


class ExitStatus(Enum):
    PASS = "pass"
    BLOCKED = "blocked"


class Severity(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RunMode(Enum):
    TEAM = "team"
    SOLO = "solo"


class RunStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class BudgetActivity(Enum):
    EXEC = "exec"
    REFLECT = "reflect"
    INTERACT = "interact"


# ── Value Objects ──


@dataclass(frozen=True)
class Budget:
    """Token budget configuration for a team."""

    max_calls: int = 15
    reflection: bool = True
    interactions: int = 3


@dataclass(frozen=True)
class Gates:
    """Quality gate configuration for a team."""

    reviewer_required: bool = True
    tester_required: bool = True


@dataclass(frozen=True)
class SkillRef:
    """A reference to a skill, as listed in a persona's ## Skills section."""

    skill_id: str


# ── Entities ──


@dataclass(frozen=True)
class Persona:
    """A role in the org."""

    id: str
    raw_content: str  # full persona.md content
    mission: str
    required_inputs: list[str] = field(default_factory=list)
    exit_criteria: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)
    source: ItemSource = ItemSource.REPO


@dataclass(frozen=True)
class RoleSpec:
    """A role in a team with its dependencies."""

    id: str
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Team:
    """A team composition."""

    id: str
    mode_default: RunMode = RunMode.TEAM
    persona_ids: list[str] = field(default_factory=list)  # ordered (for display + backwards compat)
    role_specs: list[RoleSpec] = field(default_factory=list)  # dependency graph
    governance_profile: str = "quality_first"
    execution_profile: str = "local_default"
    gates: Gates = field(default_factory=Gates)
    budget: Budget = field(default_factory=Budget)
    source: ItemSource = ItemSource.REPO

    def execution_stages(self) -> list[list[str]]:
        """Compute parallel execution stages from the dependency graph.

        Returns a list of stages. Each stage is a list of role IDs that can
        run in parallel. Stages execute sequentially.

        Falls back to one-role-per-stage if no role_specs are defined.
        """
        if not self.role_specs:
            return [[pid] for pid in self.persona_ids]

        specs = {rs.id: rs for rs in self.role_specs}
        remaining = set(specs.keys())
        completed: set[str] = set()
        stages: list[list[str]] = []

        while remaining:
            # Find roles whose dependencies are all completed
            ready = [
                rid for rid in remaining
                if all(dep in completed for dep in specs[rid].depends_on)
            ]
            if not ready:
                # Cycle or unresolvable — dump remaining as final stage
                stages.append(sorted(remaining))
                break
            stages.append(sorted(ready))
            completed.update(ready)
            remaining -= set(ready)

        return stages


@dataclass(frozen=True)
class SkillMetadata:
    """Frontmatter from a SKILL.md file."""

    name: str
    description: str
    author: str = ""
    version: str = "1.0"
    license: str = "Apache-2.0"


@dataclass(frozen=True)
class Skill:
    """A reusable procedural knowledge module."""

    id: str
    metadata: SkillMetadata
    body: str  # markdown body (frontmatter stripped)
    source: ItemSource = ItemSource.REPO


@dataclass(frozen=True)
class GovernancePolicy:
    """A governance policy definition."""

    id: str
    rules: list[str] = field(default_factory=list)
    gates: Gates = field(default_factory=Gates)


@dataclass(frozen=True)
class ExecutionPolicy:
    """An execution routing policy definition."""

    id: str
    routing: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Handoff:
    """A structured handoff artifact produced by a role."""

    role_id: str
    input_digest: str
    decision: str
    rationale: str
    artifacts: str
    risks: str
    exit_status: ExitStatus


@dataclass(frozen=True)
class Run:
    """A recorded execution run."""

    id: str
    mode: RunMode
    team_id: str | None
    task: str
    date: datetime
    status: RunStatus
    output: str = ""
    backend: str = ""
    budget_summary: str = ""
    # Debug/trace info
    roles: list[str] = field(default_factory=list)
    stages: list[list[str]] = field(default_factory=list)
    workdir: str = ""
    org_name: str = ""
    project_id: str | None = None
    reflection_mode: str = ""


@dataclass(frozen=True)
class PersonaLearning:
    """A single learning block extracted from reflection output."""

    persona_id: str
    content: str  # markdown bullet points


@dataclass(frozen=True)
class TeamLearning:
    """A team learning block extracted from reflection output."""

    team_id: str
    content: str


@dataclass(frozen=True)
class OrgLearning:
    """Org-wide learning block extracted from reflection output."""

    content: str


@dataclass(frozen=True)
class LevelAssessment:
    """A level assessment for a persona, extracted from reflection output."""

    persona_id: str
    level: Level


@dataclass(frozen=True)
class Project:
    """A project — persistent codebase context, knowledge, skills, and task history."""

    id: str
    root: Path  # e.g. ~/.agent-org/projects/my-api/
    repo_paths: list[Path] = field(default_factory=list)  # repos this project works on


@dataclass(frozen=True)
class ProjectLearning:
    """A project learning block extracted from reflection output."""

    project_id: str
    content: str


@dataclass(frozen=True)
class ReflectionResult:
    """Parsed result of a reflection LLM call."""

    persona_learnings: list[PersonaLearning] = field(default_factory=list)
    team_learnings: list[TeamLearning] = field(default_factory=list)
    org_learnings: list[OrgLearning] = field(default_factory=list)
    level_assessments: list[LevelAssessment] = field(default_factory=list)
    project_learnings: list[ProjectLearning] = field(default_factory=list)
