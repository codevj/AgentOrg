"""Tests for budget state machine."""

from agentorg.domain.budget import BudgetState
from agentorg.domain.models import Budget, BudgetActivity


def test_initial_state():
    bs = BudgetState.from_budget(Budget(max_calls=10, reflection=True, interactions=3))
    assert bs.calls_used == 0
    assert bs.calls_max == 10
    assert bs.interaction_max == 3


def test_check_exec_allowed():
    bs = BudgetState(calls_max=2)
    assert bs.check(BudgetActivity.EXEC) is True


def test_check_exec_over_budget():
    bs = BudgetState(calls_used=5, calls_max=5)
    assert bs.check(BudgetActivity.EXEC) is False


def test_check_reflect_allowed():
    bs = BudgetState(calls_max=10, reflection_allowed=True, reflection_used=0)
    assert bs.check(BudgetActivity.REFLECT) is True


def test_check_reflect_already_used():
    bs = BudgetState(calls_max=10, reflection_allowed=True, reflection_used=1)
    assert bs.check(BudgetActivity.REFLECT) is False


def test_check_reflect_disabled():
    bs = BudgetState(calls_max=10, reflection_allowed=False)
    assert bs.check(BudgetActivity.REFLECT) is False


def test_check_interact_allowed():
    bs = BudgetState(calls_max=10, interaction_used=1, interaction_max=3)
    assert bs.check(BudgetActivity.INTERACT) is True


def test_check_interact_over_budget():
    bs = BudgetState(calls_max=10, interaction_used=3, interaction_max=3)
    assert bs.check(BudgetActivity.INTERACT) is False


def test_record_exec():
    bs = BudgetState(calls_max=10)
    bs.record(BudgetActivity.EXEC)
    assert bs.calls_used == 1


def test_record_reflect():
    bs = BudgetState(calls_max=10)
    bs.record(BudgetActivity.REFLECT)
    assert bs.calls_used == 1
    assert bs.reflection_used == 1


def test_record_interact():
    bs = BudgetState(calls_max=10)
    bs.record(BudgetActivity.INTERACT)
    assert bs.calls_used == 1
    assert bs.interaction_used == 1


def test_summary():
    bs = BudgetState(calls_used=3, calls_max=10, interaction_used=1, interaction_max=3, reflection_used=1)
    s = bs.summary()
    assert "3/10" in s
    assert "1/3" in s


def test_roundtrip_dict():
    bs = BudgetState(calls_used=2, calls_max=10, reflection_used=1, interaction_used=1, interaction_max=5)
    d = bs.to_dict()
    bs2 = BudgetState.from_dict(d)
    assert bs2.calls_used == 2
    assert bs2.calls_max == 10
    assert bs2.reflection_used == 1
    assert bs2.interaction_used == 1
    assert bs2.interaction_max == 5
