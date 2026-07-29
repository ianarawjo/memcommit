"""
    MemoryStore manages all persistence for mem contexts.
    Single source of truth for reading/writing ~/.mem/.

    Serialization is delegated to Context.to_dict() / Context.from_dict().
    All disk I/O is explicit: callers must call store.save(ctx) to persist mutations.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from memcommit.context import AutoCheckpoint, Checkpoint, Context, Memory

STORE_DIR = Path.home() / ".mem"
CONTEXTS_DIR = STORE_DIR / "contexts"
STATE_FILE = STORE_DIR / "state.json"
QUERY_SOURCES_DIR = STORE_DIR / "query-sources"
IMPACT_PLAN_FILE = STORE_DIR / "impact-plan.json"
STAGED_UPDATE_FILE = STORE_DIR / "staged-update.json"
REVIEW_SESSION_FILE = STORE_DIR / "review-session.json"
ATOMIZE_ANALYSES_DIR = STORE_DIR / "atomize-analyses"
ATOMIZE_WORKBENCHES_DIR = STORE_DIR / "atomize-workbenches"
ATOMIZE_GROUNDING_SESSIONS_DIR = STORE_DIR / "atomize-groundings"
ATOMIZE_GROUNDING_HISTORY_DIR = STORE_DIR / "atomize-grounding-history"
GROUND_SESSIONS_DIR = STORE_DIR / "ground-sessions"
RESERVED_CONTEXT_SEGMENTS = frozenset({"context.json", "checkpoints"})


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build a JSON object while rejecting duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _write_json_atomic(path: Path, data: object) -> None:
    """Write JSON through a same-directory temporary file, then replace."""
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        with open(temporary, "x", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def canonical_context_record(
    value: Context | dict[str, object],
) -> dict[str, object]:
    """Return the canonical logical direct record used for persistence CAS."""
    if isinstance(value, Context):
        return value.to_dict()
    # Non-resolving deserialization preserves every pointer while normalizing
    # supported legacy omissions such as a missing explicit order list.
    return Context.from_dict(value).to_dict()


def context_record_digest(value: Context | dict[str, object]) -> str:
    """Hash one complete logical direct Context record canonically."""
    record = canonical_context_record(value)
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ConcurrentContextUpdateError(RuntimeError):
    """A Context changed after a caller captured its expected record."""


def _context_name_parts(name: str) -> tuple[str, ...]:
    """Validate a Context name and return its POSIX namespace segments."""
    if not isinstance(name, str) or not name:
        raise ValueError("Context name must be a non-empty relative path.")
    if "\\" in name:
        raise ValueError(
            f"Invalid context name '{name}': use '/' as the namespace separator."
        )
    if ":" in name:
        raise ValueError(
            f"Invalid context name '{name}': ':' is not allowed in context names."
        )

    parts = tuple(name.split("/"))
    if any(part == "" for part in parts):
        raise ValueError(
            f"Invalid context name '{name}': leading, trailing, or repeated '/' "
            "is not allowed."
        )
    if any(part in {".", ".."} for part in parts):
        raise ValueError(
            f"Invalid context name '{name}': '.' and '..' segments are not allowed."
        )
    reserved = [
        part
        for part in parts
        if part.casefold() in RESERVED_CONTEXT_SEGMENTS
    ]
    if reserved:
        raise ValueError(
            f"Invalid context name '{name}': '{reserved[0]}' is reserved for "
            "Context storage."
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError(
            f"Invalid context name '{name}': control characters are not allowed."
        )
    return parts


def _validate_context_header(data: object, expected_name: str) -> dict:
    """Validate the minimum Context JSON structure needed for safe loading."""
    if not isinstance(data, dict):
        raise ValueError(
            f"Context file for '{expected_name}' must contain a JSON object."
        )
    if data.get("name") != expected_name:
        raise ValueError(
            f"Context file for '{expected_name}' declares a different name "
            f"('{data.get('name')}')."
        )
    if not isinstance(data.get("uid"), str) or not data["uid"]:
        raise ValueError(
            f"Context file for '{expected_name}' has no valid uid."
        )
    if not isinstance(data.get("memories"), dict):
        raise ValueError(
            f"Context file for '{expected_name}' has no valid memories object."
        )
    return data


@dataclass(frozen=True)
class QuerySource:
    """Research-only source text kept outside the normal Context namespace."""

    uid: str
    name: str
    content: str


class MemoryStore:

    def __init__(self, *, create: bool = True):
        """
        Open the store.

        Normal commands create missing store infrastructure. Read-only
        inspection commands can pass create=False to guarantee that merely
        checking absent state does not create ~/.mem or state.json.
        """
        if create:
            STORE_DIR.mkdir(parents=True, exist_ok=True)
            CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
            if not STATE_FILE.exists():
                self._write_state({"current": None})

    @contextmanager
    def _context_write_lock(self, name: str) -> Iterator[None]:
        """Serialize cooperative Context saves across local mem processes."""
        _context_name_parts(name)
        lock_dir = STORE_DIR / "context-write-locks"
        if lock_dir.is_symlink():
            raise ValueError(
                "Refusing to use a symbolic-link Context lock directory."
            )
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / (
            hashlib.sha256(name.encode("utf-8")).hexdigest() + ".lock"
        )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            # os.fdopen owns the descriptor once it succeeds. If it fails
            # before taking ownership, close the raw descriptor here.
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _state_write_lock(self) -> Iterator[None]:
        """Serialize cooperative changes to the global current Context."""
        lock_path = STORE_DIR / "state-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link state lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    # --- Global state ---

    def _read_state(self) -> dict:
        with open(STATE_FILE) as f:
            return json.load(f)

    def _write_state(self, state: dict) -> None:
        # Context switching is the final phase of several multi-file
        # operations.  Replacing an fsynced sibling keeps an interrupted write
        # from leaving state.json truncated and making rollback impossible.
        _write_json_atomic(STATE_FILE, state)

    def current_context_name(self) -> Optional[str]:
        return self._read_state().get("current")

    def set_current(self, name: str) -> None:
        with self._context_write_lock(name):
            if not self.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' not found.")
            with self._state_write_lock():
                state = self._read_state()
                state["current"] = name
                self._write_state(state)

    def set_current_context_if(
        self,
        expected_current: str,
        name: str,
        *,
        expected_context_uid: str,
        expected_context_digest: str,
    ) -> None:
        """CAS-switch to one exact Context while blocking save/delete/recreate."""
        if (
            not isinstance(expected_context_digest, str)
            or len(expected_context_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_context_digest
            )
        ):
            raise ValueError("Expected Context digest is invalid.")
        with self._context_write_lock(name):
            if not self.context_exists(name):
                raise ConcurrentContextUpdateError(
                    f"Context '{name}' no longer exists."
                )
            target = self.load_direct(name)
            if (
                target.uid != expected_context_uid
                or context_record_digest(target)
                != expected_context_digest
            ):
                raise ConcurrentContextUpdateError(
                    f"Context '{name}' changed before it could be selected."
                )
            with self._state_write_lock():
                state = self._read_state()
                if state.get("current") != expected_current:
                    raise ConcurrentContextUpdateError(
                        "The current Context changed before it could be "
                        "switched."
                    )
                state["current"] = name
                self._write_state(state)

    # --- Semantic update sessions ---

    @staticmethod
    def _load_update_session(path: Path):
        """Load and validate one cached semantic update session."""
        from memcommit.update import UpdateSession

        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Semantic update session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f, object_pairs_hook=_reject_duplicate_json_keys)
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("Semantic update session is invalid JSON.") from error
        try:
            return UpdateSession.from_dict(data)
        except ValueError as error:
            raise ValueError("Semantic update session is invalid.") from error

    @staticmethod
    def _save_update_session(path: Path, session) -> None:
        """Atomically persist one validated semantic update session."""
        from memcommit.update import UpdateSession

        if not isinstance(session, UpdateSession):
            raise TypeError("Expected an UpdateSession.")
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Semantic update session storage is invalid.")
        _write_json_atomic(path, session.to_dict())

    def load_impact_plan(self):
        """Return the cached impact plan, or None when no plan exists."""
        return self._load_update_session(IMPACT_PLAN_FILE)

    def save_impact_plan(self, session) -> None:
        """Atomically cache a non-mutating impact plan."""
        self._save_update_session(IMPACT_PLAN_FILE, session)

    def load_staged_update(self):
        """Return the active staged update, or None when none exists."""
        return self._load_update_session(STAGED_UPDATE_FILE)

    def save_staged_update(self, session) -> None:
        """Atomically save the active staged update."""
        self._save_update_session(STAGED_UPDATE_FILE, session)

    # --- Semantic review sessions ---

    @staticmethod
    def _load_review_session(path: Path):
        """Load and strictly validate the active semantic review."""
        from memcommit.review import ReviewError, ReviewSession

        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Semantic review session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(
                "Semantic review session is invalid JSON."
            ) from error
        try:
            return ReviewSession.from_dict(data)
        except (ReviewError, TypeError) as error:
            raise ValueError("Semantic review session is invalid.") from error

    def load_review_session(self):
        """Return the active semantic review, or None when none exists."""
        return self._load_review_session(REVIEW_SESSION_FILE)

    def save_review_session(self, session) -> None:
        """Atomically save one validated semantic review session."""
        from memcommit.review import ReviewError, ReviewSession

        if not isinstance(session, ReviewSession):
            raise TypeError("Expected a ReviewSession.")
        if REVIEW_SESSION_FILE.exists() and (
            not REVIEW_SESSION_FILE.is_file()
            or REVIEW_SESSION_FILE.is_symlink()
        ):
            raise ValueError("Semantic review session storage is invalid.")
        data = session.to_dict()
        # Validate the exact persisted shape before replacing a recoverable
        # review. In-memory dataclasses are mutable by the TUI controller.
        try:
            ReviewSession.from_dict(data)
        except (ReviewError, TypeError) as error:
            raise ValueError("Semantic review session is invalid.") from error
        _write_json_atomic(REVIEW_SESSION_FILE, data)

    # --- Common-grounding sessions ---

    @staticmethod
    def _ground_session_path(contract_name: str) -> Path:
        """Resolve one portable contract ID without creating active state."""
        from memcommit.ground import validate_ground_contract_name

        canonical = validate_ground_contract_name(contract_name)
        if GROUND_SESSIONS_DIR.is_symlink():
            raise ValueError(
                "Grounding session storage cannot be a symbolic link."
            )
        if (
            GROUND_SESSIONS_DIR.exists()
            and not GROUND_SESSIONS_DIR.is_dir()
        ):
            raise ValueError("Grounding session storage is invalid.")
        return GROUND_SESSIONS_DIR / f"{canonical}.json"

    def load_ground_session(self, contract_name: str):
        """Return one named grounding session, or None when it does not exist."""
        from memcommit.ground import GroundError, GroundSession

        path = self._ground_session_path(contract_name)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Grounding session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = GroundSession.from_dict(data)
            if session.contract_name != contract_name:
                raise ValueError(
                    "Saved grounding contract does not match its storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            GroundError,
            ValueError,
        ) as error:
            raise ValueError("Saved grounding session is invalid.") from error

    def save_ground_session(self, session, *, replace: bool = False) -> None:
        """Atomically persist one strictly validated grounding session."""
        from memcommit.ground import GroundError, GroundSession

        if not isinstance(session, GroundSession):
            raise TypeError("Expected a GroundSession.")
        path = self._ground_session_path(session.contract_name)
        if GROUND_SESSIONS_DIR.exists() and (
            not GROUND_SESSIONS_DIR.is_dir()
            or GROUND_SESSIONS_DIR.is_symlink()
        ):
            raise ValueError("Grounding session storage is invalid.")
        GROUND_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Grounding session storage is invalid.")
        if path.exists() and not replace:
            existing = self.load_ground_session(session.contract_name)
            if existing is not None and existing.uid != session.uid:
                raise ValueError(
                    "A different grounding session already uses this "
                    "contract name."
                )
        data = session.to_dict()
        try:
            restored = GroundSession.from_dict(data)
        except GroundError as error:
            raise ValueError("Grounding session is invalid.") from error
        if restored.contract_name != session.contract_name:
            raise ValueError("Grounding session identity changed during save.")
        _write_json_atomic(path, data)

    # --- Saved semantic analyses ---

    @staticmethod
    def _atomize_analysis_path(context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize analysis Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize analysis Context uid.")
        if ATOMIZE_ANALYSES_DIR.is_symlink():
            raise ValueError(
                "Atomize analysis storage cannot be a symbolic link."
            )
        if (
            ATOMIZE_ANALYSES_DIR.exists()
            and not ATOMIZE_ANALYSES_DIR.is_dir()
        ):
            raise ValueError("Atomize analysis storage is invalid.")
        return ATOMIZE_ANALYSES_DIR / f"{canonical}.json"

    def load_atomize_analysis(self, context_uid: str):
        """Return one Context's latest saved atomize preview, or None."""
        from memcommit.atomize import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )

        path = self._atomize_analysis_path(context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize analysis storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeAnalysisSession.from_dict(data)
            if session.context_uid != context_uid:
                raise ValueError(
                    "Saved atomize analysis Context identity does not match "
                    "its storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            ValueError,
            AtomizeImpactError,
        ) as error:
            raise ValueError("Saved atomize analysis is invalid.") from error

    def save_atomize_analysis(self, session) -> None:
        """Atomically persist a validated, non-applying atomize preview."""
        from memcommit.atomize import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )

        if not isinstance(session, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        path = self._atomize_analysis_path(session.context_uid)
        if ATOMIZE_ANALYSES_DIR.exists() and (
            not ATOMIZE_ANALYSES_DIR.is_dir()
            or ATOMIZE_ANALYSES_DIR.is_symlink()
        ):
            raise ValueError("Atomize analysis storage is invalid.")
        ATOMIZE_ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize analysis storage is invalid.")
        data = session.to_dict()
        try:
            AtomizeAnalysisSession.from_dict(data)
        except AtomizeImpactError as error:
            raise ValueError("Atomize analysis is invalid.") from error
        _write_json_atomic(path, data)

    def delete_atomize_analysis(self, context_uid: str) -> None:
        """Remove one derived analysis artifact during failed save-as cleanup."""
        path = self._atomize_analysis_path(context_uid)
        if path.exists():
            if not path.is_file() or path.is_symlink():
                raise ValueError("Atomize analysis storage is invalid.")
            path.unlink()

    # --- Context-bound atomize workbenches ---

    @staticmethod
    def _atomize_workbench_path(context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                "Invalid atomize workbench Context uid."
            ) from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize workbench Context uid.")
        if ATOMIZE_WORKBENCHES_DIR.is_symlink():
            raise ValueError(
                "Atomize workbench storage cannot be a symbolic link."
            )
        if (
            ATOMIZE_WORKBENCHES_DIR.exists()
            and not ATOMIZE_WORKBENCHES_DIR.is_dir()
        ):
            raise ValueError("Atomize workbench storage is invalid.")
        return ATOMIZE_WORKBENCHES_DIR / f"{canonical}.json"

    def load_atomize_workbench(self, analysis):
        """Load mutable state only against one exact saved analysis."""
        from memcommit.atomize import AtomizeAnalysisSession
        from memcommit.atomize_workbench import (
            AtomizeWorkbenchError,
            AtomizeWorkbenchSession,
            atomize_workbench_issue_projection,
        )

        if not isinstance(analysis, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        path = self._atomize_workbench_path(analysis.context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize workbench storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeWorkbenchSession.from_dict(
                data,
                issues=atomize_workbench_issue_projection(analysis),
            )
            if (
                session.analysis_uid != analysis.uid
                or session.context_uid != analysis.context_uid
            ):
                raise ValueError(
                    "Saved atomize workbench identity does not match its "
                    "analysis or storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            AtomizeWorkbenchError,
            ValueError,
        ) as error:
            raise ValueError("Saved atomize workbench is invalid.") from error

    def save_atomize_workbench(self, session) -> None:
        """Atomically persist one Context-bound mutable workbench."""
        from memcommit.atomize_workbench import (
            AtomizeWorkbenchError,
            AtomizeWorkbenchSession,
            atomize_workbench_issue_projection,
        )

        if not isinstance(session, AtomizeWorkbenchSession):
            raise TypeError("Expected an AtomizeWorkbenchSession.")
        path = self._atomize_workbench_path(session.context_uid)
        if ATOMIZE_WORKBENCHES_DIR.exists() and (
            not ATOMIZE_WORKBENCHES_DIR.is_dir()
            or ATOMIZE_WORKBENCHES_DIR.is_symlink()
        ):
            raise ValueError("Atomize workbench storage is invalid.")
        ATOMIZE_WORKBENCHES_DIR.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize workbench storage is invalid.")
        data = session.to_dict()
        try:
            AtomizeWorkbenchSession.from_dict(
                data,
                issues=session.issues,
            )
        except AtomizeWorkbenchError as error:
            raise ValueError("Atomize workbench is invalid.") from error
        analysis = self.load_atomize_analysis(session.context_uid)
        if analysis is None or not session.matches_analysis(
            analysis_uid=analysis.uid,
            context_uid=analysis.context_uid,
            context_name=analysis.context_name,
            context_digest=analysis.context_digest,
            issues=atomize_workbench_issue_projection(analysis),
        ):
            raise ValueError(
                "Atomize workbench does not match the saved analysis."
            )
        _write_json_atomic(path, data)

    def delete_atomize_workbench(self, context_uid: str) -> None:
        """Remove derived UI state during failed save-as cleanup."""
        path = self._atomize_workbench_path(context_uid)
        if path.exists():
            if not path.is_file() or path.is_symlink():
                raise ValueError("Atomize workbench storage is invalid.")
            path.unlink()

    # --- Conversational atomize grounding sessions ---

    @staticmethod
    def _atomize_grounding_session_path(context_uid: str) -> Path:
        """Resolve one Context-bound dialogue without trusting path text."""
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                "Invalid atomize grounding Context uid."
            ) from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize grounding Context uid.")
        if ATOMIZE_GROUNDING_SESSIONS_DIR.is_symlink():
            raise ValueError(
                "Atomize grounding storage cannot be a symbolic link."
            )
        if (
            ATOMIZE_GROUNDING_SESSIONS_DIR.exists()
            and not ATOMIZE_GROUNDING_SESSIONS_DIR.is_dir()
        ):
            raise ValueError("Atomize grounding storage is invalid.")
        return ATOMIZE_GROUNDING_SESSIONS_DIR / f"{canonical}.json"

    @staticmethod
    def _atomize_grounding_history_dir(context_uid: str) -> Path:
        """Resolve one Context's immutable terminal-dialogue archive."""
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                "Invalid atomize grounding Context uid."
            ) from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize grounding Context uid.")
        if ATOMIZE_GROUNDING_HISTORY_DIR.is_symlink():
            raise ValueError(
                "Atomize grounding history cannot be a symbolic link."
            )
        if (
            ATOMIZE_GROUNDING_HISTORY_DIR.exists()
            and not ATOMIZE_GROUNDING_HISTORY_DIR.is_dir()
        ):
            raise ValueError("Atomize grounding history is invalid.")
        directory = ATOMIZE_GROUNDING_HISTORY_DIR / canonical
        if directory.is_symlink() or (
            directory.exists() and not directory.is_dir()
        ):
            raise ValueError("Atomize grounding history is invalid.")
        return directory

    @classmethod
    def _atomize_grounding_history_path(
        cls,
        context_uid: str,
        session_uid: str,
    ) -> Path:
        try:
            canonical_session = str(uuid.UUID(session_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                "Invalid atomize grounding session uid."
            ) from error
        if canonical_session != session_uid:
            raise ValueError("Invalid atomize grounding session uid.")
        return (
            cls._atomize_grounding_history_dir(context_uid)
            / f"{canonical_session}.json"
        )

    def load_atomize_grounding_session(self, context_uid: str):
        """Return one Context's latest atomize grounding dialogue, if any."""
        from memcommit.atomize_grounding import (
            AtomizeGroundingError,
            AtomizeGroundingSession,
        )

        path = self._atomize_grounding_session_path(context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize grounding storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeGroundingSession.from_dict(data)
            if session.bindings.context_uid != context_uid:
                raise ValueError(
                    "Saved atomize grounding Context identity does not match "
                    "its storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            AtomizeGroundingError,
            ValueError,
        ) as error:
            raise ValueError(
                "Saved atomize grounding session is invalid."
            ) from error

    def save_atomize_grounding_session(self, session) -> None:
        """Atomically persist one strict Context-bound grounding dialogue."""
        from memcommit.atomize_grounding import (
            AtomizeGroundingError,
            AtomizeGroundingSession,
        )

        if not isinstance(session, AtomizeGroundingSession):
            raise TypeError("Expected an AtomizeGroundingSession.")
        path = self._atomize_grounding_session_path(
            session.bindings.context_uid
        )
        if ATOMIZE_GROUNDING_SESSIONS_DIR.exists() and (
            not ATOMIZE_GROUNDING_SESSIONS_DIR.is_dir()
            or ATOMIZE_GROUNDING_SESSIONS_DIR.is_symlink()
        ):
            raise ValueError("Atomize grounding storage is invalid.")
        ATOMIZE_GROUNDING_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize grounding storage is invalid.")
        data = session.to_dict()
        try:
            restored = AtomizeGroundingSession.from_dict(data)
        except AtomizeGroundingError as error:
            raise ValueError(
                "Atomize grounding session is invalid."
            ) from error
        if (
            restored.uid != session.uid
            or restored.bindings.context_uid
            != session.bindings.context_uid
        ):
            raise ValueError(
                "Atomize grounding identity changed during save."
            )
        if session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}:
            # Terminal conversations are evidence, not disposable UI state.
            # Archive them before replacing the latest slot so a subsequent
            # grounding round cannot silently erase reviewer comments.
            history_path = self._atomize_grounding_history_path(
                session.bindings.context_uid,
                session.uid,
            )
            history_dir = history_path.parent
            ATOMIZE_GROUNDING_HISTORY_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )
            history_dir.mkdir(exist_ok=True)
            if history_path.exists() or history_path.is_symlink():
                if not history_path.is_file() or history_path.is_symlink():
                    raise ValueError("Atomize grounding history is invalid.")
                with open(history_path, encoding="utf-8") as f:
                    archived = json.load(
                        f,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                if archived != data:
                    raise ValueError(
                        "Atomize grounding history is immutable."
                    )
            else:
                _write_json_atomic(history_path, data)
        _write_json_atomic(path, data)

    def load_atomize_grounding_history(
        self,
        context_uid: str,
    ) -> list:
        """Load immutable terminal dialogues for one exact Context."""
        from memcommit.atomize_grounding import (
            AtomizeGroundingError,
            AtomizeGroundingSession,
        )

        directory = self._atomize_grounding_history_dir(context_uid)
        if not directory.exists():
            return []
        sessions = []
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Atomize grounding history is invalid.")
            try:
                with open(path, encoding="utf-8") as f:
                    value = json.load(
                        f,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                session = AtomizeGroundingSession.from_dict(value)
            except (
                json.JSONDecodeError,
                AtomizeGroundingError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Atomize grounding history is invalid."
                ) from error
            if (
                session.bindings.context_uid != context_uid
                or session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}
                or path.stem != session.uid
            ):
                raise ValueError("Atomize grounding history is invalid.")
            sessions.append(session)
        return sessions

    # --- Context paths ---

    def _context_dir(self, name: str) -> Path:
        parts = _context_name_parts(name)
        path = CONTEXTS_DIR.joinpath(*parts)
        candidate = CONTEXTS_DIR
        for part in parts:
            candidate /= part
            if candidate.is_symlink():
                raise ValueError(
                    f"Invalid context name '{name}': symbolic links are not "
                    "allowed in context namespaces."
                )
            if candidate.exists() and not candidate.is_dir():
                raise ValueError(
                    f"Invalid context name '{name}': namespace component "
                    f"'{candidate.name}' is not a directory."
                )
        contexts_root = CONTEXTS_DIR.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Invalid context name '{name}': path escapes the context store."
            )
        return path

    def _context_file(self, name: str) -> Path:
        return self._context_dir(name) / "context.json"

    def _checkpoints_dir(self, name: str) -> Path:
        path = self._context_dir(name) / "checkpoints"
        if path.is_symlink():
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' through a "
                "symbolic link."
            )
        contexts_root = CONTEXTS_DIR.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' outside the "
                "context store."
            )
        return path

    def context_exists(self, name: str) -> bool:
        try:
            context_file = self._context_file(name)
        except (OSError, TypeError, ValueError):
            return False
        return context_file.is_file() and not context_file.is_symlink()

    def list_context_names(self) -> list[str]:
        names: list[str] = []
        for context_file in CONTEXTS_DIR.rglob("context.json"):
            if not context_file.is_file() or context_file.is_symlink():
                continue
            name = context_file.parent.relative_to(CONTEXTS_DIR).as_posix()
            try:
                _context_name_parts(name)
            except ValueError:
                continue
            try:
                with open(context_file) as f:
                    data = json.load(f)
                _validate_context_header(data, name)
            except (OSError, json.JSONDecodeError):
                continue
            except ValueError:
                continue

            names.append(name)
        return sorted(names)

    def _assert_context_storage_available(self, name: str) -> None:
        """Allow a new root Context when only namespace directories predate it."""
        context_dir = self._context_dir(name)
        if not context_dir.exists():
            return
        invalid_entries = [
            entry.name
            for entry in context_dir.iterdir()
            if (
                entry.is_symlink()
                or not entry.is_dir()
                or entry.name.casefold() in RESERVED_CONTEXT_SEGMENTS
            )
        ]
        if invalid_entries:
            raise ValueError(
                f"Cannot create context '{name}': its storage directory already "
                "exists and is not empty; only child namespace directories may "
                "precede a root Context. Invalid entries: "
                + ", ".join(sorted(invalid_entries))
            )

    @staticmethod
    def _prune_empty_namespace_dirs(start: Path) -> None:
        """Remove empty namespace directories without removing CONTEXTS_DIR."""
        candidate = start
        while candidate != CONTEXTS_DIR:
            try:
                candidate.rmdir()
            except OSError:
                break
            candidate = candidate.parent

    # --- Load / Save ---

    def _load_direct_memory(
        self,
        context_name: str,
        expected_context_uid: str,
        memory_uid: str,
    ) -> Memory | None:
        """
        Resolve one directly owned Memory without recursively loading its Context.

        Reading the raw context file avoids MemoryRef chains and Context embed
        cycles. The Context uid check prevents a deleted/recreated context with
        the same name from silently becoming the new target.
        """
        if not self.context_exists(context_name):
            return None
        with open(self._context_file(context_name)) as f:
            data = json.load(f)
        try:
            data = _validate_context_header(data, context_name)
        except ValueError:
            return None
        if data.get("uid") != expected_context_uid:
            return None

        item = data.get("memories", {}).get(memory_uid)
        if (
            not isinstance(item, dict)
            or item.get("type") != "memory"
            or item.get("uid") != memory_uid
        ):
            return None
        return Memory.from_dict(item)

    def load(self, name: str, _loading: frozenset[str] = frozenset()) -> Context:
        """Load a context by name, resolving embedded context refs as live loads."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)

        def loader(ref_name: str) -> Context | None:
            if ref_name in _loading:
                return None  # break circular reference
            if not self.context_exists(ref_name):
                return None
            return self.load(ref_name, _loading | {name})

        try:
            ctx = Context.from_dict(
                data,
                loader=loader,
                memory_loader=self._load_direct_memory,
            )
            # A loaded Context carries the exact logical version it was based
            # on. Every later ordinary save uses it for optimistic concurrency
            # so a stale writer cannot erase a completed operation.
            ctx._store_digest = context_record_digest(data)
            return ctx
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Context file for '{name}' has an invalid memory structure: {e}"
            ) from e

    def load_direct(self, name: str) -> Context:
        """
        Load one Context record without opening any referenced Context files.

        Read-only operations whose scope is explicitly limited to directly
        owned Memories must not resolve embedded Contexts or MemoryRef targets
        before filtering. QueryContextRefs remain opaque under both load paths.
        """
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)
        try:
            ctx = Context.from_dict(data)
            ctx._store_digest = context_record_digest(data)
            return ctx
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Context file for '{name}' has an invalid memory structure: {e}"
            ) from e

    def load_for_update(self, name: str) -> Context:
        """Load a Context without permitting unresolved direct Context refs.

        Normal ``load`` intentionally tolerates a missing embedded Context for
        read paths. A mutating command must be stricter: serializing that
        partially resolved object would silently erase the unresolved pointer.
        """
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)
        direct_context_refs = {
            uid: item.get("name")
            for uid, item in data["memories"].items()
            if isinstance(item, dict) and item.get("type") == "context_ref"
        }
        ctx = self.load(name)
        for uid, expected_name in direct_context_refs.items():
            item = ctx.memories.get(uid)
            if (
                not isinstance(item, Context)
                or item.name != expected_name
            ):
                raise ValueError(
                    f"Context '{name}' contains an unavailable embedded "
                    f"Context reference '{expected_name}'. Refusing to save "
                    "a partial load."
                )
        return ctx

    def load_current(self) -> Context:
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load(name)

    def load_current_direct(self) -> Context:
        """Load the current Context through the non-resolving direct path."""
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load_direct(name)

    def assert_context_creatable(self, name: str) -> None:
        """Fail before expensive work when a new Context cannot use this name."""
        _context_name_parts(name)
        if self.context_exists(name):
            raise FileExistsError(f"Context '{name}' already exists.")
        self._assert_context_storage_available(name)

    def save(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
        *,
        expected_context_digest: str | None = None,
    ) -> Checkpoint | None:
        """Persist a Context, optionally only if its disk record is unchanged."""
        if expected_context_digest is None:
            expected_context_digest = getattr(ctx, "_store_digest", None)
        with self._context_write_lock(ctx.name):
            checkpoint = self._save_locked(
                ctx,
                auto_checkpoint,
                expected_context_digest=expected_context_digest,
            )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def create_context(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
    ) -> Checkpoint | None:
        """Create one new Context without overwriting a concurrent owner."""
        with self._context_write_lock(ctx.name):
            checkpoint = self._save_locked(
                ctx,
                auto_checkpoint,
                expected_context_digest=None,
                require_new=True,
            )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def _save_locked(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint],
        *,
        expected_context_digest: str | None,
        require_new: bool = False,
    ) -> Checkpoint | None:
        """Save while holding this Context's cooperative process lock."""
        ctx_dir = self._context_dir(ctx.name)
        context_file = self._context_file(ctx.name)
        if context_file.is_symlink():
            raise ValueError(
                f"Refusing to write context '{ctx.name}' through a symbolic link."
            )
        context_preexisting = self.context_exists(ctx.name)
        if require_new and context_preexisting:
            raise FileExistsError(f"Context '{ctx.name}' already exists.")
        if expected_context_digest is not None:
            if (
                len(expected_context_digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in expected_context_digest
                )
            ):
                raise ValueError("Expected Context digest is invalid.")
            if not context_preexisting:
                raise ConcurrentContextUpdateError(
                    f"Context '{ctx.name}' no longer exists."
                )
            with open(context_file, encoding="utf-8") as file:
                current_record = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            current_record = _validate_context_header(
                current_record,
                ctx.name,
            )
            if context_record_digest(current_record) != expected_context_digest:
                raise ConcurrentContextUpdateError(
                    f"Context '{ctx.name}' changed before it could be saved."
                )
        if not context_preexisting:
            self._assert_context_storage_available(ctx.name)
        ctx_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir = self._checkpoints_dir(ctx.name)
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        created_checkpoint: Checkpoint | None = None
        try:
            if auto_checkpoint is not None:
                created_checkpoint = self.checkpoint(
                    ctx,
                    message=auto_checkpoint.description,
                    command=auto_checkpoint.command,
                    args=auto_checkpoint.args,
                    description=auto_checkpoint.description,
                    auto=True,
                    _allow_unsaved=True,
                )
            _write_json_atomic(context_file, ctx.to_dict())
        except Exception as error:
            cleanup_error: Exception | None = None
            if created_checkpoint is not None:
                try:
                    matches = list(
                        checkpoints_dir.glob(
                            f"*-{created_checkpoint.uid[:8]}.json"
                        )
                    )
                    for path in matches:
                        if path.is_symlink() or not path.is_file():
                            continue
                        with open(path) as f:
                            value = json.load(f)
                        if value.get("uid") == created_checkpoint.uid:
                            path.unlink()
                            break
                except Exception as candidate:
                    cleanup_error = candidate
            if not context_preexisting and not context_file.exists():
                try:
                    checkpoints_dir.rmdir()
                    self._prune_empty_namespace_dirs(ctx_dir)
                except OSError:
                    # A pre-existing child namespace or an unexpected artifact
                    # is never removed as part of rollback.
                    pass
            if cleanup_error is not None:
                raise RuntimeError(
                    "Context save failed and its automatic checkpoint could "
                    "not be rolled back."
                ) from cleanup_error
            raise error
        return created_checkpoint

    # --- Query-only research sources ---

    @staticmethod
    def _canonical_query_source_uid(source_uid: str) -> str:
        if not isinstance(source_uid, str):
            raise ValueError("Query source uid must be a canonical UUID.")
        try:
            parsed = uuid.UUID(source_uid)
        except (AttributeError, TypeError, ValueError) as e:
            raise ValueError("Query source uid must be a canonical UUID.") from e
        canonical = str(parsed)
        if source_uid != canonical:
            raise ValueError("Query source uid must be a canonical UUID.")
        return canonical

    def _query_source_dir(self, source_uid: str) -> Path:
        canonical = self._canonical_query_source_uid(source_uid)
        if QUERY_SOURCES_DIR.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        source_dir = QUERY_SOURCES_DIR / canonical
        if source_dir.is_symlink():
            raise ValueError("Query source directory cannot be a symbolic link.")
        root = QUERY_SOURCES_DIR.resolve()
        resolved = source_dir.resolve(strict=False)
        if root not in resolved.parents:
            raise ValueError("Query source path escapes query source storage.")
        return source_dir

    def _query_source_file(self, source_uid: str) -> Path:
        source_file = self._query_source_dir(source_uid) / "source.json"
        if source_file.is_symlink():
            raise ValueError("Query source file cannot be a symbolic link.")
        return source_file

    def create_query_source(self, name: str, content: str) -> QuerySource:
        """
        Store a concealed research source outside normal Context storage.

        This is UI-level concealment for a study prototype, not a security
        boundary. The local user can still read files under ~/.mem.
        """
        _context_name_parts(name)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Query source content must be non-empty text.")
        if QUERY_SOURCES_DIR.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        QUERY_SOURCES_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(QUERY_SOURCES_DIR, 0o700)

        source = QuerySource(uid=str(uuid.uuid4()), name=name, content=content)
        source_dir = self._query_source_dir(source.uid)
        source_file = self._query_source_file(source.uid)
        source_dir.mkdir(mode=0o700)
        os.chmod(source_dir, 0o700)
        try:
            with open(source_file, "x", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": 1,
                        "uid": source.uid,
                        "name": source.name,
                        "content": source.content,
                    },
                    f,
                    indent=2,
                )
            os.chmod(source_file, 0o600)
        except Exception:
            if source_file.exists() and not source_file.is_symlink():
                source_file.unlink()
            source_dir.rmdir()
            raise
        return source

    def load_query_source(
        self,
        source_uid: str,
        *,
        expected_name: str,
    ) -> QuerySource:
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        with open(source_file, encoding="utf-8") as f:
            data = json.load(f)
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != 1
            or data.get("uid") != source_uid
            or data.get("name") != expected_name
            or not isinstance(data.get("content"), str)
        ):
            raise ValueError("Query source identity or structure is invalid.")
        return QuerySource(
            uid=data["uid"],
            name=data["name"],
            content=data["content"],
        )

    def delete_query_source(self, source_uid: str) -> None:
        """Delete one exact hidden source, used to roll back failed setup."""
        source_dir = self._query_source_dir(source_uid)
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        source_file.unlink()
        source_dir.rmdir()

    def copy_checkpoints(self, source_name: str, target_name: str) -> None:
        """Copy all checkpoint files from source into target's checkpoints directory."""
        src_dir = self._checkpoints_dir(source_name)
        tgt_dir = self._checkpoints_dir(target_name)
        tgt_dir.mkdir(parents=True, exist_ok=True)
        if src_dir.exists():
            for path in sorted(src_dir.glob("*.json")):
                if path.is_symlink() or not path.is_file():
                    continue
                destination = tgt_dir / path.name
                if destination.is_symlink():
                    raise ValueError(
                        f"Refusing to copy checkpoint to '{target_name}' through "
                        "a symbolic link."
                    )
                shutil.copy2(path, destination)

    def delete(self, name: str) -> None:
        """Delete one Context while preserving descendant Context namespaces."""
        with self._context_write_lock(name):
            self._delete_locked(name)

    def _delete_locked(self, name: str) -> None:
        """Delete one Context while its cooperative write lock is held."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        context_uid = self.load_direct(name).uid
        # Validate the derived-artifact path before deleting the primary
        # Context so a malformed analysis store cannot turn cleanup into a
        # surprising partial operation.
        try:
            canonical_context_uid = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError):
            canonical_context_uid = None
        from memcommit.comparison_store import (
            comparison_paths_for_context,
            delete_comparison_paths,
        )

        # Compare artifacts snapshot both sources and derived explanations.
        # Their privacy lifetime therefore ends when either bound source is
        # deleted, regardless of which side was the display reference.
        comparison_paths = (
            comparison_paths_for_context(context_uid)
            if canonical_context_uid == context_uid
            else ()
        )
        analysis_path = (
            self._atomize_analysis_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        workbench_path = (
            self._atomize_workbench_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        grounding_path = (
            self._atomize_grounding_session_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        grounding_history_dir = (
            self._atomize_grounding_history_dir(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        for artifact, label in (
            (analysis_path, "analysis"),
            (workbench_path, "workbench"),
            (grounding_path, "grounding"),
        ):
            if (
                artifact is not None
                and (artifact.exists() or artifact.is_symlink())
                and (not artifact.is_file() or artifact.is_symlink())
            ):
                raise ValueError(f"Atomize {label} storage is invalid.")
        if (
            grounding_history_dir is not None
            and grounding_history_dir.exists()
            and any(
                child.is_symlink()
                or not child.is_file()
                or child.suffix != ".json"
                for child in grounding_history_dir.iterdir()
            )
        ):
            raise ValueError("Atomize grounding history is invalid.")
        review_session = self.load_review_session()
        delete_review_session = (
            review_session is not None
            and review_session.context_uid == context_uid
            and review_session.context_name == name
        )
        ctx_dir = self._context_dir(name)
        context_file = self._context_file(name)
        checkpoints_dir = self._checkpoints_dir(name)
        if checkpoints_dir.exists() and not checkpoints_dir.is_dir():
            raise ValueError(
                f"Cannot delete context '{name}': its checkpoints path is not "
                "a directory."
            )

        # Move exact Context artifacts aside before deletion. Renames within a
        # directory are atomic, and descendants are never part of these paths.
        # If staging fails, restore the Context file before surfacing the error.
        token = uuid.uuid4().hex
        staged_context = ctx_dir / f".context.json.delete-{token}"
        staged_checkpoints = ctx_dir / f".checkpoints.delete-{token}"
        context_file.rename(staged_context)
        checkpoints_staged = False
        try:
            if checkpoints_dir.exists():
                checkpoints_dir.rename(staged_checkpoints)
                checkpoints_staged = True
        except OSError:
            staged_context.rename(context_file)
            raise

        try:
            staged_context.unlink()
        except OSError:
            if checkpoints_staged:
                staged_checkpoints.rename(checkpoints_dir)
            staged_context.rename(context_file)
            raise

        with self._state_write_lock():
            state = self._read_state()
            if state.get("current") == name:
                state["current"] = None
                self._write_state(state)
        if checkpoints_staged:
            shutil.rmtree(staged_checkpoints)
        if analysis_path is not None and analysis_path.exists():
            analysis_path.unlink()
        if workbench_path is not None and workbench_path.exists():
            # Workbench responses may contain free-form user context. They are
            # scoped to the deleted Context and must not survive it.
            workbench_path.unlink()
        if grounding_path is not None and grounding_path.exists():
            # Grounding turns retain the reviewer's words verbatim. Keeping
            # them after their exact Context is gone would be both misleading
            # state and an avoidable privacy leak.
            grounding_path.unlink()
        delete_comparison_paths(comparison_paths)
        if (
            grounding_history_dir is not None
            and grounding_history_dir.exists()
        ):
            # Terminal dialogues contain the same verbatim local evidence as
            # the latest slot and share the deleted Context's privacy lifetime.
            shutil.rmtree(grounding_history_dir)
            try:
                ATOMIZE_GROUNDING_HISTORY_DIR.rmdir()
            except OSError:
                pass
        if delete_review_session and REVIEW_SESSION_FILE.exists():
            # Review answers may contain user-supplied local context. Once
            # their exact Context is deleted, retaining that global artifact
            # would be both misleading state and an avoidable privacy leak.
            REVIEW_SESSION_FILE.unlink()
        self._prune_empty_namespace_dirs(ctx_dir)

    # --- Checkpoints ---

    # Storage design note:
    # Checkpoints intentionally embed a complete serialization of the Context's
    # direct state.  At the current research-prototype scale, this keeps
    # persistence, recovery, and migration simpler than an object store; nested
    # Contexts and MemoryRefs are already serialized as pointers rather than
    # recursively copied.  If Contexts or histories grow substantially, retain
    # the same logical snapshot semantics while moving Memory contents to
    # content-addressed blobs and having checkpoints point to ordered tree
    # manifests.  A pure delta/event chain is not required by the current model.
    def checkpoint(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        _allow_unsaved: bool = False,
    ) -> Checkpoint:
        """Save a point-in-time snapshot of ctx's current state."""
        if not _allow_unsaved and not self.context_exists(ctx.name):
            raise FileNotFoundError(
                f"Context '{ctx.name}' must be saved before checkpointing."
            )
        cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command=command,
            args=args,
            description=description,
            auto=auto,
        )
        ts = cp.timestamp.strftime("%Y%m%dT%H%M%S")
        slug = message[:24].replace(" ", "-").replace("/", "-") if message else (command or "checkpoint")
        cp_dir = self._checkpoints_dir(ctx.name)
        cp_dir.mkdir(parents=True, exist_ok=True)
        cp_file = cp_dir / f"{ts}-{slug}-{cp.uid[:8]}.json"
        if cp_file.is_symlink():
            raise ValueError(
                f"Refusing to write checkpoint for '{ctx.name}' through a "
                "symbolic link."
            )
        _write_json_atomic(
            cp_file,
            {
                "uid": cp.uid,
                "message": cp.message,
                "timestamp": cp.timestamp.isoformat(),
                "snapshot": cp.snapshot,
                "command": cp.command,
                "args": cp.args,
                "description": cp.description,
                "auto": cp.auto,
            },
        )
        return cp

    def list_checkpoints(self, name: str) -> list[dict]:
        """Return checkpoints for a context, sorted newest-first."""
        cp_dir = self._checkpoints_dir(name)
        if not cp_dir.exists():
            return []
        entries = []
        for path in sorted(cp_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            with open(path) as f:
                entries.append(json.load(f))
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)

    def revert(
        self, ctx_name: str, uid_prefix: str, keep_history: bool = False
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert one Context while holding its cooperative write lock."""
        with self._context_write_lock(ctx_name):
            return self._revert_locked(
                ctx_name,
                uid_prefix,
                keep_history=keep_history,
            )

    def _revert_locked(
        self,
        ctx_name: str,
        uid_prefix: str,
        *,
        keep_history: bool,
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert context to a checkpoint. Returns (pre_revert_cp, target_cp).

        By default, checkpoints newer than the target are removed and the
        pre-revert snapshot is appended as the new head. If the target is itself
        a pre-revert checkpoint carrying a log_snapshot, the full original log
        is rebuilt from that snapshot instead of just truncating.

        Pass keep_history=True to leave all checkpoint files untouched.
        """
        entries = self.list_checkpoints(ctx_name)  # captured before any mutations
        matches = [e for e in entries if e["uid"].startswith(uid_prefix)]
        if not matches:
            raise KeyError(f"No checkpoint with uid prefix '{uid_prefix}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous prefix '{uid_prefix}' matches {len(matches)} checkpoints."
            )

        target_data = matches[0]
        target_ts = target_data["timestamp"]
        ctx = self.load(ctx_name)
        cp_dir = self._checkpoints_dir(ctx_name)

        if not keep_history:
            log_snapshot = (target_data.get("args") or {}).get("log_snapshot")

            if log_snapshot is not None:
                # Target carries a log snapshot — fully restore the log from it
                for path in cp_dir.glob("*.json"):
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                for entry in sorted(log_snapshot, key=lambda x: x["timestamp"]):
                    ts_file = datetime.fromisoformat(entry["timestamp"]).strftime("%Y%m%dT%H%M%S")
                    fname = f"{ts_file}-{entry['uid'][:8]}.json"
                    cp_file = cp_dir / fname
                    if cp_file.is_symlink():
                        raise ValueError(
                            f"Refusing to restore checkpoint for '{ctx_name}' "
                            "through a symbolic link."
                        )
                    with open(cp_file, "w") as f:
                        json.dump(entry, f, indent=2)
            else:
                # Simple truncation: remove checkpoints newer than target
                for path in cp_dir.glob("*.json"):
                    if path.is_symlink() or not path.is_file():
                        continue
                    with open(path) as f:
                        entry_data = json.load(f)
                    if entry_data["timestamp"] > target_ts:
                        path.unlink()

        # Strip nested log_snapshots before storing to prevent recursive size growth
        thin_entries = []
        for e in entries:
            args = e.get("args") or {}
            if "log_snapshot" in args:
                e = {**e, "args": {k: v for k, v in args.items() if k != "log_snapshot"}}
            thin_entries.append(e)

        pre_cp = self.checkpoint(
            ctx,
            message=f"Pre-revert to [{target_data['uid'][:8]}] — revert here to undo",
            command="revert",
            args={"target_uid": target_data["uid"], "log_snapshot": thin_entries},
            description=f"Pre-revert to [{target_data['uid'][:8]}] — revert here to undo",
            auto=True,
        )

        def loader(ref_name: str) -> "Context | None":
            if not self.context_exists(ref_name):
                return None
            return self.load(ref_name)

        # A branch inherits checkpoint files whose snapshots still carry the
        # source Context identity. Restore their contents into the Context the
        # caller requested instead of writing back to the source Context.
        restored_snapshot = {
            **target_data["snapshot"],
            "uid": ctx.uid,
            "name": ctx.name,
        }
        restored = Context.from_dict(
            restored_snapshot,
            loader=loader,
            memory_loader=self._load_direct_memory,
        )
        self._save_locked(
            restored,
            None,
            expected_context_digest=ctx._store_digest,
        )
        restored._store_digest = context_record_digest(restored)

        target_cp = Checkpoint(
            uid=target_data["uid"],
            message=target_data.get("message", ""),
            timestamp=datetime.fromisoformat(target_data["timestamp"]),
            snapshot=target_data["snapshot"],
            command=target_data.get("command"),
            args=target_data.get("args"),
            description=target_data.get("description"),
            auto=target_data.get("auto", False),
        )
        return pre_cp, target_cp
