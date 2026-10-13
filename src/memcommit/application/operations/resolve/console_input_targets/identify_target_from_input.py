"""Identify the Context or direct-Memory target specified by one console input."""

from __future__ import annotations

from typing import TYPE_CHECKING

from memcommit.application.capabilities.local_target_lookup import (
    LocalDirectMemoryLocatorStore,
    try_resolve_short_local_direct_memory_locator,
)
from memcommit.application.context_access.operand_resolution import (
    try_resolve_context_access_or_local_memory,
)
from memcommit.core.context_targeting.model import DirectMemoryLocator, DirectMemoryTarget
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix

from .find_existing_context import locate_context_from_operand

if TYPE_CHECKING:
    from memcommit.application.capabilities.operand_resolution import ContextOperandCandidate
    from memcommit.application.context_access.access import ContextAccess


def identify_memory_operand(
    store: LocalDirectMemoryLocatorStore,
    operand: str,
    *,
    current_context_name: str | None,
    context_candidates: tuple[ContextOperandCandidate[ContextAccess], ...],
) -> DirectMemoryLocator:
    """Identify a Memory selector and canonicalize an explicitly named owner."""
    locator = parse_direct_memory_locator(operand)
    if locator.context_locator is None:
        return locator
    owner_name = locate_context_from_operand(
        store,
        locator.context_locator,
        current_context_name=current_context_name,
        context_candidates=context_candidates,
    )
    return DirectMemoryLocator(locator.memory_selector, owner_name)


def identify_context_or_memory_operand(
    store: LocalDirectMemoryLocatorStore,
    operand: str,
    *,
    current_context_name: str | None,
    context_candidates: tuple[ContextOperandCandidate[ContextAccess], ...],
) -> str | DirectMemoryLocator:
    """Identify an automatic operand with the existing name/UID precedence."""
    if ":" in operand:
        return identify_memory_operand(
            store,
            operand,
            current_context_name=current_context_name,
            context_candidates=context_candidates,
        )
    target = try_resolve_context_access_or_local_memory(
        store,
        operand,
        current_name=current_context_name,
        candidates=context_candidates,
    )
    if isinstance(target, DirectMemoryTarget):
        return DirectMemoryLocator(target.memory_uid, target.context_name)
    if target is not None:
        return target.name
    short_target = (
        try_resolve_short_local_direct_memory_locator(
            store,
            operand,
            current=current_context_name,
        )
        if is_memory_uid_prefix(operand)
        else None
    )
    if short_target is not None:
        return DirectMemoryLocator(short_target.memory_uid, short_target.context_name)
    return locate_context_from_operand(
        store,
        operand,
        current_context_name=current_context_name,
        context_candidates=context_candidates,
    )
