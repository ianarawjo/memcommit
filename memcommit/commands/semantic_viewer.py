"""Shared focus presentation for section-oriented terminal viewers.

This module owns the visual and viewport meaning of one semantic Viewer stop.
Callers still own section identity, semantic content, nested actions, and every
operation boundary.  Keeping those responsibilities separate lets Compare,
Result, Resolution, and small inspection viewers share one focus grammar
without pretending that they share one result or review model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from memcommit.session_workbench_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchSection,
)


ViewerAnchor = Literal["start", "end", "both"]
ViewerFragments = Sequence[tuple[str, str]]


# A focused Viewer stop changes only semantic identity fragments. Explanatory
# prose remains neutral, while a Memory may temporarily replace its resting
# lavender with the common blue focus treatment. Nested choices retain their
# separate underline grammar.
_FOCUSED_STYLE = {
    "class:title": "class:viewer-section",
    "class:section": "class:viewer-section",
    "class:case-title": "class:viewer-section",
    "class:detail-heading": "class:viewer-section",
    "class:block-heading": "class:viewer-section",
    "class:detail-card": "class:detail-card.focused",
    "class:memory-object": "class:memory-object.focused",
    "class:impact.keep": "class:impact.keep.focused",
    "class:impact.redact": "class:impact.redact.focused",
    "class:impact.summarize": "class:impact.summarize.focused",
    "class:impact.reframe": "class:impact.reframe.focused",
    "class:impact.forget": "class:impact.forget.focused",
    "class:impact.custom": "class:impact.custom.focused",
    "class:impact.other": "class:impact.other.focused",
    "class:impact.edit": "class:impact.edit.focused",
    "class:impact.add": "class:impact.add.focused",
    "class:impact.remove": "class:impact.remove.focused",
    "class:option-card": "class:option-card.focused",
}

_RESTING_STYLE = {
    # Several heading roles intentionally converge on the same blue focus
    # style. Once focus leaves Viewer they return to neutral section
    # chrome; the operation-specific heading role is not recoverable from
    # the focused class and is not semantically relevant while inactive.
    "class:viewer-section": "class:section",
    "class:detail-card.focused": "class:detail-card",
    "class:memory-object.focused": "class:memory-object",
    "class:impact.keep.focused": "class:impact.keep",
    "class:impact.redact.focused": "class:impact.redact",
    "class:impact.summarize.focused": "class:impact.summarize",
    "class:impact.reframe.focused": "class:impact.reframe",
    "class:impact.forget.focused": "class:impact.forget",
    "class:impact.custom.focused": "class:impact.custom",
    "class:impact.other.focused": "class:impact.other",
    "class:impact.edit.focused": "class:impact.edit",
    "class:impact.add.focused": "class:impact.add",
    "class:impact.remove.focused": "class:impact.remove",
    "class:option-card.focused": "class:option-card",
    "class:option-card.other": "class:option-card",
    "class:choice": "",
}


@dataclass(frozen=True)
class SemanticViewerBlock:
    """One independently focusable rendered block.

    ``focus_indices`` identifies the fragments that express this block's
    semantic identity.  When omitted, every fragment with a registered
    semantic style participates; neutral prose never becomes blue merely
    because it is inside the active block.
    """

    fragments: tuple[tuple[str, str], ...]
    anchor: ViewerAnchor = "start"
    focus_indices: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.anchor not in {"start", "end", "both"}:
            raise ValueError("Viewer anchor must be start, end, or both.")
        if self.focus_indices is not None and any(
            index < 0 or index >= len(self.fragments) for index in self.focus_indices
        ):
            raise ValueError("Viewer focus fragment index is out of range.")

    def render(
        self,
        *,
        active: bool,
        viewer_focused: bool = True,
    ) -> list[tuple[str, str]]:
        """Render one stop through the service-wide focus and anchor policy."""

        visibly_focused = active and viewer_focused
        fragments: list[tuple[str, str]] = []
        if visibly_focused and self.anchor in {"start", "both"}:
            fragments.append(("[SetCursorPosition]", ""))

        focus_indices = (
            set(self.focus_indices)
            if self.focus_indices is not None
            else {
                index
                for index, (style, _text) in enumerate(self.fragments)
                if style in _FOCUSED_STYLE
            }
        )
        for index, (style, text) in enumerate(self.fragments):
            if visibly_focused and index in focus_indices:
                style = _FOCUSED_STYLE.get(style, style)
            fragments.append((style, text))

        if visibly_focused and self.anchor in {"end", "both"}:
            fragments.append(("[SetCursorPosition]", ""))
        return fragments


@dataclass(frozen=True)
class SemanticViewerSection:
    """A stable navigation identity paired with its rendered Viewer block."""

    uid: str
    kind: str
    block: SemanticViewerBlock
    row_index: int | None = None

    def __post_init__(self) -> None:
        # Reuse the navigation model's validation at this presentation edge.
        WorkbenchSection(self.uid, self.kind, self.row_index)

    @property
    def navigation_section(self) -> WorkbenchSection:
        return WorkbenchSection(self.uid, self.kind, self.row_index)


@dataclass(frozen=True)
class SemanticViewerDocument:
    """An ordered section document rendered from the same stable identities.

    A caller no longer needs to parse its finished report text once it has
    projected this document. The navigation sequence and rendered block order
    are two views of the same immutable structure.
    """

    sections: tuple[SemanticViewerSection, ...]

    def __post_init__(self) -> None:
        uids = tuple(section.uid for section in self.sections)
        if len(set(uids)) != len(uids):
            raise ValueError("Semantic Viewer section identities must be unique.")

    @property
    def navigation_sections(self) -> tuple[WorkbenchSection, ...]:
        return tuple(section.navigation_section for section in self.sections)

    def render(
        self,
        *,
        focused_uid: str | None,
        viewer_focused: bool = True,
    ) -> list[tuple[str, str]]:
        if not self.sections:
            return []
        available = {section.uid for section in self.sections}
        active_uid = focused_uid if focused_uid in available else self.sections[0].uid
        fragments: list[tuple[str, str]] = []
        for section in self.sections:
            fragments.extend(
                section.block.render(
                    active=section.uid == active_uid,
                    viewer_focused=viewer_focused,
                )
            )
        return fragments


@dataclass
class SemanticViewerController:
    """Apply the shared focus grammar to operation-authored Viewer sections.

    Operations remain responsible for declaring stable semantic sections.
    This controller owns how those sections are focused, moved, and rendered,
    so individual shells do not reproduce UID clamping and paging behavior.
    """

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
        """Enter one operation-neutral inner reading or choice layer."""

        if not section_uid:
            raise ValueError("A nested Viewer layer requires a section uid.")
        self.nested_uid = section_uid
        self.nested_index = max(0, index)

    def close_nested(self) -> bool:
        """Close the inner layer and report whether one was active."""

        if self.nested_uid is None:
            return False
        self.nested_uid = None
        self.nested_index = 0
        return True

    def move_nested(self, size: int, delta: int) -> int:
        """Move inside the active semantic block without changing its UID."""

        if self.nested_uid is None or size <= 0:
            return self.nested_index
        self.nested_index = max(0, min(self.nested_index + delta, size - 1))
        return self.nested_index


def semantic_viewer_block_fragments(
    fragments: ViewerFragments,
    *,
    active: bool,
    viewer_focused: bool = True,
    anchor: ViewerAnchor = "start",
    focus_indices: tuple[int, ...] | None = None,
) -> list[tuple[str, str]]:
    """Render a block without making the caller reproduce focus mechanics."""

    return SemanticViewerBlock(
        tuple(fragments),
        anchor=anchor,
        focus_indices=focus_indices,
    ).render(active=active, viewer_focused=viewer_focused)


def deactivate_semantic_viewer_fragments(
    fragments: ViewerFragments,
) -> list[tuple[str, str]]:
    """Remove positional emphasis while retaining durable selection styles.

    Hidden cursor anchors are deliberately preserved. They keep the inactive
    Viewer at its last semantic reading position without presenting that
    position as the current keyboard target.
    """

    return [(_RESTING_STYLE.get(style, style), text) for style, text in fragments]
