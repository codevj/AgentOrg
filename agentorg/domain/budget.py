"""Budget state machine — tracks LLM call usage per run."""

from __future__ import annotations

from dataclasses import dataclass

from agentorg.domain.models import Budget, BudgetActivity


@dataclass
class BudgetState:
    """Mutable budget state for a single run."""

    calls_used: int = 0
    calls_max: int = 15
    reflection_allowed: bool = True
    reflection_used: int = 0
    interaction_used: int = 0
    interaction_max: int = 3

    @classmethod
    def from_budget(cls, budget: Budget) -> BudgetState:
        """Create initial state from a team's budget config."""
        return cls(
            calls_max=budget.max_calls,
            reflection_allowed=budget.reflection,
            interaction_max=budget.interactions,
        )

    def check(self, activity: BudgetActivity) -> bool:
        """Check if an activity is within budget."""
        if activity == BudgetActivity.EXEC:
            return self.calls_used < self.calls_max
        elif activity == BudgetActivity.REFLECT:
            return (
                self.reflection_allowed
                and self.calls_used < self.calls_max
                and self.reflection_used == 0
            )
        elif activity == BudgetActivity.INTERACT:
            return (
                self.interaction_used < self.interaction_max
                and self.calls_used < self.calls_max
            )
        return True

    def record(self, activity: BudgetActivity) -> None:
        """Record that an activity consumed a call."""
        self.calls_used += 1
        if activity == BudgetActivity.REFLECT:
            self.reflection_used += 1
        elif activity == BudgetActivity.INTERACT:
            self.interaction_used += 1

    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Calls: {self.calls_used}/{self.calls_max}  "
            f"Interactions: {self.interaction_used}/{self.interaction_max}  "
            f"Reflection: {self.reflection_used}"
        )

    def to_dict(self) -> dict[str, int | bool]:
        """Serialize to dict for persistence."""
        return {
            "calls_used": self.calls_used,
            "calls_max": self.calls_max,
            "reflection_allowed": self.reflection_allowed,
            "reflection_used": self.reflection_used,
            "interaction_used": self.interaction_used,
            "interaction_max": self.interaction_max,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BudgetState:
        """Deserialize from dict."""
        return cls(
            calls_used=data.get("calls_used", 0),
            calls_max=data.get("calls_max", 15),
            reflection_allowed=data.get("reflection_allowed", True),
            reflection_used=data.get("reflection_used", 0),
            interaction_used=data.get("interaction_used", 0),
            interaction_max=data.get("interaction_max", 3),
        )
