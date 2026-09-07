"""Typed document model for section-oriented semantic viewers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from memcommit.application.capabilities.reviewing.session_navigation import WorkbenchSection


ViewerAnchor = Literal["start", "end", "both"]
ViewerFragments = Sequence[tuple[str, str]]


_FOCUSED_STYLE = {
    "class:title": "class:viewer-section",
    "class:section": "class:viewer-section",
    "class:case-title": "class:viewer-section",
    "class:detail-heading": "class:viewer-section",
    "class:block-heading": "class:viewer-section",
    "class:finding-marker": "class:finding-marker.focused",
    "class:report-label": "class:report-label.focused",
    "class:viewer-body": "class:viewer-body.focused",
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


def _focused_style(style: str) -> str:
    """Apply the Viewer focus treatment to typed semantic and ordinary blocks."""

    tokens = style.split()
    if len(tokens) == 1 and tokens[0].startswith("class:semantic."):
        # Keep the resting role in the fragment so leaving Viewer can restore
        # it, while the keyboard target temporarily takes the common blue.
        return style + " class:viewer-section"
    if "class:finding-label" in tokens:
        return " ".join(
            "class:finding-label.focused"
            if token == "class:finding-label"
            else token
            for token in tokens
        )
    return _FOCUSED_STYLE.get(style, style)


@dataclass(frozen=True)
class SemanticViewerBlock:
    """One independently focusable rendered block."""

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
                if _focused_style(style) != style
            }
        )
        for index, (style, text) in enumerate(self.fragments):
            if visibly_focused and index in focus_indices:
                style = _focused_style(style)
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
        WorkbenchSection(self.uid, self.kind, self.row_index)

    @property
    def navigation_section(self) -> WorkbenchSection:
        return WorkbenchSection(self.uid, self.kind, self.row_index)


@dataclass(frozen=True)
class SemanticViewerDocument:
    """An ordered section document with stable navigation identities."""

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
