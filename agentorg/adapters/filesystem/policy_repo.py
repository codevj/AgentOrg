"""Filesystem-backed PolicyRepository.

Reads from starters only (policies are framework-level, not user-customized).
"""

from __future__ import annotations

from agentorg.config import Config
from agentorg.domain.models import ExecutionPolicy, GovernancePolicy
from agentorg.domain.policy_parser import parse_execution_policy, parse_governance_policy


class FilePolicyRepository:
    def __init__(self, config: Config) -> None:
        self._policies_dir = config.policies_dir

    def get_governance(self, profile_id: str) -> GovernancePolicy | None:
        path = self._policies_dir / "governance" / f"{profile_id}.yaml"
        if not path.is_file():
            return None
        return parse_governance_policy(path.read_text())

    def get_execution(self, profile_id: str) -> ExecutionPolicy | None:
        path = self._policies_dir / "execution" / f"{profile_id}.yaml"
        if not path.is_file():
            return None
        return parse_execution_policy(path.read_text())
