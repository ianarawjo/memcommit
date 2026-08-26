"""Command-ledger runtime for content-free Read Report Recents."""

from __future__ import annotations

from memcommit.command_attempts import (
    CommandAttempt,
    CommandAttemptError,
    CommandAttemptLedger,
)
from memcommit.reviewing.read_report import (
    ReadReportError,
    ReadReportOperation,
    ReadReportRecent,
    ReadReportTarget,
)
from memcommit.store import MemoryStore


def _legacy_memory_target(
    attempt: CommandAttempt,
    *,
    operation: ReadReportOperation,
) -> ReadReportTarget | None:
    if operation not in {"trace", "rationale"}:
        return None
    details = attempt.details.get("memory_report")
    if not isinstance(details, dict) or details.get("operation") != operation:
        return None
    context_name = details.get("context_name")
    memory_uid = details.get("memory_uid")
    if not isinstance(context_name, str) or not isinstance(memory_uid, str):
        raise ReadReportError("Legacy Memory report metadata is invalid.")
    include_descendants = details.get("include_descendants")
    if include_descendants is None:
        include_descendants = operation == "rationale"
    if type(include_descendants) is not bool:
        raise ReadReportError("Legacy Memory report range is invalid.")
    return ReadReportTarget(
        operation=operation,
        context_names=(context_name,),
        target_names=(context_name,),
        selection_mode="SINGLE",
        ranges=("RECURSIVE",) if include_descendants else ("DIRECT",),
        memory_uid=memory_uid,
    )


def recent_from_attempt(
    attempt: CommandAttempt,
    *,
    operation: ReadReportOperation,
) -> ReadReportRecent | None:
    """Project one completed matching attempt without loading report content."""

    accepted_attempt_operations = (
        {operation, "log"} if operation == "trace" else {operation}
    )
    if attempt.status != "COMPLETED" or attempt.operation not in accepted_attempt_operations:
        return None
    metadata = attempt.details.get("read_report")
    target = (
        ReadReportTarget.from_metadata(metadata)
        if metadata is not None
        else _legacy_memory_target(attempt, operation=operation)
    )
    if target is None or target.operation != operation:
        return None
    return ReadReportRecent(
        attempt_uid=attempt.uid,
        target=target,
        started_at=attempt.started_at,
    )


def read_report_recents(
    store: MemoryStore,
    *,
    operation: ReadReportOperation,
    limit: int = 20,
) -> tuple[ReadReportRecent, ...]:
    """Return latest unique content-free targets for one report operation."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ReadReportError("Read Report recent limit must be positive.")
    try:
        attempts = CommandAttemptLedger(store.store_dir).list()
    except CommandAttemptError as error:
        raise ReadReportError(str(error)) from error
    result: list[ReadReportRecent] = []
    seen: set[ReadReportTarget] = set()
    for attempt in attempts:
        recent = recent_from_attempt(attempt, operation=operation)
        if recent is None or recent.target in seen:
            continue
        seen.add(recent.target)
        result.append(recent)
        if len(result) == limit:
            break
    return tuple(result)


def revalidate_read_report_recent(
    store: MemoryStore,
    recent: ReadReportRecent,
) -> ReadReportTarget:
    """Reload one selected attempt and require exact content-free identity."""

    try:
        attempt = CommandAttemptLedger(store.store_dir).load(recent.attempt_uid)
    except CommandAttemptError as error:
        raise ReadReportError(
            "The selected recent report no longer exists. Reopen Recents."
        ) from error
    refreshed = recent_from_attempt(attempt, operation=recent.target.operation)
    if refreshed != recent:
        raise ReadReportError(
            "The selected recent report changed. Reopen Recents."
        )
    return recent.target


__all__ = [
    "read_report_recents",
    "recent_from_attempt",
    "revalidate_read_report_recent",
]
