"""Typed setup state for interactive Embed."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class EmbedTuiSetup:
    """Frozen source authority and owned-target catalogs for one TUI launch."""

    child_names: tuple[str, ...]
    child_selectable_names: frozenset[str]
    into_names: tuple[str, ...]
    memory_source_names: tuple[str, ...]
    memory_source_selectable_names: frozenset[str]
    memory_source_granted_names: frozenset[str]
    current_context: str | None = None
    child_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    memory_source_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if not self.into_names:
            raise ValueError("Interactive Embed requires one owned target Context.")
        if not self.child_selectable_names:
            raise ValueError("Interactive Embed requires one authorized Child Context.")
        if not self.memory_source_names:
            raise ValueError("Interactive Embed requires one Memory Source catalog.")
        if not self.memory_source_selectable_names:
            raise ValueError("Interactive Embed requires one authorized Memory Source.")
        if (
            len(set(self.child_names)) != len(self.child_names)
            or len(set(self.into_names)) != len(self.into_names)
            or len(set(self.memory_source_names)) != len(self.memory_source_names)
        ):
            raise ValueError("Interactive Embed requires distinct Context catalogs.")
        if not self.child_selectable_names <= set(self.child_names):
            raise ValueError("Embed Child selection is outside its visible catalog.")
        if not self.memory_source_selectable_names <= set(self.memory_source_names):
            raise ValueError(
                "Embed Memory Source selection is outside its visible catalog."
            )
        if not self.memory_source_granted_names <= self.memory_source_selectable_names:
            raise ValueError("Granted Memory Sources must be authorized for this role.")
        if any(
            not isinstance(name, str) or not name
            for name in (
                *self.child_names,
                *self.into_names,
                *self.memory_source_names,
            )
        ):
            raise ValueError("Embed TUI Context names must be nonempty text.")
        if (
            self.current_context is not None
            and self.current_context not in self.into_names
        ):
            raise ValueError("Embed TUI current Context is outside owned targets.")
        for catalog_annotations, names, label in (
            (self.child_annotations, self.child_names, "Child"),
            (
                self.memory_source_annotations,
                self.memory_source_names,
                "Memory Source",
            ),
        ):
            annotation_names = tuple(name for name, _annotation in catalog_annotations)
            if len(set(annotation_names)) != len(annotation_names) or not set(
                annotation_names
            ) <= set(names):
                raise ValueError(f"Embed {label} annotations are invalid.")
