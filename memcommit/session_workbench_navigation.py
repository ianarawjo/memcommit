"""Shared focus and semantic scrolling state for session workbenches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


WorkbenchPane = Literal["items", "viewer", "todo", "composer"]


@dataclass(frozen=True)
class WorkbenchSection:
    """One stable semantic stop in a Viewer, independent of its list offset."""

    uid: str
    kind: str
    row_index: int | None = None

    def __post_init__(self) -> None:
        if not self.uid.strip() or not self.kind.strip():
            raise ValueError("Workbench section identity must be nonempty.")
        if self.row_index is not None and self.row_index < 0:
            raise ValueError("Workbench section row index cannot be negative.")


@dataclass
class SessionWorkbenchNavigation:
    """Operation-neutral Items/Viewer focus and semantic scroll controller."""

    # The report is the primary reading surface. Pickers that intentionally
    # start from a selectable row opt into Items explicitly.
    pane: WorkbenchPane = "viewer"
    row_index: int = 0
    viewer_row_index: int = 0
    section_uid: str | None = None

    def __post_init__(self) -> None:
        if self.pane not in {"items", "viewer", "todo", "composer"}:
            raise ValueError("Unsupported workbench pane.")
        if self.row_index < 0 or self.viewer_row_index < 0:
            raise ValueError("Workbench row indices cannot be negative.")

    def focus(self, pane: WorkbenchPane) -> None:
        if pane not in {"items", "viewer", "todo", "composer"}:
            raise ValueError("Unsupported workbench pane.")
        self.pane = pane

    def toggle_frames(self) -> WorkbenchPane:
        """Toggle only the two durable reading frames."""
        self.pane = "viewer" if self.pane == "items" else "items"
        return self.pane

    def cycle_panes(
        self,
        panes: Sequence[WorkbenchPane],
        delta: int = 1,
    ) -> WorkbenchPane:
        """Cycle one shell's visible panes without inventing hidden targets."""

        values = tuple(panes)
        if not values or len(set(values)) != len(values) or "composer" in values:
            raise ValueError("Session pane cycle must contain distinct visible panes.")
        index = values.index(self.pane) if self.pane in values else 0
        self.pane = values[(index + delta) % len(values)]
        return self.pane

    def move_row(self, row_count: int, delta: int) -> int:
        if row_count < 0:
            raise ValueError("Workbench row count cannot be negative.")
        if row_count == 0:
            self.row_index = 0
        else:
            self.row_index = max(0, min(self.row_index + delta, row_count - 1))
        return self.row_index

    def preview_selected_row(self) -> int:
        """Project the selected Items row into Viewer without moving focus."""

        self.viewer_row_index = self.row_index
        self.section_uid = None
        return self.viewer_row_index

    def bind_sections(self, sections: Sequence[WorkbenchSection]) -> int:
        """Preserve the selected semantic section across projection changes."""
        if not sections:
            self.section_uid = None
            return 0
        uids = tuple(section.uid for section in sections)
        if len(set(uids)) != len(uids):
            raise ValueError("Workbench section identities must be unique.")
        if self.section_uid not in uids:
            self.section_uid = uids[0]
        return uids.index(self.section_uid)

    def section_index(self, sections: Sequence[WorkbenchSection]) -> int:
        return self.bind_sections(sections)

    def move_section(
        self,
        sections: Sequence[WorkbenchSection],
        delta: int,
    ) -> WorkbenchSection | None:
        if not sections:
            self.section_uid = None
            return None
        index = self.bind_sections(sections)
        index = max(0, min(index + delta, len(sections) - 1))
        self.section_uid = sections[index].uid
        return sections[index]

    def focus_section(
        self,
        sections: Sequence[WorkbenchSection],
        *,
        kind: str,
        last: bool = False,
    ) -> WorkbenchSection:
        matches = [section for section in sections if section.kind == kind]
        if not matches:
            raise ValueError(f"Workbench section kind '{kind}' is unavailable.")
        section = matches[-1] if last else matches[0]
        self.section_uid = section.uid
        self.pane = "viewer"
        return section

    def open_selected(
        self,
        sections: Sequence[WorkbenchSection] = (),
    ) -> None:
        self.viewer_row_index = self.row_index
        self.pane = "viewer"
        if sections:
            self.bind_sections(sections)
