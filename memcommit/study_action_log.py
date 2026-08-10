"""Content-free detailed action events for current ``init-study`` Profiles.

Every Profile keeps the small command-attempt ledger.  This module adds a
second, deliberately narrower surface only when immutable Profile provenance
marks the active store as a current Study participant or granted-memory owner.
It records command phases and non-text terminal interaction, never raw argv,
Memory/query/composer text, provider prompts, responses, or credentials.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
from typing import Callable, Iterator, ParamSpec, TypeVar
import uuid

from prompt_toolkit.application.current import (
    create_app_session,
    get_app,
    get_app_session,
)
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys

from memcommit.profile_config import (
    ProfileConfigError,
    ProfileEntry,
    profile_store_dir,
    study_run_identity,
)


class StudyActionError(RuntimeError):
    """A Study action cannot be recorded or interpreted safely."""


_ACTION = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_SAFE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+ -]{0,255}\Z")
_ROLES = frozenset({"PARTICIPANT", "GRANTED_MEMORY"})
_STATUSES = frozenset({"COMPLETED", "FAILED", "INTERRUPTED"})
_ACTION_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "COMMAND_STARTED": (
        frozenset({"operation", "stdin_tty", "stdout_tty"}),
        frozenset({"terminal_rows", "terminal_columns"}),
    ),
    "COMMAND_FINISHED": (
        frozenset({"status"}),
        frozenset({"failure_kind", "exit_code"}),
    ),
    "KEY": (
        frozenset({"key", "count", "focus"}),
        frozenset(),
    ),
    "TEXT_INPUT": (
        frozenset({"character_count", "line_break_count", "paste", "focus"}),
        frozenset(),
    ),
    "PROVIDER_CONNECT_STARTED": (
        frozenset({"operation"}),
        frozenset(),
    ),
    "PROVIDER_CONNECT_COMPLETED": (
        frozenset({"operation", "provider", "elapsed_seconds"}),
        frozenset(),
    ),
    "PROVIDER_CONNECT_FAILED": (
        frozenset({"operation", "failure_kind", "elapsed_seconds"}),
        frozenset(),
    ),
    "PROVIDER_TURN_STARTED": (
        frozenset({"operation", "provider", "input_characters", "has_schema"}),
        frozenset(),
    ),
    "PROVIDER_TURN_COMPLETED": (
        frozenset(
            {
                "operation",
                "provider",
                "output_characters",
                "elapsed_seconds",
            }
        ),
        frozenset(),
    ),
    "PROVIDER_TURN_FAILED": (
        frozenset({"operation", "provider", "failure_kind", "elapsed_seconds"}),
        frozenset(),
    ),
    "TUI_ACTION": (
        frozenset({"surface", "action"}),
        frozenset(),
    ),
    "APPROVAL_PRESENTED": (
        frozenset({"surface", "action"}),
        frozenset(),
    ),
    "APPROVAL_ACCEPTED": (
        frozenset({"surface", "action"}),
        frozenset(),
    ),
    "STUDY_CREATED": (
        frozenset(
            {
                "role",
                "paired_profile_uid",
                "baseline_profile_uid",
                "baseline_profile_name",
            }
        ),
        frozenset(),
    ),
    "PROFILE_ENTERED": (
        frozenset({"other_profile_uid", "other_profile_name"}),
        frozenset(),
    ),
    "PROFILE_LEFT": (
        frozenset({"other_profile_uid", "other_profile_name"}),
        frozenset(),
    ),
    "EFFECT": (
        frozenset({"operation", "effect"}),
        frozenset({"artifact_uid", "item_count", "target_name"}),
    ),
}
_INT_FIELDS = frozenset(
    {
        "terminal_rows",
        "terminal_columns",
        "count",
        "character_count",
        "line_break_count",
        "exit_code",
        "input_characters",
        "output_characters",
        "item_count",
    }
)
_BOOL_FIELDS = frozenset({"stdin_tty", "stdout_tty", "paste", "has_schema"})
_FLOAT_FIELDS = frozenset({"elapsed_seconds"})
_UUID_FIELDS = frozenset(
    {"paired_profile_uid", "baseline_profile_uid", "other_profile_uid", "artifact_uid"}
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _canonical_uuid(value: object, *, field: str) -> str:
    try:
        canonical = str(uuid.UUID(value))  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as error:
        raise StudyActionError(f"Study action {field} is invalid.") from error
    if value != canonical:
        raise StudyActionError(f"Study action {field} is invalid.")
    return canonical


def _safe_token(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SAFE_TOKEN.fullmatch(value) is None:
        raise StudyActionError(f"Study action {field} is invalid.")
    return value


def _validate_data(action: str, data: object) -> dict[str, object]:
    if action not in _ACTION_FIELDS or not isinstance(data, dict):
        raise StudyActionError("Study action data is invalid.")
    required, optional = _ACTION_FIELDS[action]
    if not required.issubset(data) or set(data) - required - optional:
        raise StudyActionError("Study action fields are invalid.")
    for key, value in data.items():
        if key in _INT_FIELDS:
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or (key != "exit_code" and value < 0)
            ):
                raise StudyActionError(f"Study action {key} is invalid.")
        elif key in _BOOL_FIELDS:
            if not isinstance(value, bool):
                raise StudyActionError(f"Study action {key} is invalid.")
        elif key in _FLOAT_FIELDS:
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
            ):
                raise StudyActionError(f"Study action {key} is invalid.")
        elif key in _UUID_FIELDS:
            _canonical_uuid(value, field=key)
        else:
            _safe_token(value, field=key)
    if action == "COMMAND_FINISHED" and data["status"] not in _STATUSES:
        raise StudyActionError("Study action status is invalid.")
    if "role" in data and data["role"] not in _ROLES:
        raise StudyActionError("Study action role is invalid.")
    return dict(data)


@dataclass(frozen=True)
class StudyActionEvent:
    uid: str
    sequence: int
    attempt_uid: str
    study_uid: str
    study_name: str
    profile_uid: str
    profile_role: str
    occurred_at: str
    elapsed_seconds: float | None
    action: str
    data: dict[str, object]

    def validated(self) -> "StudyActionEvent":
        _canonical_uuid(self.uid, field="uid")
        _canonical_uuid(self.attempt_uid, field="attempt uid")
        _canonical_uuid(self.study_uid, field="Study uid")
        _canonical_uuid(self.profile_uid, field="Profile uid")
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise StudyActionError("Study action sequence is invalid.")
        _safe_token(self.study_name, field="Study name")
        if self.profile_role not in _ROLES:
            raise StudyActionError("Study action Profile role is invalid.")
        try:
            parsed = datetime.fromisoformat(self.occurred_at)
        except (TypeError, ValueError) as error:
            raise StudyActionError("Study action timestamp is invalid.") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise StudyActionError("Study action timestamp must include a timezone.")
        if self.elapsed_seconds is not None and (
            not isinstance(self.elapsed_seconds, (int, float))
            or isinstance(self.elapsed_seconds, bool)
            or not math.isfinite(self.elapsed_seconds)
            or self.elapsed_seconds < 0
        ):
            raise StudyActionError("Study action elapsed time is invalid.")
        if _ACTION.fullmatch(self.action) is None:
            raise StudyActionError("Study action kind is invalid.")
        _validate_data(self.action, self.data)
        return self

    def to_dict(self) -> dict[str, object]:
        self.validated()
        return {
            "version": 1,
            "uid": self.uid,
            "sequence": self.sequence,
            "attempt_uid": self.attempt_uid,
            "study": {
                "uid": self.study_uid,
                "name": self.study_name,
            },
            "profile": {
                "uid": self.profile_uid,
                "role": self.profile_role,
            },
            "occurred_at": self.occurred_at,
            "elapsed_seconds": self.elapsed_seconds,
            "action": self.action,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, value: object) -> "StudyActionEvent":
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "version",
                "uid",
                "sequence",
                "attempt_uid",
                "study",
                "profile",
                "occurred_at",
                "elapsed_seconds",
                "action",
                "data",
            }
            or value.get("version") != 1
        ):
            raise StudyActionError("Study action event is invalid.")
        study = value.get("study")
        profile = value.get("profile")
        if not isinstance(study, dict) or set(study) != {"uid", "name"}:
            raise StudyActionError("Study action identity is invalid.")
        if not isinstance(profile, dict) or set(profile) != {"uid", "role"}:
            raise StudyActionError("Study action Profile identity is invalid.")
        return cls(
            uid=value.get("uid"),  # type: ignore[arg-type]
            sequence=value.get("sequence"),  # type: ignore[arg-type]
            attempt_uid=value.get("attempt_uid"),  # type: ignore[arg-type]
            study_uid=study.get("uid"),  # type: ignore[arg-type]
            study_name=study.get("name"),  # type: ignore[arg-type]
            profile_uid=profile.get("uid"),  # type: ignore[arg-type]
            profile_role=profile.get("role"),  # type: ignore[arg-type]
            occurred_at=value.get("occurred_at"),  # type: ignore[arg-type]
            elapsed_seconds=value.get("elapsed_seconds"),  # type: ignore[arg-type]
            action=value.get("action"),  # type: ignore[arg-type]
            data=value.get("data"),  # type: ignore[arg-type]
        ).validated()


class StudyActionLedger:
    """Append-only event files under one validated Study Profile store."""

    def __init__(self, profile: ProfileEntry, *, store_dir: Path | None = None):
        try:
            identity = study_run_identity(profile)
        except ProfileConfigError as error:
            raise StudyActionError(str(error)) from error
        if identity is None:
            raise StudyActionError("Profile is not an init-study Profile.")
        self.profile = profile
        self.identity = identity
        self.store_dir = (
            Path(store_dir) if store_dir is not None else profile_store_dir(profile)
        )
        self.directory = self.store_dir / "ledger" / "study-actions"

    def _validated_directory(self, *, create: bool) -> Path:
        ledger = self.directory.parent
        if self.store_dir.is_symlink() or not self.store_dir.is_dir():
            raise StudyActionError("Study Profile store is invalid.")
        for path, label in (
            (ledger, "Profile ledger"),
            (self.directory, "Study action ledger"),
        ):
            if path.is_symlink() or path.exists() and not path.is_dir():
                raise StudyActionError(f"{label} storage is invalid.")
        if create:
            ledger_created = not ledger.exists()
            ledger.mkdir(exist_ok=True, mode=0o700)
            if ledger_created:
                _fsync_directory(self.store_dir)
            directory_created = not self.directory.exists()
            self.directory.mkdir(exist_ok=True, mode=0o700)
            if directory_created:
                _fsync_directory(ledger)
        return self.directory

    def _path(self, attempt_uid: str) -> Path:
        canonical = _canonical_uuid(attempt_uid, field="attempt uid")
        return self.directory / f"{canonical}.jsonl"

    def append(self, event: StudyActionEvent) -> None:
        event.validated()
        if (
            event.study_uid != self.identity.uid
            or event.study_name != self.identity.name
            or event.profile_uid != self.profile.uid
            or event.profile_role != self.identity.role
        ):
            raise StudyActionError("Study action event belongs to another Profile.")
        directory = self._validated_directory(create=True)
        path = self._path(event.attempt_uid)
        if path.is_symlink() or path.exists() and not path.is_file():
            raise StudyActionError("Study action event file is invalid.")
        encoded = (
            json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if event.sequence == 1:
            _fsync_directory(directory)

    def events_for_attempt(self, attempt_uid: str) -> tuple[StudyActionEvent, ...]:
        if not self.directory.exists():
            return ()
        self._validated_directory(create=False)
        path = self._path(attempt_uid)
        if not path.exists():
            return ()
        if path.is_symlink() or not path.is_file():
            raise StudyActionError("Study action event file is invalid.")
        events: list[StudyActionEvent] = []
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    if not line.endswith("\n"):
                        raise StudyActionError("Study action event is incomplete.")
                    event = StudyActionEvent.from_dict(json.loads(line))
                    if event.attempt_uid != attempt_uid:
                        raise StudyActionError("Study action attempt identity changed.")
                    if (
                        event.study_uid != self.identity.uid
                        or event.study_name != self.identity.name
                        or event.profile_uid != self.profile.uid
                        or event.profile_role != self.identity.role
                    ):
                        raise StudyActionError(
                            "Study action event belongs to another Profile."
                        )
                    events.append(event)
        except json.JSONDecodeError as error:
            raise StudyActionError("Study action event is invalid JSON.") from error
        sequences = [event.sequence for event in events]
        if sequences and (
            sequences[0] != 1
            or any(
                current <= previous
                for previous, current in zip(sequences, sequences[1:])
            )
        ):
            raise StudyActionError("Study action sequence is invalid.")
        return tuple(events)

    def list(self) -> tuple[StudyActionEvent, ...]:
        if not self.directory.exists():
            return ()
        self._validated_directory(create=False)
        events: list[StudyActionEvent] = []
        for path in self.directory.iterdir():
            if path.name.startswith("."):
                continue
            if path.suffix != ".jsonl" or path.is_symlink() or not path.is_file():
                raise StudyActionError("Unexpected Study action ledger entry.")
            events.extend(self.events_for_attempt(path.stem))
        return tuple(
            sorted(
                events,
                key=lambda item: (
                    item.occurred_at,
                    item.attempt_uid,
                    item.sequence,
                ),
                reverse=True,
            )
        )


@dataclass
class ActiveStudyActionRecording:
    ledger: StudyActionLedger
    attempt_uid: str
    started_monotonic: float
    sequence: int = 0
    _append_lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
    )

    def append(self, event_kind: str, **data: object) -> StudyActionEvent:
        # A responsive waiting TUI can record Help navigation while its copied
        # executor context records provider progress. Serialize both against
        # one durable sequence so event order remains complete and readable.
        with self._append_lock:
            next_sequence = self.sequence + 1
            event = StudyActionEvent(
                uid=str(uuid.uuid4()),
                sequence=next_sequence,
                attempt_uid=self.attempt_uid,
                study_uid=self.ledger.identity.uid,
                study_name=self.ledger.identity.name,
                profile_uid=self.ledger.profile.uid,
                profile_role=self.ledger.identity.role,
                occurred_at=_timestamp(),
                elapsed_seconds=max(
                    0.0,
                    time.monotonic() - self.started_monotonic,
                ),
                action=event_kind,
                data=dict(data),
            )
            self.ledger.append(event)
            # Advance only after the durable append. A rejected event must not
            # manufacture a sequence gap that makes later valid telemetry
            # appear corrupt.
            self.sequence = next_sequence
            return event


_ACTIVE_STUDY_ACTIONS: ContextVar[ActiveStudyActionRecording | None] = ContextVar(
    "memcommit_active_study_actions",
    default=None,
)


def begin_study_action_recording(
    *,
    profile: ProfileEntry,
    store_dir: Path,
    attempt_uid: str,
    operation: str,
    stdin_tty: bool,
    stdout_tty: bool,
) -> ActiveStudyActionRecording | None:
    """Begin detailed recording only for current Study run provenance."""

    try:
        identity = study_run_identity(profile)
    except ProfileConfigError as error:
        raise StudyActionError(str(error)) from error
    if identity is None:
        return None
    active = ActiveStudyActionRecording(
        ledger=StudyActionLedger(profile, store_dir=store_dir),
        attempt_uid=_canonical_uuid(attempt_uid, field="attempt uid"),
        started_monotonic=time.monotonic(),
    )
    terminal: dict[str, object] = {}
    if stdin_tty:
        try:
            size = os.get_terminal_size(0)
        except OSError:
            pass
        else:
            terminal = {
                "terminal_rows": size.lines,
                "terminal_columns": size.columns,
            }
    active.append(
        "COMMAND_STARTED",
        operation=operation,
        stdin_tty=stdin_tty,
        stdout_tty=stdout_tty,
        **terminal,
    )
    _ACTIVE_STUDY_ACTIONS.set(active)
    return active


def finish_study_action_recording(
    active: ActiveStudyActionRecording,
    *,
    status: str,
    failure_kind: str | None = None,
    exit_code: int | None = None,
) -> StudyActionEvent:
    data: dict[str, object] = {"status": status}
    if failure_kind is not None:
        data["failure_kind"] = failure_kind
    if exit_code is not None:
        data["exit_code"] = exit_code
    try:
        return active.append("COMMAND_FINISHED", **data)
    finally:
        _ACTIVE_STUDY_ACTIONS.set(None)


def record_study_action(event_kind: str, **data: object) -> StudyActionEvent | None:
    active = _ACTIVE_STUDY_ACTIONS.get()
    if active is None:
        return None
    return active.append(event_kind, **data)


def record_study_action_for_profile(
    profile: ProfileEntry,
    *,
    attempt_uid: str,
    event_kind: str,
    **data: object,
) -> StudyActionEvent | None:
    """Append a creation or Profile-entry event outside the active store."""

    try:
        identity = study_run_identity(profile)
    except ProfileConfigError as error:
        raise StudyActionError(str(error)) from error
    if identity is None:
        return None
    ledger = StudyActionLedger(profile)
    existing = ledger.events_for_attempt(attempt_uid)
    event = StudyActionEvent(
        uid=str(uuid.uuid4()),
        sequence=len(existing) + 1,
        attempt_uid=attempt_uid,
        study_uid=identity.uid,
        study_name=identity.name,
        profile_uid=profile.uid,
        profile_role=identity.role,
        occurred_at=_timestamp(),
        elapsed_seconds=None,
        action=event_kind,
        data=dict(data),
    )
    ledger.append(event)
    return event


def record_provider_connection_started(operation: str) -> float:
    record_study_action("PROVIDER_CONNECT_STARTED", operation=operation)
    return time.monotonic()


def record_provider_connection_finished(
    operation: str,
    started_at: float,
    *,
    provider: str | None = None,
    failure: BaseException | None = None,
) -> None:
    elapsed = max(0.0, time.monotonic() - started_at)
    if failure is not None:
        record_study_action(
            "PROVIDER_CONNECT_FAILED",
            operation=operation,
            failure_kind=type(failure).__name__,
            elapsed_seconds=elapsed,
        )
        return
    record_study_action(
        "PROVIDER_CONNECT_COMPLETED",
        operation=operation,
        provider=provider or "unknown",
        elapsed_seconds=elapsed,
    )


P = ParamSpec("P")
R = TypeVar("R")


def record_study_provider_turn(method: Callable[P, R]) -> Callable[P, R]:
    """Decorate a provider ``complete`` method without retaining its payload."""

    @wraps(method)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        owner = args[0] if args else None
        prompt = args[1] if len(args) > 1 else kwargs.get("prompt")
        operation = kwargs.get("operation")
        operation_label = operation if isinstance(operation, str) else "semantic"
        identity = getattr(owner, "identity", None)
        provider = getattr(identity, "provider", None)
        provider_label = provider if isinstance(provider, str) else "unknown"
        record_study_action(
            "PROVIDER_TURN_STARTED",
            operation=operation_label,
            provider=provider_label,
            input_characters=len(prompt) if isinstance(prompt, str) else 0,
            has_schema=kwargs.get("output_schema") is not None,
        )
        started_at = time.monotonic()
        try:
            result = method(*args, **kwargs)
        except BaseException as error:
            record_study_action(
                "PROVIDER_TURN_FAILED",
                operation=operation_label,
                provider=provider_label,
                failure_kind=type(error).__name__,
                elapsed_seconds=max(0.0, time.monotonic() - started_at),
            )
            raise
        record_study_action(
            "PROVIDER_TURN_COMPLETED",
            operation=operation_label,
            provider=provider_label,
            output_characters=len(result) if isinstance(result, str) else 0,
            elapsed_seconds=max(0.0, time.monotonic() - started_at),
        )
        return result

    return wrapped


def _focus_label() -> str:
    try:
        control = get_app().layout.current_control
    except Exception:
        return "unknown"
    label = type(control).__name__
    return label if _SAFE_TOKEN.fullmatch(label) is not None else "unknown"


def _key_name(press: KeyPress) -> str | None:
    key = press.key
    if key == Keys.BracketedPaste:
        return None
    if isinstance(key, Keys):
        # Most prompt-toolkit values (for example ``down`` and ``c-a``) are
        # already durable tokens. A few control and synthetic keys contain
        # schema punctuation, so retain their stable Enum name instead of
        # letting a wire spelling abort the input loop.
        return key.value if _SAFE_TOKEN.fullmatch(key.value) is not None else key.name
    value = str(key)
    if len(value) == 1 and value.isprintable():
        # A printable byte may be a shortcut or private composer text. The
        # shared input boundary cannot safely distinguish a focus transition
        # that occurs between keys already buffered in one read.
        return None
    return value if _SAFE_TOKEN.fullmatch(value) is not None else "unknown"


class StudyRecordingInput(Input):
    """Prompt-toolkit Input proxy that retains keys but redacts printable text."""

    def __init__(self, wrapped: Input):
        self.wrapped = wrapped

    def fileno(self) -> int:
        return self.wrapped.fileno()

    def typeahead_hash(self) -> str:
        return self.wrapped.typeahead_hash()

    def _record(self, presses: list[KeyPress]) -> None:
        focus = _focus_label()
        pending_key: str | None = None
        pending_count = 0
        text_characters = 0
        text_lines = 0
        text_paste = False

        def flush_key() -> None:
            nonlocal pending_key, pending_count
            if pending_key is not None:
                record_study_action(
                    "KEY",
                    key=pending_key,
                    count=pending_count,
                    focus=focus,
                )
            pending_key = None
            pending_count = 0

        def flush_text() -> None:
            nonlocal text_characters, text_lines, text_paste
            if text_characters or text_lines:
                record_study_action(
                    "TEXT_INPUT",
                    character_count=text_characters,
                    line_break_count=text_lines,
                    paste=text_paste,
                    focus=focus,
                )
            text_characters = 0
            text_lines = 0
            text_paste = False

        for press in presses:
            if press.key == Keys.CPRResponse:
                # CPR is a terminal-renderer protocol response, not a person
                # action. It must still pass through read_keys unchanged so
                # prompt-toolkit can complete its pending cursor query.
                continue
            key_name = _key_name(press)
            if key_name is None:
                flush_key()
                text = press.data
                text_characters += len(text.replace("\r", "").replace("\n", ""))
                text_lines += text.count("\r") + text.count("\n")
                text_paste = text_paste or press.key == Keys.BracketedPaste
                continue
            flush_text()
            if pending_key == key_name:
                pending_count += 1
            else:
                flush_key()
                pending_key = key_name
                pending_count = 1
        flush_key()
        flush_text()

    def read_keys(self) -> list[KeyPress]:
        presses = self.wrapped.read_keys()
        self._record(presses)
        return presses

    def flush_keys(self) -> list[KeyPress]:
        presses = self.wrapped.flush_keys()
        self._record(presses)
        return presses

    def flush(self) -> None:
        self.wrapped.flush()

    @property
    def closed(self) -> bool:
        return self.wrapped.closed

    def raw_mode(self):
        return self.wrapped.raw_mode()

    def cooked_mode(self):
        return self.wrapped.cooked_mode()

    def attach(self, input_ready_callback):
        return self.wrapped.attach(input_ready_callback)

    def detach(self):
        return self.wrapped.detach()

    def close(self) -> None:
        self.wrapped.close()


@contextmanager
def study_recording_app_session() -> Iterator[None]:
    """Install the input recorder for production TTY Applications in a command."""

    active = _ACTIVE_STUDY_ACTIONS.get()
    if active is None or not sys.stdin.isatty() or not sys.stdout.isatty():
        yield
        return
    session = get_app_session()
    with create_app_session(
        input=StudyRecordingInput(session.input),
        output=session.output,
    ):
        yield
