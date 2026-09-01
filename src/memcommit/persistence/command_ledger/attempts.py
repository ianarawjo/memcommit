"""Profile-scoped audit records for every entered ``mem`` command.

The attempt ledger records the complete entered argv, command lifecycle, and
bounded operation metadata. A RUNNING record is published before command
dispatch so process loss still leaves evidence that an attempt began; ordinary
completion replaces that same file atomically.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shlex
import time
from typing import Literal
import uuid

from memcommit.application.capabilities.reviewing.read_report import ReadReportTarget


AttemptStatus = Literal["RUNNING", "COMPLETED", "FAILED", "INTERRUPTED"]
CommandOutcome = Literal["NO_CHANGE", "CANCELLED"]
_FINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "INTERRUPTED"})
_COMPLETION_OUTCOMES = frozenset({"NO_CHANGE", "CANCELLED"})
_OPERATION = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_SCOPE = frozenset({"THIS_CONTEXT_ONLY", "INCLUDE_DESCENDANTS"})
_COMMAND_TEXT_LIMIT = 16 * 1024 * 1024


class CommandAttemptError(RuntimeError):
    """The command-attempt ledger cannot be written or interpreted safely."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_nonempty(value: object, *, field: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise CommandAttemptError(f"Command attempt {field} is invalid.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CommandAttemptError(f"Command attempt {field} is invalid.")
    return value


@dataclass(frozen=True)
class CommandAttempt:
    uid: str
    operation: str
    command: str | None
    status: AttemptStatus
    started_at: str
    completed_at: str | None
    elapsed_seconds: float | None
    stdin_tty: bool
    stdout_tty: bool
    details: dict[str, object]
    outcome: CommandOutcome | None
    failure: dict[str, object] | None

    def validated(self) -> "CommandAttempt":
        try:
            canonical_uid = str(uuid.UUID(self.uid))
            datetime.fromisoformat(self.started_at)
            if self.completed_at is not None:
                datetime.fromisoformat(self.completed_at)
        except (TypeError, ValueError) as error:
            raise CommandAttemptError("Command attempt identity or time is invalid.") from error
        if canonical_uid != self.uid or _OPERATION.fullmatch(self.operation) is None:
            raise CommandAttemptError("Command attempt identity or operation is invalid.")
        if self.command is not None and (
            not isinstance(self.command, str)
            or not self.command.strip()
            or len(self.command) > _COMMAND_TEXT_LIMIT
        ):
            raise CommandAttemptError("Command attempt command is invalid.")
        if self.status not in {"RUNNING", *_FINAL_STATUSES}:
            raise CommandAttemptError("Command attempt status is invalid.")
        if self.status == "RUNNING":
            if self.completed_at is not None or self.elapsed_seconds is not None:
                raise CommandAttemptError("Running command attempt has terminal timing.")
        elif (
            self.completed_at is None
            or not isinstance(self.elapsed_seconds, (int, float))
            or isinstance(self.elapsed_seconds, bool)
            or not math.isfinite(self.elapsed_seconds)
            or self.elapsed_seconds < 0
        ):
            raise CommandAttemptError("Finished command attempt timing is invalid.")
        if not isinstance(self.stdin_tty, bool) or not isinstance(self.stdout_tty, bool):
            raise CommandAttemptError("Command attempt terminal flags are invalid.")
        if self.outcome is not None and self.outcome not in _COMPLETION_OUTCOMES:
            raise CommandAttemptError("Command attempt outcome is invalid.")
        if self.status in {"FAILED", "INTERRUPTED"} and self.outcome is not None:
            raise CommandAttemptError(
                "Unsuccessful command attempt cannot retain a completion outcome."
            )
        _validated_details(self.details)
        _validated_failure(self.failure, status=self.status)
        return self

    def to_dict(self) -> dict[str, object]:
        self.validated()
        return {
            "version": 3,
            "uid": self.uid,
            "operation": self.operation,
            "command": self.command,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_seconds": self.elapsed_seconds,
            "terminal": {
                "stdin_tty": self.stdin_tty,
                "stdout_tty": self.stdout_tty,
            },
            "details": self.details,
            "outcome": self.outcome,
            "failure": self.failure,
        }

    @classmethod
    def from_dict(cls, value: object) -> "CommandAttempt":
        version_one_fields = {
            "version",
            "uid",
            "operation",
            "status",
            "started_at",
            "completed_at",
            "elapsed_seconds",
            "terminal",
            "details",
            "failure",
        }
        if not isinstance(value, dict):
            raise CommandAttemptError("Command attempt record is invalid.")
        version = value.get("version")
        if not (
            version == 1
            and set(value) == version_one_fields
            or version == 2
            and set(value) == {*version_one_fields, "outcome"}
            or version == 3
            and set(value) == {*version_one_fields, "outcome", "command"}
        ):
            raise CommandAttemptError("Command attempt record is invalid.")
        terminal = value.get("terminal")
        if not isinstance(terminal, dict) or set(terminal) != {"stdin_tty", "stdout_tty"}:
            raise CommandAttemptError("Command attempt terminal record is invalid.")
        attempt = cls(
            uid=value.get("uid"),  # type: ignore[arg-type]
            operation=value.get("operation"),  # type: ignore[arg-type]
            command=(
                value.get("command")  # type: ignore[arg-type]
                if version == 3
                else None
            ),
            status=value.get("status"),  # type: ignore[arg-type]
            started_at=value.get("started_at"),  # type: ignore[arg-type]
            completed_at=value.get("completed_at"),  # type: ignore[arg-type]
            elapsed_seconds=value.get("elapsed_seconds"),  # type: ignore[arg-type]
            stdin_tty=terminal.get("stdin_tty"),  # type: ignore[arg-type]
            stdout_tty=terminal.get("stdout_tty"),  # type: ignore[arg-type]
            details=value.get("details"),  # type: ignore[arg-type]
            outcome=(
                value.get("outcome")  # type: ignore[arg-type]
                if version in {2, 3}
                else None
            ),
            failure=value.get("failure"),  # type: ignore[arg-type]
        )
        return attempt.validated()


def _validated_details(value: object) -> None:
    if not isinstance(value, dict) or set(value) - {
        "sever",
        "memory_report",
        "read_report",
    }:
        raise CommandAttemptError("Command attempt details are invalid.")
    read_report = value.get("read_report")
    if read_report is not None:
        try:
            ReadReportTarget.from_metadata(read_report)
        except ValueError as error:
            raise CommandAttemptError("Read Report attempt details are invalid.") from error
    memory_report = value.get("memory_report")
    if memory_report is not None:
        required = {"operation", "context_name", "memory_uid"}
        if (
            not isinstance(memory_report, dict)
            or not required <= set(memory_report)
            or set(memory_report) - {*required, "include_descendants"}
        ):
            raise CommandAttemptError("Memory report attempt details are invalid.")
        if memory_report.get("operation") not in {"trace", "rationale"}:
            raise CommandAttemptError("Memory report operation is invalid.")
        _safe_nonempty(memory_report.get("context_name"), field="Context name")
        _safe_nonempty(memory_report.get("memory_uid"), field="Memory UID")
        include_descendants = memory_report.get("include_descendants")
        if include_descendants is not None and type(include_descendants) is not bool:
            raise CommandAttemptError("Memory report scope is invalid.")
    sever = value.get("sever")
    if sever is None:
        return
    allowed = {
        "source_name",
        "source_scope",
        "source_memory_count",
        "criteria_name",
        "criteria_scope",
        "criteria_memory_count",
        "output_name",
        "excluded_query_context_count",
        "provider",
        "provider_timeout_seconds",
        "failure_kind",
    }
    if not isinstance(sever, dict) or set(sever) - allowed:
        raise CommandAttemptError("Sever attempt details are invalid.")
    for field in ("source_name", "criteria_name", "output_name", "provider"):
        if field in sever:
            _safe_nonempty(sever[field], field=field)
    for field in ("source_scope", "criteria_scope"):
        if field in sever and sever[field] not in _SCOPE:
            raise CommandAttemptError("Sever attempt scope is invalid.")
    for field in (
        "source_memory_count",
        "criteria_memory_count",
        "excluded_query_context_count",
    ):
        if field in sever and (
            not isinstance(sever[field], int)
            or isinstance(sever[field], bool)
            or sever[field] < 0
        ):
            raise CommandAttemptError(f"Sever attempt {field} is invalid.")
    timeout = sever.get("provider_timeout_seconds")
    if timeout is not None and (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise CommandAttemptError("Sever attempt provider timeout is invalid.")
    if "failure_kind" in sever and sever["failure_kind"] not in {
        "TIMEOUT",
        "PROVIDER",
        "VALIDATION",
    }:
        raise CommandAttemptError("Sever attempt failure kind is invalid.")


def _validated_failure(value: object, *, status: AttemptStatus) -> None:
    if status in {"RUNNING", "COMPLETED"}:
        if value is not None:
            raise CommandAttemptError("Successful command attempt has failure metadata.")
        return
    if not isinstance(value, dict) or set(value) != {"kind", "exit_code"}:
        raise CommandAttemptError("Failed command attempt metadata is invalid.")
    _safe_nonempty(value.get("kind"), field="failure kind", limit=128)
    exit_code = value.get("exit_code")
    if exit_code is not None and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool)
    ):
        raise CommandAttemptError("Command attempt exit code is invalid.")


class CommandAttemptLedger:
    """Atomic append/finalize access within one Profile's existing ledger."""

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.directory = self.store_dir / "ledger" / "command-attempts"

    def _validated_directory(self, *, create: bool) -> Path:
        ledger = self.directory.parent
        for path, label in ((ledger, "Profile ledger"), (self.directory, "command attempt ledger")):
            if path.is_symlink() or path.exists() and not path.is_dir():
                raise CommandAttemptError(f"{label} storage is invalid.")
        if create:
            store_created = not self.store_dir.exists()
            self.store_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            if store_created:
                _fsync_directory(self.store_dir.parent)
            ledger_created = not ledger.exists()
            ledger.mkdir(exist_ok=True, mode=0o700)
            if ledger_created:
                _fsync_directory(self.store_dir)
            directory_created = not self.directory.exists()
            self.directory.mkdir(exist_ok=True, mode=0o700)
            if directory_created:
                _fsync_directory(ledger)
        return self.directory

    def _path(self, uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(uid))
        except (TypeError, ValueError) as error:
            raise CommandAttemptError("Command attempt uid is invalid.") from error
        if canonical != uid:
            raise CommandAttemptError("Command attempt uid is invalid.")
        return self.directory / f"{uid}.json"

    def create(self, attempt: CommandAttempt) -> None:
        attempt.validated()
        directory = self._validated_directory(create=True)
        path = self._path(attempt.uid)
        if path.exists() or path.is_symlink():
            raise CommandAttemptError("Command attempt already exists.")
        self._write(path, attempt, exclusive=True)
        _fsync_directory(directory)

    def replace(self, attempt: CommandAttempt) -> None:
        attempt.validated()
        self._validated_directory(create=False)
        path = self._path(attempt.uid)
        if not path.is_file() or path.is_symlink():
            raise CommandAttemptError("Command attempt no longer exists.")
        self._write(path, attempt, exclusive=False)
        _fsync_directory(self.directory)

    def _write(self, path: Path, attempt: CommandAttempt, *, exclusive: bool) -> None:
        temporary = self.directory / f".{path.name}.write-{uuid.uuid4().hex}"
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(attempt.to_dict(), handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            if exclusive and (path.exists() or path.is_symlink()):
                raise CommandAttemptError("Command attempt already exists.")
            os.replace(temporary, path)
        finally:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()

    def load(self, uid: str) -> CommandAttempt:
        self._validated_directory(create=False)
        path = self._path(uid)
        if not path.is_file() or path.is_symlink():
            raise CommandAttemptError("Command attempt was not found.")
        try:
            with open(path, encoding="utf-8") as handle:
                return CommandAttempt.from_dict(json.load(handle))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandAttemptError("Command attempt is not valid JSON.") from error

    def list(self) -> tuple[CommandAttempt, ...]:
        if not self.directory.exists():
            return ()
        self._validated_directory(create=False)
        records: list[CommandAttempt] = []
        for path in self.directory.iterdir():
            if path.name.startswith("."):
                continue
            if path.suffix != ".json" or not path.is_file() or path.is_symlink():
                raise CommandAttemptError("Unexpected command attempt ledger entry.")
            records.append(self.load(path.stem))
        return tuple(sorted(records, key=lambda item: (item.started_at, item.uid), reverse=True))


@dataclass
class ActiveCommandAttempt:
    ledger: CommandAttemptLedger
    record: CommandAttempt
    monotonic_started_at: float


_ACTIVE_ATTEMPT: ContextVar[ActiveCommandAttempt | None] = ContextVar(
    "memcommit_active_command_attempt",
    default=None,
)


def begin_command_attempt(
    *,
    store_dir: Path,
    operation: str,
    stdin_tty: bool,
    stdout_tty: bool,
    command_argv: tuple[str, ...] | None = None,
) -> ActiveCommandAttempt:
    if command_argv is not None and any(
        not isinstance(argument, str) for argument in command_argv
    ):
        raise CommandAttemptError("Command attempt argv is invalid.")
    attempt = CommandAttempt(
        uid=str(uuid.uuid4()),
        operation=operation,
        command=(
            None
            if command_argv is None
            else shlex.join(("mem", *command_argv))
        ),
        status="RUNNING",
        started_at=_timestamp(),
        completed_at=None,
        elapsed_seconds=None,
        stdin_tty=stdin_tty,
        stdout_tty=stdout_tty,
        details={},
        outcome=None,
        failure=None,
    )
    active = ActiveCommandAttempt(
        ledger=CommandAttemptLedger(store_dir),
        record=attempt,
        monotonic_started_at=time.monotonic(),
    )
    active.ledger.create(attempt)
    _ACTIVE_ATTEMPT.set(active)
    return active


def current_command_attempt_uid() -> str | None:
    active = _ACTIVE_ATTEMPT.get()
    return active.record.uid if active is not None else None


def annotate_command_outcome(outcome: CommandOutcome) -> None:
    """Persist one exceptional normal-completion outcome on the active command.

    Normal success is deliberately implicit.  Commands call this only when
    they can prove that the whole invocation ended without a Context effect or
    was cancelled before its operation-owned completion boundary.
    """

    if outcome not in _COMPLETION_OUTCOMES:
        raise CommandAttemptError("Command attempt outcome is invalid.")
    active = _ACTIVE_ATTEMPT.get()
    if active is None:
        return
    if active.record.status != "RUNNING":
        raise CommandAttemptError("Finished command attempt cannot change outcome.")
    if active.record.outcome is not None and active.record.outcome != outcome:
        raise CommandAttemptError("Command attempt outcome is already finalized.")
    updated = replace(active.record, outcome=outcome)
    active.ledger.replace(updated)
    active.record = updated


def annotate_sever_attempt(**updates: object) -> None:
    """Persist only the allowlisted, content-free Sever attempt fields."""
    active = _ACTIVE_ATTEMPT.get()
    if active is None:
        return
    details = dict(active.record.details)
    sever = dict(details.get("sever", {}))
    sever.update(updates)
    details["sever"] = sever
    updated = replace(active.record, details=details)
    active.ledger.replace(updated)
    active.record = updated


def annotate_read_report_attempt(target: ReadReportTarget) -> None:
    """Persist one content-free report identity on the active CLI attempt."""

    if not isinstance(target, ReadReportTarget):
        raise TypeError("Read Report annotation requires a typed target.")
    active = _ACTIVE_ATTEMPT.get()
    if active is None:
        return
    if active.record.operation != target.operation:
        raise CommandAttemptError(
            "Read Report metadata does not match the active operation."
        )
    details = dict(active.record.details)
    details["read_report"] = target.to_metadata()
    updated = replace(active.record, details=details)
    active.ledger.replace(updated)
    active.record = updated


def finish_command_attempt(
    active: ActiveCommandAttempt,
    *,
    status: Literal["COMPLETED", "FAILED", "INTERRUPTED"],
    failure_kind: str | None = None,
    exit_code: int | None = None,
) -> CommandAttempt:
    failure = (
        None
        if status == "COMPLETED"
        else {
            "kind": _safe_nonempty(
                failure_kind or status.title(), field="failure kind", limit=128
            ),
            "exit_code": exit_code,
        }
    )
    finished = replace(
        active.record,
        status=status,
        completed_at=_timestamp(),
        elapsed_seconds=max(0.0, time.monotonic() - active.monotonic_started_at),
        # A later failure supersedes a provisional normal-completion annotation.
        # The durable checkpoint/receipt remains authoritative for any effect
        # already published before that failure.
        outcome=active.record.outcome if status == "COMPLETED" else None,
        failure=failure,
    )
    active.ledger.replace(finished)
    active.record = finished
    _ACTIVE_ATTEMPT.set(None)
    return finished
