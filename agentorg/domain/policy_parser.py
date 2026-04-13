"""Parse governance and execution policy YAML into domain models."""

from __future__ import annotations

import yaml

from agentorg.domain.models import ExecutionPolicy, Gates, GovernancePolicy


def parse_governance_policy(content: str) -> GovernancePolicy:
    """Parse a governance policy YAML string."""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("Governance policy YAML must be a mapping")

    gates_data = data.get("gates", {})
    rules = data.get("rules", [])

    return GovernancePolicy(
        id=data.get("id", ""),
        rules=rules if isinstance(rules, list) else [],
        gates=Gates(
            reviewer_required=gates_data.get("reviewer_required", True),
            tester_required=gates_data.get("tester_required", True),
        ),
    )


def parse_execution_policy(content: str) -> ExecutionPolicy:
    """Parse an execution policy YAML string."""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("Execution policy YAML must be a mapping")

    return ExecutionPolicy(
        id=data.get("id", ""),
        routing=data.get("routing", {}),
    )
