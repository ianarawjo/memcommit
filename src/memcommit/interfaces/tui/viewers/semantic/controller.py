"""Shared section and nested-layer navigation for semantic viewers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.interfaces.tui.viewers.semantic.model import SemanticViewerDocument
from memcommit.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchSection,
)


@dataclass
class SemanticViewerController:
    """Apply the shared focus grammar to operation-authored Viewer sections."""

    navigation: SessionWorkbenchNavigation
    nested_uid: str | None = None
    nested_index: int = 0

    @staticmethod
    def _sections(
        source: SemanticViewerDocument | Sequence[WorkbenchSection],
    ) -> tuple[WorkbenchSection, ...]:
        if isinstance(source, SemanticViewerDocument):
            return source.navigation_sections
        return tuple(source)

    def index(
        self,
        source: SemanticViewerDocument | Sequence[WorkbenchSection],
    ) -> int:
        return self.navigation.section_index(self._sections(source))

    def current(
        self,
        source: SemanticViewerDocument | Sequence[WorkbenchSection],
    ) -> WorkbenchSection | None:
        sections = self._sections(source)
        if not sections:
            self.navigation.section_uid = None
            return None
        return sections[self.navigation.section_index(sections)]

    def move(
        self,
        source: SemanticViewerDocument | Sequence[WorkbenchSection],
        delta: int,
    ) -> WorkbenchSection | None:
        return self.navigation.move_section(self._sections(source), delta)

    def home(
        self,
        source: SemanticViewerDocument | Sequence[WorkbenchSection],
    ) -> WorkbenchSection | None:
        return self.move(source, -1_000_000)

    def end(
        self,
        source: SemanticViewerDocument | Sequence[WorkbenchSection],
    ) -> WorkbenchSection | None:
        return self.move(source, 1_000_000)

    def render(
        self,
        document: SemanticViewerDocument,
        *,
        viewer_focused: bool = True,
    ) -> list[tuple[str, str]]:
        current = self.current(document)
        return document.render(
            focused_uid=None if current is None else current.uid,
            viewer_focused=viewer_focused,
        )

    def open_nested(self, section_uid: str, *, index: int = 0) -> None:
        if not section_uid:
            raise ValueError("A nested Viewer layer requires a section uid.")
        self.nested_uid = section_uid
        self.nested_index = max(0, index)

    def close_nested(self) -> bool:
        if self.nested_uid is None:
            return False
        self.nested_uid = None
        self.nested_index = 0
        return True

    def move_nested(self, size: int, delta: int) -> int:
        if self.nested_uid is None or size <= 0:
            return self.nested_index
        self.nested_index = max(0, min(self.nested_index + delta, size - 1))
        return self.nested_index
