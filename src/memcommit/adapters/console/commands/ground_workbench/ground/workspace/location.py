"""Save Location model and chooser for a new physical Ground workspace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import (
    ContextNameView,
    choose_context_name,
)


@dataclass(frozen=True)
class GroundWorkspaceLocationSetup:
    """Host-owned namespace and validator for one uncreated workspace root."""

    initial_name: str
    current_context: str | None
    context_names: tuple[str, ...]
    validate_name: Callable[[str], object] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.initial_name, str) or not self.initial_name:
            raise ValueError("Ground workspace Save Location is required.")
        if len(set(self.context_names)) != len(self.context_names) or any(
            not isinstance(name, str) or not name for name in self.context_names
        ):
            raise ValueError(
                "Ground workspace TUI requires a distinct local Context catalog."
            )
        if self.current_context is not None and (
            not isinstance(self.current_context, str) or not self.current_context
        ):
            raise ValueError("Ground workspace current Context is invalid.")
        if not callable(self.validate_name):
            raise TypeError("Ground workspace TUI requires a name validator.")


def choose_ground_workspace_location(
    setup: GroundWorkspaceLocationSetup,
    *,
    chooser: Callable[[ContextNameView], str | None] = choose_context_name,
) -> str | None:
    """Return an exact uncreated root name without creating or switching."""

    return chooser(
        ContextNameView(
            value=setup.initial_name,
            label="NEW GROUND · SAVE LOCATION",
            state="NOT CREATED",
            detail=(
                "Enter continues to an unsaved Ground. Its root and five fixed "
                "child Contexts are created only after exact command approval."
            ),
            validate=setup.validate_name,
            context_names=setup.context_names,
            current_context=setup.current_context,
        )
    )


__all__ = ["GroundWorkspaceLocationSetup", "choose_ground_workspace_location"]
