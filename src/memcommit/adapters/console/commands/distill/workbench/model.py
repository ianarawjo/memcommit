"""Typed values owned by the Distill proposal workbench."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from memcommit.adapters.console.terminal.components.context_picker import (
    ContextMemoryRow,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.reach import (
    ContextReachViewMode,
)
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class DistillTuiSetup:
    """One frozen readable catalog and one-operation reach default."""

    names: tuple[str, ...]
    selected_context: str
    initial_range_mode: ContextReachViewMode = "EXACT"
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    source_locked: bool = False
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Distill TUI requires a distinct readable catalog.")
        if self.selected_context not in self.names:
            raise ValueError("The selected Distill Context is outside the catalog.")
        if self.initial_range_mode not in {"EXACT", "SUBTREE"}:
            raise ValueError("Distill TUI requires one exact reach mode.")
        if self.current_context is not None and self.current_context not in self.names:
            raise ValueError("The current Context is outside the Distill catalog.")
        if type(self.source_locked) is not bool:
            raise ValueError("Distill TUI source_locked must be boolean.")
        if self.memory_loader is not None and not callable(self.memory_loader):
            raise ValueError("Distill TUI Memory loader must be callable.")
        if self.source_locked and self.names != (self.selected_context,):
            raise ValueError("Fixed Distill requires only its selected Source Context.")


@dataclass(frozen=True)
class DistillClipboardProjection:
    text: str
    label: str

    def __post_init__(self) -> None:
        if not self.text or not self.label:
            raise ValueError("Distill clipboard projection must be nonblank.")
