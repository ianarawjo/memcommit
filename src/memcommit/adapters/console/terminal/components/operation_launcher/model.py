"""Typed, operation-neutral values for the terminal launcher."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, TypeAlias


LauncherSortMode = Literal["recent", "name"]
LauncherGroupMode = Literal["all", "context"]


def _one_line(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(character in value for character in "\r\n")
    ):
        raise ValueError(f"Launcher {label} must be non-empty one-line text.")
    return value


@dataclass(frozen=True)
class LauncherEntry:
    """One frozen catalog row; it carries no executable receipt."""

    kind: str
    key: str
    title: str
    status: str
    subtitle: str
    group: str
    sort_timestamp: float
    detail: str
    detail_only: bool = False

    def __post_init__(self) -> None:
        for label, value in (
            ("entry kind", self.kind),
            ("entry key", self.key),
            ("entry title", self.title),
            ("entry status", self.status),
            ("entry group", self.group),
        ):
            _one_line(value, label)
        for label, value in (
            ("entry subtitle", self.subtitle),
            ("entry detail", self.detail),
        ):
            if not isinstance(value, str):
                raise ValueError(f"Launcher {label} must be text.")
        if not isinstance(self.detail_only, bool):
            raise TypeError("Launcher detail-only mode must be a boolean.")
        if (
            isinstance(self.sort_timestamp, bool)
            or not isinstance(self.sort_timestamp, (int, float))
            or not math.isfinite(self.sort_timestamp)
        ):
            raise ValueError("Launcher sort timestamp must be finite numeric time.")
        try:
            datetime.fromtimestamp(self.sort_timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError(
                "Launcher sort timestamp must be renderable UTC time."
            ) from error


@dataclass(frozen=True)
class LauncherAction:
    """One pinned non-entry action such as New or Select Context."""

    uid: str
    label: str
    description: str

    def __post_init__(self) -> None:
        _one_line(self.uid, "action uid")
        # Labels and descriptions are untrusted display content and are escaped
        # exactly once by the renderer. Only the opaque action UID is syntax.
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("Launcher action label must be non-empty text.")
        if not isinstance(self.description, str) or not self.description:
            raise ValueError("Launcher action description must be non-empty text.")


@dataclass(frozen=True)
class LauncherOrientation:
    """Frozen human orientation rendered above the catalog."""

    rows: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple) or not self.rows:
            raise ValueError("Launcher orientation requires at least one row.")
        for label, value in self.rows:
            _one_line(label, "orientation label")
            # Orientation values are untrusted metadata. They may contain
            # controls because the renderer escapes them; rejecting them here
            # would make the presentation component an authority boundary.
            if not isinstance(value, str) or not value:
                raise ValueError(
                    "Launcher orientation value must be non-empty text."
                )


@dataclass(frozen=True)
class LauncherEntrySelection:
    """Identity of one selected frozen catalog entry."""

    kind: str
    key: str

    def __post_init__(self) -> None:
        _one_line(self.kind, "selected entry kind")
        _one_line(self.key, "selected entry key")


@dataclass(frozen=True)
class LauncherActionSelection:
    """Identity of one selected pinned action."""

    uid: str

    def __post_init__(self) -> None:
        _one_line(self.uid, "selected action uid")


LauncherSelection: TypeAlias = LauncherEntrySelection | LauncherActionSelection


@dataclass(frozen=True)
class OperationLauncherSpec:
    """Complete presentation contract for one launcher invocation."""

    title: str
    entries: tuple[LauncherEntry, ...]
    action: LauncherAction | None = None
    orientation: LauncherOrientation | None = None
    initial_sort_mode: LauncherSortMode = "recent"
    initial_group_mode: LauncherGroupMode = "all"
    catalog_label: str = "entries"
    enter_action: str = "open"

    def __post_init__(self) -> None:
        _one_line(self.title, "title")
        if not isinstance(self.entries, tuple) or any(
            not isinstance(entry, LauncherEntry) for entry in self.entries
        ):
            raise TypeError("Launcher entries must be a tuple of LauncherEntry.")
        identities = tuple((entry.kind, entry.key) for entry in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("Launcher entries repeat a kind/key identity.")
        if self.action is not None and not isinstance(self.action, LauncherAction):
            raise TypeError("Launcher action is invalid.")
        if self.orientation is not None and not isinstance(
            self.orientation, LauncherOrientation
        ):
            raise TypeError("Launcher orientation is invalid.")
        if self.initial_sort_mode not in ("recent", "name"):
            raise ValueError("Launcher initial sort mode is invalid.")
        if self.initial_group_mode not in ("all", "context"):
            raise ValueError("Launcher initial group mode is invalid.")
        _one_line(self.catalog_label, "catalog label")
        _one_line(self.enter_action, "Enter action")


__all__ = [
    "LauncherAction",
    "LauncherActionSelection",
    "LauncherEntry",
    "LauncherEntrySelection",
    "LauncherGroupMode",
    "LauncherOrientation",
    "LauncherSelection",
    "LauncherSortMode",
    "OperationLauncherSpec",
]
