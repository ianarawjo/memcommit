"""Profile-scoped application contract for the user's operation timeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


LogEntryStatus = Literal["RUNNING", "COMPLETED", "FAILED", "INTERRUPTED"]


class LogError(RuntimeError):
    """The Profile operation timeline could not be read safely."""


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One user-entered operation attempt in the Profile timeline."""

    uid: str
    operation: str
    started_at: str
    status: LogEntryStatus
    command: str | None = None
    outcome: str | None = None
    elapsed_seconds: float | None = None
    failure: dict[str, object] | None = None
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LogRequest:
    """One bounded request for the Profile-wide operation timeline."""

    limit: int = 20
    exclude_attempt_uid: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or not 1 <= self.limit <= 200:
            raise ValueError("Log limit must be between 1 and 200.")


@dataclass(frozen=True, slots=True)
class LogResult:
    """Frozen Profile-wide Log projection, newest first."""

    entries: tuple[LogEntry, ...]


class LogSource(Protocol):
    """Read boundary supplying an already selected Profile timeline."""

    def read(self, request: LogRequest) -> LogResult: ...


def run_log(request: LogRequest, *, source: LogSource) -> LogResult:
    """Return a bounded Profile timeline without presentation concerns."""

    result = source.read(request)
    if not isinstance(result, LogResult):
        raise TypeError("Log source returned an invalid result.")
    return result


__all__ = [
    "LogEntry",
    "LogEntryStatus",
    "LogError",
    "LogRequest",
    "LogResult",
    "LogSource",
    "run_log",
]
