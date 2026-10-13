"""Process console inputs, require one Context, and return Resolve targets."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.application.capabilities.local_target_lookup import (
    LocalDirectMemoryLocatorStore,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
)
from memcommit.core.context_targeting.model import DirectMemoryLocator

from ..model import ResolveError
from .find_existing_context import (
    find_memory_owner_context,
    locate_context_from_operand,
)
from .identify_target_from_input import (
    identify_context_or_memory_operand,
    identify_memory_operand,
)


@dataclass(frozen=True, slots=True)
class ResolveConsoleTargets:
    """One canonical Resolve Context and its optional Memory restrictions."""

    context_name: str | None
    memory_selectors: tuple[str, ...]


def finalize_console_targets(
    store: LocalDirectMemoryLocatorStore,
    auto_operands: Sequence[str],
    *,
    context_locator: str | None,
    memory_operands: Sequence[str],
    current_context_name: str | None,
    recursive: bool = False,
) -> ResolveConsoleTargets:
    """Finalize request targets while preserving the one-Context input contract.

    Every lookup uses the same command-start current Context and frozen readable
    candidates. Explicit Memory selectors retain their prefixes when a Context
    is known; otherwise local owner lookup supplies their canonical Memory UIDs.
    """
    context_candidates = freeze_profile_context_access_candidates(
        store,
        current_name=current_context_name,
    )
    context_names: list[str] = []
    if context_locator is not None:
        context_names.append(
            locate_context_from_operand(
                store,
                context_locator,
                current_context_name=current_context_name,
                context_candidates=context_candidates,
            )
        )
    identified_inputs = [
        identify_context_or_memory_operand(
            store,
            operand,
            current_context_name=current_context_name,
            context_candidates=context_candidates,
        )
        for operand in auto_operands
    ]
    identified_inputs.extend(
        identify_memory_operand(
            store,
            operand,
            current_context_name=current_context_name,
            context_candidates=context_candidates,
        )
        for operand in memory_operands
    )
    memory_locators: list[DirectMemoryLocator] = []
    for target in identified_inputs:
        if isinstance(target, str):
            context_names.append(target)
        else:
            memory_locators.append(target)
            if target.context_locator is not None and not recursive:
                context_names.append(target.context_locator)

    if recursive:
        root = require_single_context(
            context_names, current_context_name=current_context_name
        )
        if root is None and memory_locators:
            root = require_single_context(
                [
                    locator.context_locator
                    or find_memory_owner_context(
                        store,
                        locator.memory_selector,
                        current_context_name=current_context_name,
                    ).context_name
                    for locator in memory_locators
                ],
                current_context_name=None,
            )
        return ResolveConsoleTargets(
            root,
            tuple(
                f"{locator.context_locator}:{locator.memory_selector}"
                if locator.context_locator
                else locator.memory_selector
                for locator in memory_locators
            ),
        )
    if context_names:
        selectors = tuple(locator.memory_selector for locator in memory_locators)
    else:
        memory_targets = tuple(
            find_memory_owner_context(
                store,
                locator.memory_selector,
                current_context_name=current_context_name,
            )
            for locator in memory_locators
        )
        context_names.extend(target.context_name for target in memory_targets)
        selectors = tuple(target.memory_uid for target in memory_targets)
    return ResolveConsoleTargets(
        context_name=require_single_context(
            context_names,
            current_context_name=current_context_name,
        ),
        memory_selectors=selectors,
    )


def require_single_context(
    context_names: Sequence[str],
    *,
    current_context_name: str | None,
) -> str | None:
    """Require one distinct owner, falling back to current only without targets."""
    canonical_contexts = tuple(dict.fromkeys(context_names))
    if len(canonical_contexts) > 1:
        raise ResolveError(
            "Resolve operands select multiple Contexts: "
            + ", ".join(repr(name) for name in canonical_contexts)
            + ". Every selected Memory must belong to one Resolve Context."
        )
    return canonical_contexts[0] if canonical_contexts else current_context_name


__all__ = ["ResolveConsoleTargets", "finalize_console_targets"]
