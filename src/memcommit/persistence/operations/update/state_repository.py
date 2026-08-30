"""Persist and apply Impact plans and staged Update sessions."""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from memcommit.core.context import AutoCheckpoint


from ...store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from ...store.context_memory.records import (
    context_record_digest,
)
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
        """Apply one staged Update as one globally ordered command."""
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            return self._apply_staged_update_command_locked(session)

    def _apply_staged_update_command_locked(self, session):
        """Apply one exact staged plan to its local target Context graph.

        Every owner is preflighted before the first write. Cooperative Context
        locks remain held through the last checkpoint and the application
        receipt. If an ordinary write fails, already-written owners and their
        new checkpoints are rolled back before the error escapes.

        A process crash can still interrupt the sequence of per-Context atomic
        replacements. A durable transaction journal is intentionally deferred
        with remote publication; this prototype provides exception atomicity,
        not crash atomicity, across several Context files.
        """
        from memcommit.application.operations.update.model import (
            UpdateApplicationReceipt,
            UpdateCheckpointReceipt,
            UpdateError,
            UpdateSession,
            applied_session_matches,
            collect_update_inputs,
            inline_update_session_source,
            operation_digest,
            session_matches,
        )
        from memcommit.application.operations.update.application import (
            prepare_update_application,
        )
        from memcommit.core.context_targeting.loading import load_context_scope
        from memcommit.application.capabilities.semantic.goal_focus import (
            GoalFocusError,
        )
        from memcommit.application.capabilities.semantic.goal_focus_runtime import (
            revalidate_goal_focus,
        )

        if not isinstance(session, UpdateSession) or session.status != "staged":
            raise ValueError("Expected one staged UpdateSession.")

        inline_source = inline_update_session_source(session)
        lock_names = {context.name for context in session.target_contexts}
        lock_names.add(session.target_name)
        if inline_source is None:
            lock_names.update(context.name for context in session.source_contexts)
            lock_names.add(session.source_name)
        # A source MemoryRef is readable evidence owned outside the embedded
        # source graph. Lock every cited owner too so its supporting text
        # cannot change between freshness validation and the final receipt.
        lock_names.update(
            source.context_name
            for operation in session.operations
            for source in operation.source_refs
            if inline_source is None or source.context_name != inline_source.name
        )
        if session.goal_focus is not None and session.goal_focus.kind != "INLINE":
            assert session.goal_focus.context_name is not None
            lock_names.add(session.goal_focus.context_name)

        with self._update_session_write_lock():
            current = self._load_update_session(self.staged_update_file)
            if current != session:
                raise ConcurrentContextUpdateError(
                    "The active staged update changed before application."
                )

            with self._context_write_locks(lock_names):
                if session.goal_focus is not None:
                    # Goal is a frozen relevance criterion, not Update Source
                    # evidence. It still participates in the Apply freshness
                    # boundary so a changed Goal cannot authorize a plan that
                    # was reviewed against an older outcome.
                    try:
                        revalidate_goal_focus(self, session.goal_focus)
                    except GoalFocusError as error:
                        raise ConcurrentContextUpdateError(
                            "The Update Goal focus changed before application."
                        ) from error
                source = inline_source or load_context_scope(
                    self,
                    session.source_name,
                    include_descendants=session.source_include_descendants,
                )
                target = load_context_scope(
                    self,
                    session.target_name,
                    include_descendants=session.target_include_descendants,
                )
                if not session_matches(session, source, target):
                    raise ConcurrentContextUpdateError(
                        "The update source or local fork changed before application."
                    )

                result = prepare_update_application(session, target)
                base_by_identity = {
                    (context.uid, context.name): context
                    for context in session.target_contexts
                }
                original_records: dict[str, dict[str, object]] = {}
                expected_digests: dict[str, str] = {}
                for owner in result.affected_owners:
                    identity = (
                        owner.owner_context_uid,
                        owner.owner_context_name,
                    )
                    base = base_by_identity.get(identity)
                    if base is None:
                        raise UpdateError(
                            "Update owner is outside the recorded local fork."
                        )
                    direct = self.load_direct(owner.owner_context_name)
                    if (
                        direct.uid != owner.owner_context_uid
                        or context_record_digest(direct) != base.digest
                    ):
                        raise ConcurrentContextUpdateError(
                            f"Local fork Context '{owner.owner_context_name}' "
                            "changed before application."
                        )
                    if (
                        owner.post_image.uid != owner.owner_context_uid
                        or owner.post_image.name != owner.owner_context_name
                    ):
                        raise UpdateError(
                            "Update application changed an owner identity."
                        )
                    original_records[owner.owner_context_name] = direct.to_dict()
                    expected_digests[owner.owner_context_name] = base.digest

                created_checkpoints: list[tuple[str, str]] = []
                written_owner_names: list[str] = []
                try:
                    operation_hash = operation_digest(session.operations)
                    for owner in result.affected_owners:
                        owner_operations = [
                            operation
                            for operation in session.operations
                            if (operation.owner_context_uid == owner.owner_context_uid)
                        ]
                        checkpoint = self._save_locked(
                            owner.post_image,
                            AutoCheckpoint(
                                command="update",
                                args={
                                    "update_session_uid": session.uid,
                                    "operation_digest": operation_hash,
                                    "source_context_uid": session.source_uid,
                                    "source_context_name": session.source_name,
                                    "target_context_uid": session.target_uid,
                                    "target_context_name": session.target_name,
                                    "goal_focus": (
                                        None
                                        if session.goal_focus is None
                                        else session.goal_focus.receipt_record()
                                    ),
                                    "owner_context_uid": (owner.owner_context_uid),
                                    "operation_memory_uids": [
                                        operation.memory_uid
                                        for operation in owner_operations
                                    ],
                                    "command_contexts": [
                                        {
                                            "uid": affected.owner_context_uid,
                                            "name": affected.owner_context_name,
                                        }
                                        for affected in result.affected_owners
                                    ],
                                },
                                description=(
                                    "Applied semantic update "
                                    f"{session.uid[:8]} from "
                                    f"{session.source_name}."
                                ),
                            ),
                            expected_context_digest=expected_digests[
                                owner.owner_context_name
                            ],
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Update application created no checkpoint."
                            )
                        written_owner_names.append(owner.owner_context_name)
                        created_checkpoints.append(
                            (
                                owner.owner_context_name,
                                checkpoint.uid,
                            )
                        )

                    source_after = inline_source or load_context_scope(
                        self,
                        session.source_name,
                        include_descendants=session.source_include_descendants,
                    )
                    target_after = load_context_scope(
                        self,
                        session.target_name,
                        include_descendants=session.target_include_descendants,
                    )
                    inputs_after = collect_update_inputs(
                        source_after,
                        target_after,
                    )
                    checkpoint_uid_by_name = dict(created_checkpoints)
                    receipt = UpdateApplicationReceipt(
                        applied_at=datetime.now().astimezone().isoformat(),
                        operation_digest=operation_hash,
                        target_digest=inputs_after.target_digest,
                        target_contexts=(inputs_after.target_context_fingerprints),
                        checkpoints=tuple(
                            UpdateCheckpointReceipt(
                                context_uid=owner.owner_context_uid,
                                context_name=owner.owner_context_name,
                                checkpoint_uid=checkpoint_uid_by_name[
                                    owner.owner_context_name
                                ],
                            )
                            for owner in result.affected_owners
                        ),
                    )
                    applied = session.with_application(receipt)
                    if not applied_session_matches(
                        applied,
                        source_after,
                        target_after,
                    ):
                        raise RuntimeError(
                            "Applied local fork does not match its receipt."
                        )
                    self._save_active_terminal_update(applied)
                except Exception:
                    rollback_error: Exception | None = None
                    for name in written_owner_names:
                        try:
                            _write_json_atomic(
                                self._context_file(name),
                                original_records[name],
                            )
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
                    for name, checkpoint_uid in created_checkpoints:
                        try:
                            removed = False
                            for path in self._checkpoints_dir(name).glob(
                                f"*-{checkpoint_uid[:8]}.json"
                            ):
                                if path.is_symlink() or not path.is_file():
                                    continue
                                with open(path, encoding="utf-8") as file:
                                    value = json.load(
                                        file,
                                        object_pairs_hook=(_reject_duplicate_json_keys),
                                    )
                                if value.get("uid") == checkpoint_uid:
                                    path.unlink()
                                    removed = True
                                    break
                            if not removed:
                                raise RuntimeError(
                                    "Update checkpoint could not be found "
                                    "during rollback."
                                )
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
                    if rollback_error is not None:
                        raise RuntimeError(
                            "Update application failed and its local fork "
                            "could not be fully rolled back."
                        ) from rollback_error
                    raise

        return applied
