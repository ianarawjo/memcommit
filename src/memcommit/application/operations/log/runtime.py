"""Command-attempt ledger binding for the Profile Log application."""

from __future__ import annotations

from memcommit.application.operations.log.application import (
    LogEntry,
    LogError,
    LogRequest,
    LogResult,
    run_log,
)
from memcommit.persistence.command_ledger.attempts import (
    CommandAttemptError,
    CommandAttemptLedger,
)
from memcommit.persistence.store import MemoryStore


class CommandAttemptLogSource:
    """Adapt one Profile's durable command-attempt ledger to Log entries."""

    def __init__(self, store: MemoryStore) -> None:
        self._ledger = CommandAttemptLedger(store.store_dir)

    def read(self, request: LogRequest) -> LogResult:
        try:
            attempts = tuple(
                attempt
                for attempt in self._ledger.list()
                if attempt.uid != request.exclude_attempt_uid
            )[: request.limit]
        except CommandAttemptError as error:
            raise LogError(str(error)) from error
        return LogResult(
            entries=tuple(
                LogEntry(
                    uid=attempt.uid,
                    operation=attempt.operation,
                    started_at=attempt.started_at,
                    status=attempt.status,
                    command=attempt.command,
                    outcome=attempt.outcome,
                    elapsed_seconds=attempt.elapsed_seconds,
                    failure=attempt.failure,
                    details=attempt.details,
                )
                for attempt in attempts
            )
        )


def execute_log(store: MemoryStore, request: LogRequest) -> LogResult:
    """Read the Profile-wide operation Log through its application port."""

    return run_log(request, source=CommandAttemptLogSource(store))


__all__ = ["CommandAttemptLogSource", "execute_log"]
