"""Coordinate common Copy and Move console operands."""

from __future__ import annotations

from memcommit.application.capabilities.memory_transfer.contracts import (
    MemoryTransferError,
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


__all__ = ["selected_memory_locators"]
