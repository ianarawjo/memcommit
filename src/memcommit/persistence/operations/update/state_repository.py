"""Persist Impact plans and staged Update sessions."""

from __future__ import annotations

import json
from pathlib import Path

from ...store.context_memory.models import ConcurrentContextUpdateError
from ...store.infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)
from ...store.infrastructure.protection import _profile_write_guarded


_NO_UPDATE_SESSION_EXPECTATION = object()


class _UpdateStateStoreMixin:
    """Own Update-specific persisted working state."""

    @staticmethod
    def _load_update_session(path: Path):
        """Load and validate one cached semantic update session."""
        from memcommit.application.operations.update.model import UpdateSession

        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Semantic update session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("Semantic update session is invalid JSON.") from error
        try:
            return UpdateSession.from_dict(data)
        except ValueError as error:
            raise ValueError("Semantic update session is invalid.") from error

    @staticmethod
    def _save_update_session(path: Path, session) -> None:
        """Atomically persist one validated semantic update session."""
        from memcommit.application.operations.update.model import UpdateSession

        if not isinstance(session, UpdateSession):
            raise TypeError("Expected an UpdateSession.")
        try:
            data = session.to_dict()
            restored = UpdateSession.from_dict(data)
        except ValueError as error:
            raise ValueError("Semantic update session is invalid.") from error
        if restored != session:
            raise ValueError("Semantic update session changed during validation.")
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Semantic update session storage is invalid.")
        _write_json_atomic(path, data)

    def load_impact_plan(self):
        """Return the cached impact plan, or None when no plan exists."""
        return self._load_update_session(self.impact_plan_file)

    @_profile_write_guarded
    def save_impact_plan(self, session) -> None:
        """Atomically cache a non-mutating impact plan."""
        self._save_update_session(self.impact_plan_file, session)

    def load_staged_update(self):
        """Return the active staged/applied update record, if one exists."""
        return self._load_update_session(self.staged_update_file)

    @_profile_write_guarded
    def save_staged_update(
        self,
        session,
        *,
        expected_current: object = _NO_UPDATE_SESSION_EXPECTATION,
    ) -> None:
        """Atomically save the active update, optionally using record CAS."""
        with self._update_session_write_lock():
            current = self._load_update_session(self.staged_update_file)
            if expected_current is not _NO_UPDATE_SESSION_EXPECTATION:
                if current != expected_current:
                    raise ConcurrentContextUpdateError(
                        "The active update record changed before it could be saved."
                    )
            from memcommit.application.operations.update.receipt_store import (
                UpdateReceiptStore,
            )

            receipts = UpdateReceiptStore(self)
            if current is not None and current.status in {"applied", "undone"}:
                # Migrate the last singleton receipt before any newer Update
                # can replace it, including receipts created by older builds.
                receipts.save_terminal(current)
            if session.status in {"applied", "undone"}:
                self._save_active_terminal_update(session, receipts=receipts)
            else:
                self._save_update_session(self.staged_update_file, session)

    def _save_active_terminal_update(self, session, *, receipts=None) -> None:
        """Publish the active terminal session and immutable receipt as a pair."""
        from memcommit.application.operations.update.receipt_store import (
            UpdateReceiptStore,
        )

        receipts = receipts or UpdateReceiptStore(self)
        previous = self._load_update_session(self.staged_update_file)
        self._save_update_session(self.staged_update_file, session)
        try:
            receipts.save_terminal(session)
        except Exception:
            try:
                if previous is None:
                    if self.staged_update_file.exists():
                        self.staged_update_file.unlink()
                else:
                    self._save_update_session(self.staged_update_file, previous)
            except Exception as rollback_error:
                raise RuntimeError(
                    "Update receipt save failed and the active session could not "
                    "be restored."
                ) from rollback_error
            raise

    def apply_staged_update(self, session):
        """Compatibility facade for Update's application-owned publication."""

        from memcommit.application.operations.update.publication import (
            apply_staged_update,
        )

        return apply_staged_update(self, session)
