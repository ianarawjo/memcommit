"""Exact-name terminal adapter for one ordinary Context Init request."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from memcommit.application.operations.context_init.application import ContextInitRequest
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import (
    ContextNameView,
    choose_context_name,
    suggest_fresh_context_name,
)


@dataclass(frozen=True)
class ContextInitTuiSetup:
    """Host-provided namespace and validator for one exact name edit."""

    expected_current: str | None
    context_names: tuple[str, ...]
    validate_name: Callable[[str], object] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if len(set(self.context_names)) != len(self.context_names) or any(
            not isinstance(name, str) or not name for name in self.context_names
        ):
            raise ValueError("Context Init TUI requires a distinct local catalog.")
        if self.expected_current is not None and (
            not isinstance(self.expected_current, str) or not self.expected_current
        ):
            raise ValueError("Context Init TUI current Context is invalid.")
        if not callable(self.validate_name):
            raise TypeError("Context Init TUI requires a name validator.")


def run_context_init_tui(
    *,
    setup: ContextInitTuiSetup,
    create_parents: bool,
    chooser: Callable[[ContextNameView], str | None] = choose_context_name,
) -> ContextInitRequest | None:
    """Edit one proposed name and return a request without creating anything."""

    suggestion = suggest_fresh_context_name("new-context", setup.context_names)
    name = chooser(
        ContextNameView(
            value=suggestion,
            label="NEW CONTEXT NAME",
            state="NEW CONTEXT",
            detail="Enter creates this exact Context and switches to it.",
            validate=setup.validate_name,
            context_names=setup.context_names,
            current_context=setup.expected_current,
        )
    )
    if name is None:
        return None
    return ContextInitRequest(
        name=name,
        create_parents=create_parents,
        expected_current=setup.expected_current,
    )


__all__ = ["ContextInitTuiSetup", "run_context_init_tui"]
