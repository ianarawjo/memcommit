"""Typed setup for interactive snapshot Reference."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class ReferenceTuiSetup:
    """Freeze local Context roles and the wider authorized Memory Source role."""

    # ``names`` remains the compatibility spelling for ordinary local Contexts.
    # Both Context Reference Source and every Target must stay inside it.
    names: tuple[str, ...]
    selected_source: str
    selected_target: str
    current_context: str | None = None
    memory_source_names: tuple[str, ...] = ()
    memory_source_selectable_names: frozenset[str] = frozenset()
    selected_memory_source: str | None = None
    memory_source_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

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
        if self.current_context is not None and self.current_context not in self.names:
            raise ValueError("Reference TUI current Context must be local.")

        memory_names = self.memory_source_names or self.names
        selectable = self.memory_source_selectable_names or frozenset(memory_names)
        selected_memory = self.selected_memory_source or self.selected_source
        if (
            not memory_names
            or len(set(memory_names)) != len(memory_names)
            or any(not isinstance(name, str) or not name for name in memory_names)
        ):
            raise ValueError("Reference TUI requires a Memory Source catalog.")
        if not set(self.names) <= set(memory_names):
            raise ValueError("Reference TUI Memory Sources must include local Contexts.")
        if not set(self.names) <= selectable or not selectable <= set(memory_names):
            raise ValueError("Reference TUI Memory Source authority is invalid.")
        if selected_memory not in selectable:
            raise ValueError("Reference TUI initial Memory Source is unavailable.")
        annotation_names = tuple(name for name, _value in self.memory_source_annotations)
        if (
            len(set(annotation_names)) != len(annotation_names)
            or not set(annotation_names) <= set(memory_names)
        ):
            raise ValueError("Reference TUI Memory Source annotations are invalid.")

        object.__setattr__(self, "memory_source_names", memory_names)
        object.__setattr__(self, "memory_source_selectable_names", selectable)
        object.__setattr__(self, "selected_memory_source", selected_memory)

    @property
    def context_source_names(self) -> tuple[str, ...]:
        """Return the ordinary local Context Reference Source catalog."""

        return self.names

    @property
    def target_names(self) -> tuple[str, ...]:
        """Return the ordinary local Reference Target catalog."""

        return self.names


__all__ = ["ReferenceTuiSetup"]
