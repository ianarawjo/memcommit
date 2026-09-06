"""Operation-neutral values exchanged by History projections and controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from prompt_toolkit.formatted_text.base import StyleAndTextTuples


@runtime_checkable
class HistoryPickerItem(Protocol):
    """Minimal projection a checkpoint or semantic Log adapter must provide."""

    uid: str
    timestamp: str
    command: str
    description: str
    detail: str


@dataclass(frozen=True)
class HistoryPickerEntry:
    """Validated built-in implementation of :class:`HistoryPickerItem`."""

    uid: str
    timestamp: str
    command: str
    description: str
    detail: str

    def __post_init__(self) -> None:
        for label, value in (
            ("history UID", self.uid),
            ("history timestamp", self.timestamp),
            ("history command", self.command),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{label} must be non-empty text.")
        if not isinstance(self.description, str):
            raise ValueError("history description must be text.")
        if not isinstance(self.detail, str):
            raise ValueError("history detail must be text.")


@dataclass(frozen=True)
class HistoryDetailView:
    """Rendered detail plus logical line anchors for navigable change units."""

    content: str | StyleAndTextTuples
    unit_start_lines: tuple[int, ...]
    unit_label: str = "CHANGE"

    def __post_init__(self) -> None:
        if not isinstance(self.content, (str, list, tuple)):
            raise ValueError("History detail content must be renderable text.")
        if not self.unit_label or "\n" in self.unit_label:
            raise ValueError("History detail unit label must be one non-empty line.")
        if any(
            not isinstance(line, int) or isinstance(line, bool) or line < 0
            for line in self.unit_start_lines
        ):
            raise ValueError("History detail unit anchors must be line indexes.")
        if tuple(sorted(set(self.unit_start_lines))) != self.unit_start_lines:
            raise ValueError("History detail unit anchors must be strictly increasing.")


@dataclass(frozen=True)
class HistoryBackNavigation:
    """Read-only receipt requesting return to the owning previous screen."""


HISTORY_BACK = HistoryBackNavigation()


HistoryDetailContent = str | StyleAndTextTuples | HistoryDetailView
HistoryDetailRenderer = Callable[[HistoryPickerItem], HistoryDetailContent]
