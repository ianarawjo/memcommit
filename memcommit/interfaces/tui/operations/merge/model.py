"""Frozen readable Source catalog for interactive Merge."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class MergeTuiSetup:
    """Process-local Source choices and one frozen current Target."""

    names: tuple[str, ...]
    selectable_names: frozenset[str]
    selected_source: str
    target_context: str
    initial_recursive: bool = False
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Merge TUI requires a distinct visible catalog.")
        if not self.selectable_names or not self.selectable_names <= set(self.names):
            raise ValueError("Merge TUI requires one readable Source.")
        if self.selected_source not in self.selectable_names:
            raise ValueError("Initial Merge Source is unavailable.")
        if not isinstance(self.target_context, str) or not self.target_context:
            raise ValueError("Merge TUI requires one frozen Target Context.")
        if self.target_context == self.selected_source:
            raise ValueError("Merge Source and Target must be distinct.")
        if type(self.initial_recursive) is not bool:
            raise TypeError("Merge TUI recursive state must be a boolean.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Merge TUI annotations are outside the catalog.")
