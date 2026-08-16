"""Typed values for a Context-scoped semantic result workbench."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.context_targeting.tui.reach import ContextReachViewMode
from memcommit.interfaces.tui.viewers.semantic import SemanticViewerDocument
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class ContextSummaryWorkbenchView:
    """Caller-authored labels and frozen process-local workbench state."""

    names: tuple[str, ...]
    selected_context: str
    range_mode: ContextReachViewMode
    operation_label: str
    result_title: str
    empty_message: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    document: SemanticViewerDocument | None = None
    allow_both: bool = True
    targeting_editable: bool = True

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Context workbench requires a distinct catalog.")
        if self.selected_context not in self.names:
            raise ValueError("The selected Context is outside the workbench catalog.")
        if self.current_context is not None and self.current_context not in self.names:
            raise ValueError("The current Context is outside the workbench catalog.")
        if self.range_mode not in {"BOTH", "EXACT", "SUBTREE"}:
            raise ValueError("Context workbench range mode is invalid.")
        if type(self.allow_both) is not bool:
            raise ValueError("Context workbench allow_both must be boolean.")
        if type(self.targeting_editable) is not bool:
            raise ValueError("Context workbench targeting_editable must be boolean.")
        if not self.allow_both and self.range_mode == "BOTH":
            raise ValueError("This Context workbench requires one reach mode.")
        if not self.targeting_editable and self.names != (self.selected_context,):
            raise ValueError(
                "A locked Context workbench requires only its selected Context."
            )
        if not self.operation_label.strip() or not self.result_title.strip():
            raise ValueError("Context workbench labels must be nonblank.")
        if not self.empty_message.strip():
            raise ValueError("Context workbench empty guidance must be nonblank.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Context workbench annotations are outside the catalog.")


@dataclass(frozen=True)
class ContextSummaryWorkbenchReceipt:
    """Explicit process-local Context and reach selection."""

    context_name: str
    range_mode: ContextReachViewMode

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name:
            raise ValueError("Context workbench receipt requires one Context.")
        if self.range_mode not in {"BOTH", "EXACT", "SUBTREE"}:
            raise ValueError("Context workbench receipt range is invalid.")
