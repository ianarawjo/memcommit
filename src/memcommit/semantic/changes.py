"""Structured change types proposed by semantic operations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from memcommit.context import Memory

if TYPE_CHECKING:
    from memcommit.context import Context


@dataclass
class AddChange:
    """Proposed addition of new information as a fresh memory."""
    content: str
    reason: str


@dataclass
class RemoveChange:
    """Proposed deletion of an entire memory."""
    uid: str
    content: str   # snapshot of the memory text, for display only
    reason: str


@dataclass
class EditChange:
    """Proposed in-place edit of a memory (partial relevance to the forget query)."""
    uid: str
    old_content: str
    new_content: str
    reason: str


ProposedChange: TypeAlias = AddChange | RemoveChange | EditChange


def parse_proposals(data: dict, ctx: Context) -> list[ProposedChange]:
    """
    Convert a parsed LLM response dict into ProposedChange objects.
    Silently skips entries with unknown uids (hallucinations) or missing fields.
    """
    valid_uids = {
        uid
        for uid, info in ctx.iter_entries()
        if isinstance(info, Memory)
    }
    changes: list[ProposedChange] = []

    for item in data.get("proposed_changes", []):
        op = item.get("operation")
        uid = item.get("uid", "")

        if uid not in valid_uids:
            continue

        if op == "remove":
            mem = ctx.memories[uid]
            assert isinstance(mem, Memory)
            changes.append(RemoveChange(
                uid=uid,
                content=mem.content,
                reason=item.get("reason", ""),
            ))

        elif op == "edit":
            new_content = item.get("new_content", "").strip()
            if not new_content:
                continue
            mem = ctx.memories[uid]
            assert isinstance(mem, Memory)
            changes.append(EditChange(
                uid=uid,
                old_content=mem.content,
                new_content=new_content,
                reason=item.get("reason", ""),
            ))

    return changes


def apply_changes(ctx: Context, changes: list[ProposedChange]) -> None:
    """
    Apply approved ProposedChanges to ctx in-memory.
    Call store.save(ctx) afterwards to persist.
    """
    import uuid
    for change in changes:
        if isinstance(change, AddChange):
            ctx.add(Memory(uid=str(uuid.uuid4()), content=change.content))
        elif isinstance(change, RemoveChange):
            if change.uid in ctx.memories:
                ctx.remove(change.uid)
        elif isinstance(change, EditChange):
            if change.uid in ctx.memories and isinstance(ctx.memories[change.uid], Memory):
                ctx.replace(Memory(uid=change.uid, content=change.new_content))
