"""Typed setup and process-local draft state for interactive Add."""

from __future__ import annotations

from dataclasses import dataclass, field

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class AddWorkbenchSetup:
    """Frozen target catalog supplied by the Add composition boundary."""

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
            raise ValueError(
                "Add workbench requires a distinct nonempty target catalog."
            )
        if not self.selectable_names or not self.selectable_names <= set(self.names):
            raise ValueError("Add workbench requires at least one selectable target.")
        if self.selected_context not in self.selectable_names:
            raise ValueError("Initial Add target is unavailable.")


@dataclass
class AddDraftState:
    """One ordered batch with a read state and an explicit edit mode."""

    drafts: list[str | None] = field(default_factory=lambda: [None])
    cursor: int = 0
    editing: int | None = None
    _editing_new: bool = False

    def __post_init__(self) -> None:
        if not self.drafts:
            raise ValueError("Add draft state requires one placeholder.")
        if not 0 <= self.cursor < len(self.drafts):
            raise ValueError("Add draft cursor is outside the batch.")
        for content in self.drafts:
            if content is not None and (
                not isinstance(content, str) or not content.strip()
            ):
                raise ValueError("Saved Add drafts must contain nonblank text.")

    @property
    def selected(self) -> str | None:
        return self.drafts[self.cursor]

    @property
    def ready_contents(self) -> tuple[str, ...]:
        return tuple(content for content in self.drafts if content is not None)

    def move(self, delta: int) -> bool:
        if delta not in {-1, 1} or self.editing is not None:
            return False
        candidate = max(0, min(self.cursor + delta, len(self.drafts) - 1))
        if candidate == self.cursor:
            return False
        self.cursor = candidate
        return True

    def begin_edit(self) -> str:
        if self.editing is not None:
            raise ValueError("A draft is already being edited.")
        self.editing = self.cursor
        self._editing_new = self.selected is None
        return self.selected or ""

    def new(self) -> str:
        if self.editing is not None:
            raise ValueError("Finish the current draft before adding another.")
        self.drafts.append(None)
        self.cursor = len(self.drafts) - 1
        self.editing = self.cursor
        self._editing_new = True
        return ""

    def save_edit(self, content: str) -> None:
        if self.editing is None:
            raise ValueError("No Add draft is being edited.")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("A Memory must contain nonblank text.")
        self.drafts[self.editing] = content
        self.cursor = self.editing
        self.editing = None
        self._editing_new = False

    def cancel_edit(self) -> None:
        if self.editing is None:
            return
        index = self.editing
        if self._editing_new and self.drafts[index] is None and len(self.drafts) > 1:
            del self.drafts[index]
            self.cursor = min(index, len(self.drafts) - 1)
        self.editing = None
        self._editing_new = False

    def delete_selected(self) -> None:
        if self.editing is not None:
            raise ValueError("Finish the current edit before deleting a draft.")
        if len(self.drafts) == 1:
            self.drafts[0] = None
            self.cursor = 0
            return
        del self.drafts[self.cursor]
        self.cursor = min(self.cursor, len(self.drafts) - 1)
