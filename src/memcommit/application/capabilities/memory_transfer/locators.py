"""Transfer operand resolution and exact Target insertion gaps."""

from __future__ import annotations

import memcommit.core.context_targeting.direct_items as direct_items
from memcommit.application.capabilities.memory_transfer.context_bindings import (
    StoreTransferFrame,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferError,
    MemoryTransferPlacement,
)
from memcommit.application.capabilities.operand_resolution import (
    ContextOperandCandidate,
    ContextOperandNotFoundError,
    resolve_existing_context_operand,
)
from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator


def placement_for_context(
    context: Context,
    *,
    before: str | None,
    after: str | None,
) -> MemoryTransferPlacement:
    if before is not None and after is not None:
        raise MemoryTransferError("Pass only one of --before or --after.")
    order = context.ordered_uids()
    if before is None and after is None:
        position = len(order)
    else:
        selector = before if before is not None else after
        assert selector is not None
        anchor = direct_items.resolve_direct_item(context, selector)
        position = order.index(anchor.uid) + (1 if after is not None else 0)
    return MemoryTransferPlacement(
        position=position,
        previous_uid=order[position - 1] if position else None,
        next_uid=order[position] if position < len(order) else None,
    )


def _memory_matches(
    frames: tuple[StoreTransferFrame, ...],
    selector: str,
    *,
    owner_name: str | None,
) -> tuple[tuple[StoreTransferFrame, Memory], ...]:
    candidates = (
        tuple(frame for frame in frames if not frame.access.is_granted)
        if owner_name is None
        else tuple(frame for frame in frames if frame.display_name == owner_name)
    )
    if owner_name is not None and not candidates:
        raise FileNotFoundError(f"Context '{owner_name}' does not exist locally.")
    return tuple(
        (frame, item)
        for frame in candidates
        for item in frame.context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(selector)
    )


def resolve_one_memory(
    frames: tuple[StoreTransferFrame, ...],
    operand: str,
    *,
    explicit_source: str | None,
    current_name: str | None,
) -> tuple[StoreTransferFrame, Memory]:
    try:
        locator = parse_direct_memory_locator(
            operand,
            explicit_context=explicit_source,
        )
    except ValueError as error:
        raise MemoryTransferError(str(error)) from error
    owner_name = None
    if locator.context_locator is not None:
        try:
            owner_name = resolve_existing_context_operand(
                tuple(
                    ContextOperandCandidate(
                        uid=frame.context.uid,
                        name=frame.display_name,
                        value=frame,
                    )
                    for frame in frames
                ),
                locator.context_locator,
                current=current_name,
            ).name
        except ContextOperandNotFoundError as error:
            raise FileNotFoundError(
                f"Context {locator.context_locator!r} does not exist locally."
            ) from error
    matches = _memory_matches(
        frames,
        locator.memory_selector,
        owner_name=owner_name,
    )
    if not matches:
        if owner_name is None:
            raise MemoryTransferError(
                f"No directly owned Memory with uid starting with "
                f"{locator.memory_selector!r} was found in any local Context."
            )
        raise MemoryTransferError(
            f"No directly owned Memory with uid starting with "
            f"{locator.memory_selector!r} exists in Context {owner_name!r}."
        )
    if len(matches) > 1:
        choices = "; ".join(
            f"{frame.display_name}:{memory.uid}"
            for frame, memory in sorted(
                matches,
                key=lambda value: (value[0].display_name.casefold(), value[1].uid),
            )
        )
        raise MemoryTransferError(
            f"Memory prefix {locator.memory_selector!r} has multiple local "
            f"matches ({len(matches)}): {choices}. Use CONTEXT:UID."
        )
    return matches[0]


def target_frame(
    frames: tuple[StoreTransferFrame, ...],
    locator: str | None,
    *,
    current_name: str | None,
) -> StoreTransferFrame:
    if locator is None and current_name is None:
        raise MemoryTransferError(
            "No current Context. Pass --into TARGET_CONTEXT explicitly."
        )
    target_locator = locator or current_name or ""
    try:
        resolved = resolve_existing_context_operand(
            tuple(
                ContextOperandCandidate(
                    uid=frame.context.uid,
                    name=frame.display_name,
                    value=frame,
                )
                for frame in frames
                if not frame.access.is_granted
            ),
            target_locator,
            current=current_name,
        )
    except ContextOperandNotFoundError as error:
        raise FileNotFoundError(
            f"Copy/Move Target Context {target_locator!r} does not exist locally."
        ) from error
    return resolved.value


def unique_local_source_frames(
    memories: tuple[FrozenTransferMemory, ...],
    frames_by_name: dict[str, StoreTransferFrame],
) -> tuple[StoreTransferFrame, ...]:
    names = tuple(dict.fromkeys(item.source_context_name for item in memories))
    return tuple(
        frames_by_name[name]
        for name in names
        if not frames_by_name[name].access.is_granted
    )


def source_owner_locators(
    memory_locators: tuple[str, ...],
    source_locator: str | None,
) -> tuple[str, ...]:
    locators: list[str] = []
    for operand in memory_locators:
        try:
            locator = parse_direct_memory_locator(
                operand,
                explicit_context=source_locator,
            )
        except ValueError as error:
            raise MemoryTransferError(str(error)) from error
        if locator.context_locator is None:
            continue
        if locator.context_locator not in locators:
            locators.append(locator.context_locator)
    return tuple(locators)


def resolve_source_memories(
    locators: tuple[str, ...],
    *,
    source_locator: str | None,
    frames: tuple[StoreTransferFrame, ...],
    current_name: str | None,
) -> tuple[tuple[StoreTransferFrame, Memory], ...]:
    """Resolve a unique ordered batch without assigning output identity or authority."""
    resolved: list[tuple[StoreTransferFrame, Memory]] = []
    seen: set[tuple[str, str]] = set()
    for operand in locators:
        frame, memory = resolve_one_memory(
            frames,
            operand,
            explicit_source=source_locator,
            current_name=current_name,
        )
        identity = (frame.context.uid, memory.uid)
        if identity in seen:
            raise MemoryTransferError(
                f"Memory '{frame.display_name}:{memory.uid}' was selected more than once."
            )
        seen.add(identity)
        resolved.append((frame, memory))
    return tuple(resolved)
