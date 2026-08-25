"""Trace/Rationale adapter over the shared Read Report recent lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.interfaces.tui.components.operation_launcher.location import (
    operation_launcher_orientation,
)
from memcommit.interfaces.tui.workbenches.read_report import (
    ReadReportSelectTarget,
    choose_read_report_recent,
)
from memcommit.read_report import ReadReportError, ReadReportTarget
from memcommit.read_report_recents import (
    read_report_recents,
    revalidate_read_report_recent,
)
from memcommit.store import MemoryStore


MemoryReportOperation = Literal["trace", "rationale"]


class MemoryReportRecentError(ValueError):
    """A recent Memory report cannot be trusted or reopened."""


@dataclass(frozen=True)
class MemoryReportRecent:
    attempt_uid: str
    operation: MemoryReportOperation
    context_name: str
    memory_uid: str
    include_descendants: bool
    started_at: str


@dataclass(frozen=True)
class MemoryReportRecentSelection:
    context_name: str
    memory_uid: str
    include_descendants: bool


@dataclass(frozen=True)
class MemoryReportSelectAction:
    """Request the normal common Context/Memory selector."""


def _memory_recent(recent) -> MemoryReportRecent:
    target = recent.target
    if target.memory_uid is None or len(target.context_names) != 1:
        raise MemoryReportRecentError("Recent Memory report metadata is invalid.")
    return MemoryReportRecent(
        attempt_uid=recent.attempt_uid,
        operation=target.operation,  # type: ignore[arg-type]
        context_name=target.context_names[0],
        memory_uid=target.memory_uid,
        include_descendants=target.include_descendants,
        started_at=recent.started_at,
    )


def memory_report_recents(
    store: MemoryStore,
    *,
    operation: MemoryReportOperation,
    limit: int = 20,
) -> tuple[MemoryReportRecent, ...]:
    """Retain the legacy typed projection while using shared Recents storage."""

    try:
        return tuple(
            _memory_recent(recent)
            for recent in read_report_recents(
                store,
                operation=operation,
                limit=limit,
            )
        )
    except ReadReportError as error:
        raise MemoryReportRecentError(str(error)) from error


def choose_memory_report_recent(
    store: MemoryStore,
    *,
    operation: MemoryReportOperation,
) -> MemoryReportRecentSelection | MemoryReportSelectAction | None:
    """Choose and revalidate a shared content-free recent Memory target."""

    try:
        recents = read_report_recents(store, operation=operation)
        selected = choose_read_report_recent(
            recents,
            operation=operation,
            orientation=operation_launcher_orientation(store),
        )
        if selected is None:
            return None
        if isinstance(selected, ReadReportSelectTarget):
            return MemoryReportSelectAction()
        if not isinstance(selected, ReadReportTarget):
            raise MemoryReportRecentError(
                "Memory report launcher returned an invalid selection."
            )
        matching = next(
            (recent for recent in recents if recent.target == selected),
            None,
        )
        if matching is None:
            raise MemoryReportRecentError(
                "Memory report launcher returned an unknown selection."
            )
        target = revalidate_read_report_recent(store, matching)
    except ReadReportError as error:
        raise MemoryReportRecentError(str(error)) from error
    if target.memory_uid is None or len(target.context_names) != 1:
        raise MemoryReportRecentError("Recent Memory report target is invalid.")
    return MemoryReportRecentSelection(
        context_name=target.context_names[0],
        memory_uid=target.memory_uid,
        include_descendants=target.include_descendants,
    )
