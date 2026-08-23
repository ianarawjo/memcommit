"""Normalize Resolve's mixed Context and direct-Memory CLI operands."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.authority.access import resolve_context_access
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.memory_focus import is_memory_uid_prefix
from memcommit.context_targeting.loading import (
    LocalDirectMemoryLocatorStore,
    resolve_local_direct_memory_locator,
    try_resolve_short_local_direct_memory_locator,
)
from memcommit.context_targeting.model import (
    DirectMemoryLocator,
    ExistingContextOperand,
)
from memcommit.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
    parse_direct_memory_locator,
)
from memcommit.resolve_application import ResolveError


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

    context_locators: list[str] = []
    memory_locators: list[DirectMemoryLocator] = []

    if context_locator is not None:
        context_locators.append(context_locator)

    def add_memory_operand(operand: str) -> None:
        locator = parse_direct_memory_locator(operand)
        memory_locators.append(locator)
        if locator.context_locator is not None:
            context_locators.append(locator.context_locator)

    for operand in auto_operands:
        parsed = parse_auto_typed_context_memory_operand(operand)
        if isinstance(parsed, DirectMemoryLocator):
            memory_locators.append(parsed)
            if parsed.context_locator is not None:
                context_locators.append(parsed.context_locator)
        else:
            assert isinstance(parsed, ExistingContextOperand)
            short_target = None
            if is_memory_uid_prefix(parsed.locator):
                canonical = resolve_context_locator(
                    parsed.locator,
                    current=current_context_name,
                )
                exact_context = store.context_exists(canonical)
                if not exact_context:
                    try:
                        resolve_context_access(
                            store,
                            canonical,
                            current_name=current_context_name,
                            required_permission="READ",
                        )
                    except FileNotFoundError:
                        pass
                    else:
                        exact_context = True
                short_target = (
                    None
                    if exact_context
                    else try_resolve_short_local_direct_memory_locator(
                        store,
                        parsed.locator,
                        current=current_context_name,
                    )
                )
            if short_target is None:
                # A nonlocal name may still be a readable Grant. Resolve's
                # authority port retains the final existence decision.
                context_locators.append(parsed.locator)
            else:
                context_locators.append(short_target.context_name)
                memory_locators.append(
                    DirectMemoryLocator(
                        short_target.memory_uid,
                        short_target.context_name,
                    )
                )

    for operand in memory_operands:
        add_memory_operand(operand)

    canonical_contexts = list(
        dict.fromkeys(
            resolve_context_locator(locator, current=current_context_name)
            for locator in context_locators
        )
    )
    if canonical_contexts:
        selectors = tuple(
            locator.memory_selector for locator in memory_locators
        )
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
            canonical_contexts[0]
            if canonical_contexts
            else current_context_name
        ),
        memory_selectors=selectors,
    )


__all__ = ["ResolveCliTargets", "normalize_resolve_cli_targets"]
