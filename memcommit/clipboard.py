"""System-text and structured-result clipboard support for mem commands."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from typing import Callable, Iterator

import memcommit.store as store_module

try:
    import fcntl
except ImportError:  # pragma: no cover - clipboard support is macOS-only.
    fcntl = None  # type: ignore[assignment]


SCHEMA_VERSION = 1
_STAGE_FILE_NAME = "clipboard.json"
_LOCK_FILE_NAME = "clipboard.lock"
_CLIPBOARD_TIMEOUT_SECONDS = 5


class ClipboardError(RuntimeError):
    """A clipboard operation could not preserve its documented contract."""


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _digest_selection(selection: dict[str, object]) -> str:
    try:
        canonical = json.dumps(
            selection,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ClipboardError("The structured clipboard selection is invalid.") from error
    return _digest_text(canonical)


def _stage_path() -> Path:
    # Resolve this dynamically so tests and alternate stores that redirect
    # STORE_DIR keep the structured clipboard inside the same trust boundary.
    return store_module.STORE_DIR / _STAGE_FILE_NAME


def _lock_path() -> Path:
    return store_module.STORE_DIR / _LOCK_FILE_NAME


@contextmanager
def _clipboard_lock() -> Iterator[None]:
    """Serialize the system-text and typed-stage pair across mem processes."""
    if fcntl is None:
        raise ClipboardError(
            "Structured clipboard coordination is unavailable on this platform."
        )

    path = _lock_path()
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    locked = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ClipboardError("Refusing to use a symbolic-link clipboard lock.")
        descriptor = os.open(path, flags, 0o600)
        # The lock spans both representations. Locking only the stage file
        # would still let one copy validate or delete another copy's result.
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        locked = True
    except ClipboardError:
        if descriptor is not None:
            os.close(descriptor)
        raise
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise ClipboardError(
            "Could not coordinate the structured clipboard."
        ) from error

    try:
        yield
    finally:
        if descriptor is not None:
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(descriptor)


def _clipboard_command(name: str, *, platform_name: str | None = None) -> list[str]:
    platform_value = platform_name or sys.platform
    if platform_value != "darwin":
        raise ClipboardError(
            "System clipboard integration is currently available only on macOS."
        )
    return [f"/usr/bin/{name}"]


def write_system_clipboard(
    text: str,
    *,
    runner: Runner | None = None,
    platform_name: str | None = None,
) -> None:
    """Write exact UTF-8 text to the platform clipboard."""
    run = runner or subprocess.run
    command = _clipboard_command("pbcopy", platform_name=platform_name)
    try:
        result = run(
            command,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=_CLIPBOARD_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClipboardError("Could not write to the system clipboard.") from error
    if result.returncode != 0:
        raise ClipboardError("Could not write to the system clipboard.")


def read_system_clipboard(
    *,
    runner: Runner | None = None,
    platform_name: str | None = None,
) -> str:
    """Read exact UTF-8 text from the platform clipboard."""
    run = runner or subprocess.run
    command = _clipboard_command("pbpaste", platform_name=platform_name)
    try:
        result = run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=_CLIPBOARD_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClipboardError("Could not read the system clipboard.") from error
    if result.returncode != 0:
        raise ClipboardError("Could not read the system clipboard.")
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ClipboardError(
            "The system clipboard does not contain valid UTF-8 text."
        ) from error


@dataclass(frozen=True)
class ClipboardPayload:
    """One frozen command result with text and a producer-owned typed selection."""

    producer: str
    plain_text: str
    selection: dict[str, object]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        producer: str,
        plain_text: str,
        selection: dict[str, object],
    ) -> ClipboardPayload:
        return cls(
            producer=producer,
            plain_text=plain_text,
            selection=selection,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "producer": self.producer,
            "created_at": self.created_at,
            "plain_text": self.plain_text,
            "plain_text_sha256": _digest_text(self.plain_text),
            "selection": self.selection,
            "selection_sha256": _digest_selection(self.selection),
        }

    @classmethod
    def from_dict(cls, value: object) -> ClipboardPayload:
        if not isinstance(value, dict):
            raise ClipboardError("The structured clipboard record is invalid.")
        expected_keys = {
            "schema_version",
            "producer",
            "created_at",
            "plain_text",
            "plain_text_sha256",
            "selection",
            "selection_sha256",
        }
        if set(value) != expected_keys:
            raise ClipboardError("The structured clipboard record is invalid.")
        if value["schema_version"] != SCHEMA_VERSION:
            raise ClipboardError(
                "The structured clipboard was created by an unsupported version."
            )
        producer = value["producer"]
        created_at = value["created_at"]
        plain_text = value["plain_text"]
        digest = value["plain_text_sha256"]
        selection = value["selection"]
        selection_digest = value["selection_sha256"]
        if (
            not isinstance(producer, str)
            or not producer
            or not isinstance(created_at, str)
            or not created_at
            or not isinstance(plain_text, str)
            or not isinstance(digest, str)
            or not isinstance(selection, dict)
            or not isinstance(selection_digest, str)
        ):
            raise ClipboardError("The structured clipboard record is invalid.")
        if digest != _digest_text(plain_text):
            raise ClipboardError("The structured clipboard record is invalid.")
        if selection_digest != _digest_selection(selection):
            raise ClipboardError("The structured clipboard record is invalid.")
        return cls(
            producer=producer,
            plain_text=plain_text,
            selection=selection,
            created_at=created_at,
        )


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ClipboardError("The structured clipboard record is invalid.")
        result[key] = value
    return result


def _invalidate_stage() -> None:
    """Remove the old typed half before replacing either clipboard half."""
    path = _stage_path()
    if path.is_symlink():
        raise ClipboardError("Refusing to use a symbolic-link clipboard record.")
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise ClipboardError(
            "Could not invalidate the previous structured clipboard."
        ) from error


def _write_stage(payload: ClipboardPayload) -> None:
    path = _stage_path()
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ClipboardError(
                "Refusing to use a symbolic-link clipboard record."
            )
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            descriptor = None
            json.dump(payload.to_dict(), file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except ClipboardError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise ClipboardError(
            "Could not save the structured clipboard record."
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _read_stage() -> ClipboardPayload:
    path = _stage_path()
    if path.is_symlink():
        raise ClipboardError("Refusing to use a symbolic-link clipboard record.")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, encoding="utf-8") as file:
            descriptor = None
            value = json.load(file, object_pairs_hook=_reject_duplicate_keys)
    except FileNotFoundError as error:
        raise ClipboardError(
            "No structured mem clipboard is available; run 'mem ls --copy' first."
        ) from error
    except (OSError, json.JSONDecodeError, ClipboardError) as error:
        if isinstance(error, ClipboardError):
            raise
        raise ClipboardError("The structured clipboard record is invalid.") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return ClipboardPayload.from_dict(value)


def copy_payload(payload: ClipboardPayload) -> None:
    """
    Replace both clipboard halves, leaving no usable typed stage on failure.

    The old stage is invalidated first because two selections can render the
    same text while carrying different object identities.
    """
    with _clipboard_lock():
        _invalidate_stage()
        write_system_clipboard(payload.plain_text)
        try:
            _write_stage(payload)
            if read_system_clipboard() != payload.plain_text:
                raise ClipboardError(
                    "The system clipboard changed before the structured copy "
                    "completed."
                )
        except Exception:
            _invalidate_stage()
            raise


def load_payload(*, expected_producer: str) -> ClipboardPayload:
    """Load a typed payload only while its exact text remains on the clipboard."""
    # Preserve the read-only missing-stage path: merely asking to paste should
    # not create ~/.mem when no mem clipboard has ever existed. If the first
    # copy races this check, fail closed instead of accepting an unlocked pair.
    if not _stage_path().parent.exists():
        raise ClipboardError(
            "No structured mem clipboard is available; run 'mem ls --copy' first."
        )

    with _clipboard_lock():
        payload = _read_stage()
        if payload.producer != expected_producer:
            raise ClipboardError(
                "The structured clipboard does not contain a "
                f"{expected_producer} result."
            )
        current_text = read_system_clipboard()
        if (
            current_text != payload.plain_text
            or _digest_text(current_text) != _digest_text(payload.plain_text)
        ):
            raise ClipboardError(
                "The system clipboard changed after the mem result was copied; "
                "run 'mem ls --copy' again."
            )
        return payload
