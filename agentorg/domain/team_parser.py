"""Parse team YAML content into a Team domain model."""

from __future__ import annotations

import yaml

from agentorg.domain.models import Budget, Gates, ItemSource, RoleSpec, RunMode, Team


def parse_team(content: str, source: ItemSource = ItemSource.REPO) -> Team:
    """Parse a team YAML string into a Team model.

    Supports two formats:

    Flat (backwards compatible):
        personas:
          - architect
          - developer

    Graph (with dependencies):
        roles:
          - id: architect
            depends_on: [program-manager]
          - id: developer
            depends_on: [architect]
          - id: tester
            depends_on: [developer]
          - id: code-reviewer
            depends_on: [developer]

    If both `roles` and `personas` are present, `roles` takes precedence.
    """
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid team YAML: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Team YAML must be a mapping")

    team_id = data.get("team_id", "")
    if not team_id:
        raise ValueError("Team YAML must have a team_id field")

    gates_data = data.get("gates", {})
    budget_data = data.get("budget", {})

    # Parse roles — graph format or flat format
    role_specs: list[RoleSpec] = []
    persona_ids: list[str] = []

    roles_data = data.get("roles")
    if roles_data and isinstance(roles_data, list):
        # Graph format
        for entry in roles_data:
            if isinstance(entry, str):
                # Simple string in roles list — no dependencies
                role_specs.append(RoleSpec(id=entry))
                persona_ids.append(entry)
            elif isinstance(entry, dict):
                rid = entry.get("id", "")
                deps = entry.get("depends_on", [])
                if isinstance(deps, str):
                    deps = [deps]
                role_specs.append(RoleSpec(id=rid, depends_on=deps))
                persona_ids.append(rid)
    else:
        # Flat format — sequential chain (each depends on previous)
        flat_ids = data.get("personas", [])
        persona_ids = flat_ids
        prev = None
        for pid in flat_ids:
            deps = [prev] if prev else []
            role_specs.append(RoleSpec(id=pid, depends_on=deps))
            prev = pid

    return Team(
        id=team_id,
        mode_default=RunMode(data.get("mode_default", "team")),
        persona_ids=persona_ids,
        role_specs=role_specs,
        governance_profile=data.get("governance_profile", "quality_first"),
        execution_profile=data.get("execution_profile", "local_default"),
        gates=Gates(
            reviewer_required=gates_data.get("reviewer_required", True),
            tester_required=gates_data.get("tester_required", True),
        ),
        budget=Budget(
            max_calls=budget_data.get("max_calls", 15),
            reflection=budget_data.get("reflection", True),
            interactions=budget_data.get("interactions", 3),
        ),
        source=source,
    )
