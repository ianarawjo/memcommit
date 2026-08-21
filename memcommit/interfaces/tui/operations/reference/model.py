"""Typed setup for interactive snapshot Reference."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceTuiSetup:
    names: tuple[str, ...]
    selected_source: str
    selected_target: str
    current_context: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Reference TUI requires a local Context catalog.")
        if (
            self.selected_source not in self.names
            or self.selected_target not in self.names
        ):
            raise ValueError("Reference TUI initial Context is unavailable.")


__all__ = ["ReferenceTuiSetup"]
