"""Resolution logic — merge two sources with user-wins semantics.

Pure functions, no I/O. The filesystem adapter calls these after scanning directories.
"""

from __future__ import annotations

from typing import TypeVar

from agentorg.domain.models import ItemSource

T = TypeVar("T")


def resolve_item(
    user_item: T | None, repo_item: T | None
) -> tuple[T | None, ItemSource]:
    """Resolve a single item. User wins on collision."""
    if user_item is not None:
        return user_item, ItemSource.USER
    if repo_item is not None:
        return repo_item, ItemSource.REPO
    return None, ItemSource.NONE


def merge_id_lists(user_ids: list[str], repo_ids: list[str]) -> list[str]:
    """Union of ID lists. User IDs first, no duplicates. Preserves ordering."""
    seen = set(user_ids)
    return list(user_ids) + [rid for rid in repo_ids if rid not in seen]


def item_source(user_exists: bool, repo_exists: bool) -> ItemSource:
    """Determine source based on existence flags."""
    if user_exists:
        return ItemSource.USER
    if repo_exists:
        return ItemSource.REPO
    return ItemSource.NONE
