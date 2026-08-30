"""Coordinate common Copy and Move console operands."""

from __future__ import annotations

from memcommit.application.operations.copy_and_move.application import (
    MemoryTransferError,
)
from memcommit.adapters.console.coordination.endpoint_operand import (
    choose_endpoint_operand,
)


def selected_memory_locators(
    positional: list[str] | None,
    options: list[str] | None,
) -> tuple[str, ...]:
    """Return one unambiguous nonempty Memory-locator sequence."""

    positional_values = tuple(positional or ())
    option_values = tuple(options or ())
    if positional_values and option_values:
        raise MemoryTransferError(
            "Use positional MEMORY locators or repeat --memory, not both."
        )
    values = positional_values or option_values
    if not values:
        raise MemoryTransferError(
            "Provide one or more MEMORY locators, or repeat --memory."
        )
    return values


def target_context_option(into: str | None, to: str | None) -> str | None:
    """Resolve the canonical Target operand from its two public spellings."""

    try:
        return choose_endpoint_operand(
            None,
            role="Target",
            options=(("--into", into), ("--to", to)),
        )
    except ValueError as error:
        raise MemoryTransferError(str(error)) from error


__all__ = ["selected_memory_locators", "target_context_option"]
