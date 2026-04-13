"""Run store protocol — save and retrieve execution runs."""

from __future__ import annotations

from typing import Protocol

from agentorg.domain.budget import BudgetState
from agentorg.domain.models import Run


class RunStore(Protocol):
    """Port for persisting run logs and budget tracking."""

    def save(self, run: Run) -> None: ...
    def list_recent(self, count: int = 10) -> list[Run]: ...
    def get(self, run_id: str) -> Run | None: ...
    def save_budget(self, run_id: str, budget: BudgetState) -> None: ...
    def load_budget(self, run_id: str) -> BudgetState | None: ...
