"""Frozen readable Source catalog for interactive Merge."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class MergeTuiSetup:
    """Process-local readable Source and writable Target choices."""

    names: tuple[str, ...]
    selectable_names: frozenset[str]
    selected_source: str
    target_names: tuple[str, ...]
    target_selectable_names: frozenset[str]
    target_context: str
    initial_recursive: bool = False
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    target_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

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
        if (
            not self.target_names
            or len(set(self.target_names)) != len(self.target_names)
            or any(
                not isinstance(name, str) or not name for name in self.target_names
            )
        ):
            raise ValueError("Merge TUI requires a distinct Target catalog.")
        if (
            not self.target_selectable_names
            or not self.target_selectable_names <= set(self.target_names)
        ):
            raise ValueError("Merge TUI requires one CREATE-authorized Target.")
        if self.target_context not in self.target_selectable_names:
            raise ValueError("Initial Merge Target is unavailable.")
        if type(self.initial_recursive) is not bool:
            raise TypeError("Merge TUI recursive state must be a boolean.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Merge TUI annotations are outside the catalog.")
        target_labels = dict(self.target_annotations)
        if len(target_labels) != len(self.target_annotations) or set(
            target_labels
        ) - set(self.target_names):
            raise ValueError("Merge TUI Target annotations are outside the catalog.")
