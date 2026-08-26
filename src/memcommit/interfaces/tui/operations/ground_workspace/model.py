"""Frozen setup values for a new physical Ground workspace location."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


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
        if (
            len(set(self.context_names)) != len(self.context_names)
            or any(not isinstance(name, str) or not name for name in self.context_names)
        ):
            raise ValueError(
                "Ground workspace TUI requires a distinct local Context catalog."
            )
        if self.current_context is not None and (
            not isinstance(self.current_context, str)
            or not self.current_context
        ):
            raise ValueError("Ground workspace current Context is invalid.")
        if not callable(self.validate_name):
            raise TypeError("Ground workspace TUI requires a name validator.")


__all__ = ["GroundWorkspaceLocationSetup"]
