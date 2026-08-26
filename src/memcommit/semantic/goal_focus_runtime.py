"""Local Store projection and freshness checks for shared Goal operands."""

from __future__ import annotations

import hashlib

from memcommit.context import Context, Memory
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.loading import (
    resolve_local_direct_memory_locator,
    try_resolve_short_local_direct_memory_locator,
)
from memcommit.context_targeting.model import DirectMemoryLocator, InlineTextOperand
from memcommit.context_targeting.operands import (
    classify_context_or_inline_text_operand,
)
from memcommit.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.semantic.goal_focus import (
    FrozenGoalFocus,
    GoalFocusError,
    GoalFocusItem,
    GoalFocusKind,
    inline_goal_focus,
)
from memcommit.store import MemoryStore, context_record_digest


def _memory_digest(memory: Memory) -> str:
    return hashlib.sha256(memory.content.encode("utf-8")).hexdigest()


def _items(context: Context, memories: tuple[Memory, ...]) -> tuple[GoalFocusItem, ...]:
    return tuple(
        GoalFocusItem(
            alias=f"g{index:06d}",
            content=memory.content,
            context_name=context.name,
            context_uid=context.uid,
            memory_uid=memory.uid,
            content_digest=_memory_digest(memory),
        )
        for index, memory in enumerate(memories, 1)
    )


def _memory_focus(
    store: MemoryStore,
    *,
    locator: str,
    current_name: str | None,
    kind: GoalFocusKind = "MEMORY",
) -> FrozenGoalFocus:
    target = resolve_local_direct_memory_locator(
        store,
        locator,
        current=current_name,
    )
    context = store.load_direct(target.context_name)
    memory = context.memories.get(target.memory_uid)
    if not isinstance(memory, Memory):  # pragma: no cover - resolver invariant
        raise GoalFocusError("The selected Goal item is not an ordinary Memory.")
    return FrozenGoalFocus(
        kind=kind,
        label=f"{context.name}:{memory.uid[:8]}",
        items=_items(context, (memory,)),
        context_name=context.name,
        context_uid=context.uid,
        context_digest=context_record_digest(context),
    )


def freeze_goal_focus_context(
    context: Context,
    *,
    kind: GoalFocusKind = "CONTEXT",
    require_single: bool = False,
) -> FrozenGoalFocus:
    """Freeze the directly owned ordinary Memories of one already-loaded Context."""

    direct_items = tuple(context.iter_items())
    if any(not isinstance(item, Memory) for item in direct_items):
        raise GoalFocusError(
            "A Goal Context must contain only directly owned ordinary Memories."
        )
    memories = tuple(item for item in direct_items if isinstance(item, Memory))
    if not memories:
        raise GoalFocusError("A Goal Context contains no direct Memories.")
    if require_single and len(memories) != 1:
        raise GoalFocusError("This operation requires exactly one Goal Memory.")
    return FrozenGoalFocus(
        kind=kind,
        label=context.name,
        items=_items(context, memories),
        context_name=context.name,
        context_uid=context.uid,
        context_digest=context_record_digest(context),
    )


def freeze_goal_focus_operand(
    store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
    require_single: bool = False,
) -> FrozenGoalFocus:
    """Resolve one Context, direct Memory, or explicit/unambiguous inline Goal.

    Existing Contexts win. UUID-shaped and ``CONTEXT:UID`` values remain strict
    Memory selectors. Missing relative or portable-looking Context names fail
    closed so a typo cannot become provider-visible Goal text. ``text:`` is the
    explicit escape hatch for short or otherwise locator-shaped literal text.
    """

    if not isinstance(operand, str) or not operand.strip():
        raise GoalFocusError("A Goal operand must be nonblank.")
    value = operand.strip()
    if value.startswith("text:"):
        return inline_goal_focus(value.removeprefix("text:"))

    parsed = parse_auto_typed_context_memory_operand(value)
    if isinstance(parsed, DirectMemoryLocator):
        return _memory_focus(
            store,
            locator=value,
            current_name=current_name,
        )

    canonical_name = resolve_context_locator(parsed.locator, current=current_name)
    if store.context_exists(canonical_name):
        return freeze_goal_focus_context(
            store.load_direct(canonical_name),
            require_single=require_single,
        )

    short_memory = try_resolve_short_local_direct_memory_locator(
        store,
        parsed.locator,
        current=current_name,
    )
    if short_memory is not None:
        return _memory_focus(
            store,
            locator=short_memory.memory_uid,
            current_name=current_name,
        )

    classified = classify_context_or_inline_text_operand(
        value,
        current=current_name,
        context_exists=store.context_exists,
    )
    if isinstance(classified, InlineTextOperand):
        return inline_goal_focus(classified.text)
    raise GoalFocusError(f"Goal Context {canonical_name!r} does not exist locally.")


def revalidate_goal_focus(store: MemoryStore, focus: FrozenGoalFocus) -> None:
    """Reject any durable Goal focus whose exact Context pre-image changed."""

    if not isinstance(focus, FrozenGoalFocus):
        raise TypeError("Goal focus revalidation requires a FrozenGoalFocus.")
    if focus.kind == "INLINE":
        return
    assert focus.context_name is not None
    if not store.context_exists(focus.context_name):
        raise GoalFocusError(
            f"Goal Context {focus.context_name!r} no longer exists."
        )
    current = store.load_direct(focus.context_name)
    if (
        current.uid != focus.context_uid
        or context_record_digest(current) != focus.context_digest
    ):
        raise GoalFocusError(
            f"Goal Context {focus.context_name!r} changed while semantic work was running."
        )


__all__ = [
    "freeze_goal_focus_context",
    "freeze_goal_focus_operand",
    "revalidate_goal_focus",
]
