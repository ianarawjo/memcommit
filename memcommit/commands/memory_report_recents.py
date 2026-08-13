"""Shared recent-report launcher for Trace and Rationale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from memcommit.command_attempts import (
    CommandAttempt,
    CommandAttemptError,
    CommandAttemptLedger,
)
from memcommit.commands.ground_session_picker import session_picker_location
from memcommit.commands.session_picker import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.store import MemoryStore


MemoryReportOperation = Literal["trace", "rationale"]


class MemoryReportRecentError(ValueError):
    """A recent report receipt cannot be trusted or reopened."""


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


def _recent_from_attempt(
    attempt: CommandAttempt,
    *,
    operation: MemoryReportOperation,
) -> MemoryReportRecent | None:
    details = attempt.details.get("memory_report")
    if (
        attempt.status != "COMPLETED"
        or attempt.operation
        not in ({operation, "log"} if operation == "trace" else {operation})
        or not isinstance(details, dict)
        or details.get("operation") != operation
    ):
        return None
    context_name = details.get("context_name")
    memory_uid = details.get("memory_uid")
    if not isinstance(context_name, str) or not isinstance(memory_uid, str):
        raise MemoryReportRecentError("Recent report metadata is invalid.")
    include_descendants = details.get("include_descendants")
    if include_descendants is None:
        # Before range selection existed, Rationale was always subtree-scoped
        # and Trace was always exact. Preserve those historical receipts.
        include_descendants = operation == "rationale"
    if type(include_descendants) is not bool:
        raise MemoryReportRecentError("Recent report scope is invalid.")
    return MemoryReportRecent(
        attempt_uid=attempt.uid,
        operation=operation,
        context_name=context_name,
        memory_uid=memory_uid,
        include_descendants=include_descendants,
        started_at=attempt.started_at,
    )


def memory_report_recents(
    store: MemoryStore,
    *,
    operation: MemoryReportOperation,
    limit: int = 20,
) -> tuple[MemoryReportRecent, ...]:
    """Return latest unique report targets without retaining Memory content."""
    if operation not in {"trace", "rationale"}:
        raise MemoryReportRecentError("Recent report operation is invalid.")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise MemoryReportRecentError("Recent report limit must be positive.")
    try:
        attempts = CommandAttemptLedger(store.store_dir).list()
    except CommandAttemptError as error:
        raise MemoryReportRecentError(str(error)) from error
    result: list[MemoryReportRecent] = []
    seen: set[tuple[str, str, bool]] = set()
    for attempt in attempts:
        recent = _recent_from_attempt(attempt, operation=operation)
        if recent is None:
            continue
        identity = (
            recent.context_name,
            recent.memory_uid,
            recent.include_descendants,
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(recent)
        if len(result) == limit:
            break
    return tuple(result)


def _entry(recent: MemoryReportRecent) -> SessionPickerEntry:
    try:
        timestamp = datetime.fromisoformat(recent.started_at).timestamp()
    except ValueError as error:  # The ledger normally validates this first.
        raise MemoryReportRecentError("Recent report time is invalid.") from error
    command = recent.operation.upper()
    return SessionPickerEntry(
        kind=recent.operation,
        key=recent.attempt_uid,
        title=recent.context_name,
        status="COMPLETED",
        subtitle=f"{command} · Memory [{recent.memory_uid[:8]}]",
        group=recent.context_name,
        sort_timestamp=timestamp,
        detail=(
            f"{command} report\n"
            f"Context {recent.context_name}\n"
            f"Range {'INCLUDE DESCENDANTS' if recent.include_descendants else 'THIS CONTEXT ONLY'}\n"
            f"Memory UID {recent.memory_uid}\n"
            f"Opened {recent.started_at}\n\n"
            "Memory content is not copied into Recents. Opening this row "
            "revalidates the current Context, UID, and permissions."
        ),
        reopen_argv=(
            "mem",
            recent.operation,
            recent.memory_uid,
            "--context",
            recent.context_name,
        ),
    )


def choose_memory_report_recent(
    store: MemoryStore,
    *,
    operation: MemoryReportOperation,
) -> MemoryReportRecentSelection | MemoryReportSelectAction | None:
    """Choose a frozen recent target or enter the normal Memory selector."""
    recents = memory_report_recents(store, operation=operation)
    entries = tuple(_entry(recent) for recent in recents)
    if not entries:
        # With no navigation history there is no catalog decision to make.
        # Continue directly to the common Context/Memory target picker instead
        # of presenting an empty saved-session-shaped launcher.
        return MemoryReportSelectAction()
    select_receipt = SessionNewReceipt(
        kind=f"{operation}-select",
        argv=("mem", operation),
        action_label="SELECT A MEMORY",
        action_description=(
            "Leave Recents and choose from the common Context/Memory tree."
        ),
    )
    receipt = choose_session(
        entries,
        title=f"MEM {operation.upper()} · RECENTS OR SELECT",
        new_receipt=select_receipt,
        location=session_picker_location(store),
        catalog_label="recent reports",
    )
    if receipt is None:
        return None
    if isinstance(receipt, SessionNewReceipt):
        if receipt != select_receipt:
            raise MemoryReportRecentError("Report launcher returned a forged action.")
        return MemoryReportSelectAction()
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != operation:
        raise MemoryReportRecentError("Report launcher returned an invalid receipt.")
    by_key = {recent.attempt_uid: recent for recent in recents}
    selected = by_key.get(receipt.key)
    if selected is None or receipt.argv != _entry(selected).reopen_argv:
        raise MemoryReportRecentError("Report launcher returned a forged receipt.")
    try:
        live_attempt = CommandAttemptLedger(store.store_dir).load(selected.attempt_uid)
    except CommandAttemptError as error:
        raise MemoryReportRecentError(
            "The selected recent report no longer exists. Reopen Recents."
        ) from error
    if _recent_from_attempt(live_attempt, operation=operation) != selected:
        raise MemoryReportRecentError(
            "The selected recent report changed. Reopen Recents."
        )
    return MemoryReportRecentSelection(
        context_name=selected.context_name,
        memory_uid=selected.memory_uid,
        include_descendants=selected.include_descendants,
    )
