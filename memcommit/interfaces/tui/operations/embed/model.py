"""Typed setup state for interactive Embed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbedTuiSetup:
    """Frozen local Context catalog supplied by the composition boundary."""

    names: tuple[str, ...]
    current_context: str | None = None

    def __post_init__(self) -> None:
        if len(self.names) < 2:
            raise ValueError("Interactive Embed requires at least two local Contexts.")
        if len(set(self.names)) != len(self.names):
            raise ValueError("Interactive Embed requires a distinct local catalog.")
        if any(not isinstance(name, str) or not name for name in self.names):
            raise ValueError("Embed TUI Context names must be nonempty text.")
        if self.current_context is not None and self.current_context not in self.names:
            raise ValueError("Embed TUI current Context is outside the local catalog.")
