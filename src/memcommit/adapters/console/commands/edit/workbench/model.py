"""Typed setup for the interactive exact Edit console workbench."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class EditTuiSetup:
    names: tuple[str, ...]
    selectable_names: frozenset[str]
    selected_context: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Edit TUI requires a distinct Context catalog.")
        if not self.selectable_names or not self.selectable_names <= set(self.names):
            raise ValueError("Edit TUI requires an UPDATE-authorized Context.")
        if self.selected_context not in self.selectable_names:
            raise ValueError("Initial Edit Context is unavailable.")


__all__ = ["EditTuiSetup"]
