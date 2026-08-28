"""Persist Review sessions, retained Sources, and session history."""

from __future__ import annotations
import json
import uuid
from pathlib import Path
from memcommit.core.context import Context


from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)
from ..infrastructure.protection import _profile_write_guarded


class _ReviewStateStoreMixin:
    """Focused slice of the temporary Store assembly."""

    @staticmethod
    def _load_review_session(path: Path):
        """Load and strictly validate the active semantic review."""
        from memcommit.application.operations.review.model import (
            ReviewError,
            ReviewSession,
        )

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
            raise ValueError("Semantic review session is invalid JSON.") from error
        try:
            return ReviewSession.from_dict(data)
        except (ReviewError, TypeError) as error:
            raise ValueError("Semantic review session is invalid.") from error

    def load_review_session(self):
        """Return the active semantic review, or None when none exists."""
        return self._load_review_session(self.review_session_file)

    def _review_session_history_path(self, session_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(session_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid semantic review session uid.") from error
        if canonical != session_uid:
            raise ValueError("Invalid semantic review session uid.")
        return self.review_session_history_dir / f"{canonical}.json"

    def _review_session_source_path(self, session_uid: str) -> Path:
        # Source snapshots share the same UID grammar as terminal histories,
        # but are written when the review is first saved so later Context
        # changes cannot rewrite the evidence it actually displayed.
        canonical = self._review_session_history_path(session_uid).stem
        return self.review_session_sources_dir / f"{canonical}.json"

    def load_review_session_source(self, session_uid: str) -> Context:
        """Load the immutable direct-Context frame bound to one Review UID."""

        from memcommit.application.operations.review.model import direct_context_digest

        session = self.load_review_session_by_uid(session_uid)
        path = self._review_session_source_path(session_uid)
        if not path.exists():
            raise FileNotFoundError(
                f"Review source snapshot '{session_uid}' is unavailable."
            )
        if not path.is_file() or path.is_symlink():
            raise ValueError("Semantic review source storage is invalid.")
        try:
            with open(path, encoding="utf-8") as handle:
                context = Context.from_dict(
                    json.load(
                        handle,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("Semantic review source storage is invalid.") from error
        if (
            context.uid != session.context_uid
            or context.name != session.context_name
            or direct_context_digest(context) != session.context_digest
        ):
            raise ValueError("Semantic review source snapshot is invalid.")
        return context

    def _retain_review_session_source(self, session) -> bool:
        """Persist the initial source frame once when it is still available."""

        from memcommit.application.operations.review.model import direct_context_digest

        path = self._review_session_source_path(session.uid)
        if path.exists() or path.is_symlink():
            if not path.is_file() or path.is_symlink():
                raise ValueError("Semantic review source storage is invalid.")
            return False
        try:
            context = self.load_direct(session.context_name)
        except FileNotFoundError:
            return False
        if (
            context.uid != session.context_uid
            or direct_context_digest(context) != session.context_digest
        ):
            # A legacy session may first be saved again only after its Source
            # has changed. Do not fabricate an historical frame from new data.
            return False
        if self.review_session_sources_dir.exists() and (
            not self.review_session_sources_dir.is_dir()
            or self.review_session_sources_dir.is_symlink()
        ):
            raise ValueError("Semantic review source storage is invalid.")
        self.review_session_sources_dir.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, context.to_dict())
        return True

    def load_review_session_history(self, session_uid: str):
        """Load one immutable displaced terminal ReviewSession by exact UID."""

        path = self._review_session_history_path(session_uid)
        session = self._load_review_session(path)
        if session is None:
            raise FileNotFoundError(f"Review session '{session_uid}' is unavailable.")
        if session.uid != session_uid or not session.terminal:
            raise ValueError("Semantic review history is invalid.")
        return session

    def list_review_sessions(self) -> tuple:
        """Return the active ReviewSession plus immutable terminal history."""

        active = self.load_review_session()
        sessions = [] if active is None else [active]
        if not self.review_session_history_dir.exists():
            return tuple(sessions)
        if (
            not self.review_session_history_dir.is_dir()
            or self.review_session_history_dir.is_symlink()
        ):
            raise ValueError("Semantic review history is invalid.")
        active_uid = active.uid if active is not None else None
        for path in sorted(self.review_session_history_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Semantic review history is invalid.")
            if path != self._review_session_history_path(path.stem):
                raise ValueError("Semantic review history is invalid.")
            session = self.load_review_session_history(path.stem)
            if session.uid != active_uid:
                sessions.append(session)
        return tuple(sessions)

    def load_review_session_by_uid(self, session_uid: str):
        """Resolve one exact active or retained ReviewSession identity."""

        active = self.load_review_session()
        if active is not None and active.uid == session_uid:
            return active
        return self.load_review_session_history(session_uid)

    @_profile_write_guarded
    def save_review_session(self, session) -> None:
        """Atomically save one validated semantic review session."""
        from memcommit.application.operations.review.model import (
            ReviewError,
            ReviewSession,
        )

        if not isinstance(session, ReviewSession):
            raise TypeError("Expected a ReviewSession.")
        if self.review_session_file.exists() and (
            not self.review_session_file.is_file()
            or self.review_session_file.is_symlink()
        ):
            raise ValueError("Semantic review session storage is invalid.")
        data = session.to_dict()
        # Validate the exact persisted shape before replacing a recoverable
        # review. In-memory dataclasses are mutable by the TUI controller.
        try:
            ReviewSession.from_dict(data)
        except (ReviewError, TypeError) as error:
            raise ValueError("Semantic review session is invalid.") from error
        current = None
        if self.review_session_file.exists():
            try:
                current = self._load_review_session(self.review_session_file)
            except ValueError:
                # --new/--replace-review is also the documented recovery path
                # for a malformed legacy singleton. There is no trustworthy
                # terminal evidence to archive in that case.
                current = None
        if current is not None and current.uid != session.uid and current.terminal:
            history_path = self._review_session_history_path(current.uid)
            if self.review_session_history_dir.exists() and (
                not self.review_session_history_dir.is_dir()
                or self.review_session_history_dir.is_symlink()
            ):
                raise ValueError("Semantic review history is invalid.")
            self.review_session_history_dir.mkdir(parents=True, exist_ok=True)
            archived = current.to_dict()
            if history_path.exists() or history_path.is_symlink():
                retained = self._load_review_session(history_path)
                if retained is None or retained.to_dict() != archived:
                    raise ValueError("Semantic review history is immutable.")
            else:
                _write_json_atomic(history_path, archived)
        source_created = self._retain_review_session_source(session)
        try:
            _write_json_atomic(self.review_session_file, data)
        except Exception:
            if source_created:
                source_path = self._review_session_source_path(session.uid)
                if source_path.exists() and not source_path.is_symlink():
                    source_path.unlink()
            raise
        if current is not None and current.uid != session.uid and not current.terminal:
            displaced_source = self._review_session_source_path(current.uid)
            if displaced_source.exists() and not displaced_source.is_symlink():
                displaced_source.unlink()
