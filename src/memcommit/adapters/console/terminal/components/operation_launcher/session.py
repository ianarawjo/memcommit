"""Saved-session adapter for the operation-neutral launcher."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, TypeAlias

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.operation_launcher.model import (
    LauncherAction,
    LauncherActionSelection,
    LauncherEntry,
    LauncherEntrySelection,
    LauncherOrientation,
    OperationLauncherSpec,
)
from memcommit.adapters.console.terminal.components.operation_launcher.screen import (
    _compact,
    _grouped_line_count,
    _ordered_entries,
    _render_detail,
    _render_entry_line,
    _render_location as _render_launcher_location,
    _visible_bounds,
    _visible_grouped_bounds,
    run_operation_launcher,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text


SessionSortMode = Literal["recent", "name"]
SessionGroupMode = Literal["all", "context"]


def _validate_argv(value: tuple[str, ...], *, label: str) -> None:
    if (
        not isinstance(value, tuple)
        or not value
        or any(not isinstance(argument, str) for argument in value)
        or not value[0]
    ):
        raise ValueError(f"{label} must be a non-empty tuple of text arguments.")


@dataclass(frozen=True)
class SessionPickerEntry:
    """Session projection translated to a neutral launcher row."""

    kind: str
    key: str
    title: str
    status: str
    subtitle: str
    group: str
    sort_timestamp: float
    detail: str
    reopen_argv: tuple[str, ...]
    detail_only: bool = False

    def __post_init__(self) -> None:
        for label, value in (
            ("session kind", self.kind),
            ("session key", self.key),
            ("session title", self.title),
            ("session status", self.status),
            ("session group", self.group),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{label} must be non-empty text.")
        for label, value in (
            ("session subtitle", self.subtitle),
            ("session detail", self.detail),
        ):
            if not isinstance(value, str):
                raise ValueError(f"{label} must be text.")
        if not isinstance(self.detail_only, bool):
            raise ValueError("session detail-only mode must be boolean.")
        if (
            isinstance(self.sort_timestamp, bool)
            or not isinstance(self.sort_timestamp, (int, float))
            or not math.isfinite(self.sort_timestamp)
        ):
            raise ValueError("session sort timestamp must be finite numeric time.")
        try:
            datetime.fromtimestamp(self.sort_timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError(
                "session sort timestamp must be renderable UTC time."
            ) from error
        _validate_argv(self.reopen_argv, label="session reopen argv")

    def launcher_entry(self) -> LauncherEntry:
        return LauncherEntry(
            kind=self.kind,
            key=self.key,
            title=self.title,
            status=self.status,
            subtitle=self.subtitle,
            group=self.group,
            sort_timestamp=self.sort_timestamp,
            detail=self.detail,
            detail_only=self.detail_only,
        )


@dataclass(frozen=True)
class SessionOpenReceipt:
    """Exact adapter-owned receipt for reopening one frozen session."""

    kind: str
    key: str
    argv: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("open receipt kind must be non-empty text.")
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("open receipt key must be non-empty text.")
        _validate_argv(self.argv, label="open receipt argv")


@dataclass(frozen=True)
class SessionNewReceipt:
    """Exact adapter-owned receipt for leaving the launcher through New."""

    kind: str
    argv: tuple[str, ...]
    action_label: str | None = None
    action_description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("new receipt kind must be non-empty text.")
        _validate_argv(self.argv, label="new receipt argv")
        for label, value in (
            ("new receipt action label", self.action_label),
            ("new receipt action description", self.action_description),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or any(character in value for character in "\r\n")
            ):
                raise ValueError(f"{label} must be non-empty single-line text.")

    def launcher_action(self) -> LauncherAction:
        operation = self.kind.replace("_", " ").replace("-", " ").title()
        return LauncherAction(
            uid="session-new",
            label=self.action_label or f"Add new {operation} session",
            description=(
                self.action_description
                or "Leave saved-session browsing and enter operation-specific setup."
            ),
        )


SessionPickerReceipt: TypeAlias = SessionOpenReceipt | SessionNewReceipt


@dataclass(frozen=True)
class SessionPickerLocation:
    """Frozen Store orientation projected into neutral launcher rows."""

    profile_name: str
    store_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.profile_name, str) or not self.profile_name:
            raise ValueError("session picker profile name must be non-empty text.")
        if not isinstance(self.store_path, str) or not self.store_path:
            raise ValueError("session picker store path must be non-empty text.")

    def launcher_orientation(self) -> LauncherOrientation:
        return LauncherOrientation(
            rows=(("PROFILE", self.profile_name), ("STORE", self.store_path))
        )


def _new_session_label(receipt: SessionNewReceipt) -> str:
    """Compatibility projection of the adapter-owned pinned action label."""

    return display_escape_text(receipt.launcher_action().label)


def _render_new_detail(receipt: SessionNewReceipt) -> str:
    action = receipt.launcher_action()
    return "\n".join(
        (
            f" {_new_session_label(receipt)}",
            f" {display_escape_text(action.description)}",
        )
    )


def _render_location(location: SessionPickerLocation) -> str:
    return _render_launcher_location(location.launcher_orientation())


def choose_session(
    entries: Sequence[SessionPickerEntry],
    *,
    title: str,
    new_receipt: SessionNewReceipt | None = None,
    location: SessionPickerLocation | None = None,
    initial_sort_mode: SessionSortMode = "recent",
    initial_group_mode: SessionGroupMode = "all",
    catalog_label: str = "saved sessions",
    enter_action: str = "open",
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SessionPickerReceipt | None:
    """Adapt session receipts around the operation-neutral launcher."""

    options = tuple(entries)
    if not isinstance(title, str) or not title:
        raise ValueError("Session picker title must be non-empty text.")
    if any(not isinstance(entry, SessionPickerEntry) for entry in options):
        raise ValueError("Session picker received an invalid entry.")
    identities = tuple((entry.kind, entry.key) for entry in options)
    if len(set(identities)) != len(identities):
        raise ValueError("Session picker received duplicate kind/key entries.")
    if new_receipt is not None and not isinstance(new_receipt, SessionNewReceipt):
        raise ValueError("Session picker received an invalid new receipt.")
    if location is not None and not isinstance(location, SessionPickerLocation):
        raise ValueError("Session picker received an invalid location.")
    if initial_sort_mode not in ("recent", "name"):
        raise ValueError("Session picker received an invalid initial sort mode.")
    if initial_group_mode not in ("all", "context"):
        raise ValueError("Session picker received an invalid initial group mode.")
    if (
        not isinstance(catalog_label, str)
        or not catalog_label
        or any(character in catalog_label for character in "\r\n")
    ):
        raise ValueError("Session picker catalog label must be non-empty text.")
    if (
        not isinstance(enter_action, str)
        or not enter_action
        or any(character in enter_action for character in "\r\n")
    ):
        raise ValueError(
            "Session picker Enter action must be non-empty single-line text."
        )

    selection = run_operation_launcher(
        OperationLauncherSpec(
            title=title,
            entries=tuple(entry.launcher_entry() for entry in options),
            action=(
                new_receipt.launcher_action() if new_receipt is not None else None
            ),
            orientation=(
                location.launcher_orientation() if location is not None else None
            ),
            initial_sort_mode=initial_sort_mode,
            initial_group_mode=initial_group_mode,
            catalog_label=catalog_label,
            enter_action=enter_action,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if selection is None:
        return None
    if isinstance(selection, LauncherActionSelection):
        if new_receipt is None or selection.uid != "session-new":
            raise RuntimeError("Session launcher returned an unknown action.")
        return new_receipt
    if not isinstance(selection, LauncherEntrySelection):
        raise RuntimeError("Session launcher returned an invalid selection.")
    matching = tuple(
        entry
        for entry in options
        if (entry.kind, entry.key) == (selection.kind, selection.key)
    )
    if len(matching) != 1:
        raise RuntimeError("Session launcher returned an unknown entry.")
    entry = matching[0]
    return SessionOpenReceipt(
        kind=entry.kind,
        key=entry.key,
        argv=entry.reopen_argv,
    )


__all__ = [
    "SessionGroupMode",
    "SessionNewReceipt",
    "SessionOpenReceipt",
    "SessionPickerEntry",
    "SessionPickerLocation",
    "SessionPickerReceipt",
    "SessionSortMode",
    "_compact",
    "_grouped_line_count",
    "_new_session_label",
    "_ordered_entries",
    "_render_detail",
    "_render_entry_line",
    "_render_location",
    "_render_new_detail",
    "_visible_bounds",
    "_visible_grouped_bounds",
    "choose_session",
]
