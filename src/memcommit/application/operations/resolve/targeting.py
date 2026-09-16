"""Normalize Resolve's mixed Context and direct-Memory CLI operands."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
    try_resolve_context_access_or_local_memory,
)
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.application.capabilities.local_target_lookup import (
    LocalDirectMemoryLocatorStore,
    resolve_local_direct_memory_locator,
    try_resolve_short_local_direct_memory_locator,
)
from memcommit.core.context_targeting.model import (
    DirectMemoryLocator,
    DirectMemoryTarget,
)
from memcommit.core.context_targeting.resolution import (
    parse_direct_memory_locator,
)
from memcommit.application.operations.resolve.application import ResolveError


@dataclass(frozen=True, slots=True)
class ResolveCliTargets:
    """One canonical Resolve Context and its optional Memory restrictions."""

    context_name: str | None
    memory_selectors: tuple[str, ...]


def normalize_resolve_cli_targets(
    store: LocalDirectMemoryLocatorStore,
    auto_operands: Sequence[str],
    *,
    context_locator: str | None,
    memory_operands: Sequence[str],
    current_context_name: str | None,
) -> ResolveCliTargets:
    """Classify mixed operands without weakening Resolve's one-Context frame.

    UUID-shaped or ``CONTEXT:UID`` positional values use the shared direct-
    Memory grammar. Other positional values are existing-Context locators.
    Explicit ``--memory`` values may use short prefixes because their role is
    already known. Every owner locator is resolved against the same command-
    start current Context, and all resulting Contexts must agree.
    """

    context_names: list[str] = []
    memory_locators: list[DirectMemoryLocator] = []
    context_candidates = freeze_profile_context_access_candidates(
        store,
        current_name=current_context_name,
    )

    def add_context_operand(operand: str) -> str:
        resolved = resolve_existing_context_access(
            store,
            operand,
            current_name=current_context_name,
            required_permission="READ",
            candidates=context_candidates,
        )
        context_names.append(resolved.name)
        return resolved.name

    if context_locator is not None:
        add_context_operand(context_locator)

    def add_memory_operand(operand: str) -> None:
        locator = parse_direct_memory_locator(operand)
        if locator.context_locator is not None:
            owner_name = add_context_operand(locator.context_locator)
            locator = DirectMemoryLocator(locator.memory_selector, owner_name)
        memory_locators.append(locator)

    for operand in auto_operands:
        if ":" in operand:
            add_memory_operand(operand)
            continue
        target = try_resolve_context_access_or_local_memory(
            store,
            operand,
            current_name=current_context_name,
            candidates=context_candidates,
        )
        if isinstance(target, DirectMemoryTarget):
            context_names.append(target.context_name)
            memory_locators.append(
                DirectMemoryLocator(target.memory_uid, target.context_name)
            )
            continue
        if target is not None:
            context_names.append(target.name)
            continue
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
            context_names.append(short_target.context_name)
            memory_locators.append(
                DirectMemoryLocator(
                    short_target.memory_uid,
                    short_target.context_name,
                )
            )
            continue
        add_context_operand(operand)

    for operand in memory_operands:
        add_memory_operand(operand)

    canonical_contexts = list(dict.fromkeys(context_names))
    if canonical_contexts:
        selectors = tuple(locator.memory_selector for locator in memory_locators)
    else:
        # A bare Memory operand carries enough stable UUID shape to find its
        # directly owned local Context without giving the current Context
        # hidden priority. Grant contents are deliberately not enumerable here;
        # their public Context must be named explicitly before Resolve loads it.
        globally_resolved = tuple(
            resolve_local_direct_memory_locator(
                store,
                locator.memory_selector,
                current=current_context_name,
            )
            for locator in memory_locators
        )
        canonical_contexts.extend(
            dict.fromkeys(target.context_name for target in globally_resolved)
        )
        selectors = tuple(target.memory_uid for target in globally_resolved)

    if len(canonical_contexts) > 1:
        raise ResolveError(
            "Resolve operands select multiple Contexts: "
            + ", ".join(repr(name) for name in canonical_contexts)
            + ". Every selected Memory must belong to one Resolve Context."
        )

    return ResolveCliTargets(
        context_name=(
            canonical_contexts[0] if canonical_contexts else current_context_name
        ),
        memory_selectors=selectors,
    )


__all__ = ["ResolveCliTargets", "normalize_resolve_cli_targets"]
