"""CLI coordination for explicit Context-or-Memory history reports."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.application.capabilities.context_locator import (
    resolve_context_locator,
    suggest_context_locators,
)
from memcommit.application.capabilities.name_suggestions import did_you_mean_suffix
from memcommit.core.context_targeting.memory_focus import is_memory_uid_selector
from memcommit.core.context_targeting.model import ContextTarget, DirectMemoryTarget
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator


HistoryReportTarget = ContextTarget | DirectMemoryTarget


def resolve_explicit_context_history_target(
    operand: str,
    *,
    current_context: str | None,
    available_context_names: Sequence[str],
) -> ContextTarget | None:
    """Return a Context target or leave explicit Memory grammar untouched."""

    names = tuple(dict.fromkeys(available_context_names))
    candidate = resolve_context_locator(operand, current=current_context)
    if candidate in names:
        return ContextTarget(candidate)
    if ":" in operand or is_memory_uid_selector(operand):
        return None
    suggestions = suggest_context_locators(
        operand,
        current=current_context,
        available_names=names,
    )
    raise ValueError(
        f"Context {candidate!r} does not exist."
        + did_you_mean_suffix(suggestions)
    )


def resolve_history_report_target(
    operand: str,
    *,
    explicit_context: str | None,
    current_context: str | None,
    available_context_names: Sequence[str],
) -> HistoryReportTarget:
    """Classify one explicit operand without fuzzy selection or UID guessing.

    Existing Context names win the otherwise ambiguous positional grammar.
    Qualified and explicitly scoped values remain Memory selectors, while a
    bare UUID-shaped value preserves the established Memory meaning.
    """

    names = tuple(dict.fromkeys(available_context_names))
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("History target received an invalid Context catalog.")

    if explicit_context is not None or ":" in operand:
        locator = parse_direct_memory_locator(
            operand,
            explicit_context=explicit_context,
        )
        owner_locator = locator.context_locator or current_context
        if owner_locator is None:
            raise ValueError(
                "No current Context is available for this Memory; use CONTEXT:UID."
            )
        return DirectMemoryTarget(
            resolve_context_locator(owner_locator, current=current_context),
            locator.memory_selector,
        )

    candidate = resolve_context_locator(operand, current=current_context)
    if candidate in names:
        return ContextTarget(candidate)
    if is_memory_uid_selector(operand):
        if current_context is None:
            raise ValueError(
                "No current Context is available for this Memory; use CONTEXT:UID."
            )
        return DirectMemoryTarget(current_context, operand)
    suggestions = suggest_context_locators(
        operand,
        current=current_context,
        available_names=names,
    )
    raise ValueError(
        f"Context {candidate!r} does not exist."
        + did_you_mean_suffix(suggestions)
    )


__all__ = [
    "HistoryReportTarget",
    "resolve_explicit_context_history_target",
    "resolve_history_report_target",
]
