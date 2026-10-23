"""Exact Memory content groups in first-occurrence Context order."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from memcommit.models.context import Context
from memcommit.models.memory import Memory

ExactDuplicateKind = Literal["MEMORY"]


@dataclass(frozen=True)
class ExactDuplicateGroup:
    """One group of owned Memories with identical stored text."""

    item_kind: ExactDuplicateKind
    survivor_uid: str
    absorbed_uids: tuple[str, ...]
    summary: str
    content: str | None = None

    @property
    def duplicate_count(self) -> int:
        return len(self.absorbed_uids)


def find_exact_duplicate_groups(context: Context) -> tuple[ExactDuplicateGroup, ...]:
    """Keep the first Memory and list later exact-content occurrences."""
    if not isinstance(context, Context):
        raise TypeError("Exact duplicate discovery requires one Context.")
    members_by_content: dict[str, list[Memory]] = {}
    for memory in context.iter_memories():
        members_by_content.setdefault(memory.content, []).append(memory)
    return tuple(
        ExactDuplicateGroup(
            "MEMORY",
            members[0].uid,
            tuple(memory.uid for memory in members[1:]),
            content,
            content,
        )
        for content, members in members_by_content.items()
        if len(members) > 1
    )


__all__ = ["ExactDuplicateGroup", "ExactDuplicateKind", "find_exact_duplicate_groups"]
