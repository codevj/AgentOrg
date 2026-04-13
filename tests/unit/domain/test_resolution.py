"""Tests for resolution — merge logic with user-wins semantics."""

from agentorg.domain.resolution import resolve_item, merge_id_lists, item_source
from agentorg.domain.models import ItemSource


def test_resolve_user_wins():
    result, source = resolve_item("user_val", "repo_val")
    assert result == "user_val"
    assert source == ItemSource.USER


def test_resolve_repo_fallback():
    result, source = resolve_item(None, "repo_val")
    assert result == "repo_val"
    assert source == ItemSource.REPO


def test_resolve_none():
    result, source = resolve_item(None, None)
    assert result is None
    assert source == ItemSource.NONE


def test_merge_ids_union():
    merged = merge_id_lists(["a", "b"], ["b", "c", "d"])
    assert merged == ["a", "b", "c", "d"]


def test_merge_ids_user_first():
    merged = merge_id_lists(["x"], ["a", "b"])
    assert merged == ["x", "a", "b"]


def test_merge_ids_no_duplicates():
    merged = merge_id_lists(["a", "b"], ["a", "b"])
    assert merged == ["a", "b"]


def test_merge_ids_empty():
    assert merge_id_lists([], []) == []
    assert merge_id_lists(["a"], []) == ["a"]
    assert merge_id_lists([], ["b"]) == ["b"]


def test_item_source_user():
    assert item_source(True, True) == ItemSource.USER
    assert item_source(True, False) == ItemSource.USER


def test_item_source_repo():
    assert item_source(False, True) == ItemSource.REPO


def test_item_source_none():
    assert item_source(False, False) == ItemSource.NONE
