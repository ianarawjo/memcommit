"""Record Context lifecycle events and commit deletion."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import replace
import fcntl
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

from memcommit.core.context_name_validation import validate_context_name
from memcommit.models.context import Context
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)
from memcommit.persistence.store.context_memory.lifecycle_model import (
    ContextLifecycleEvent,
    PREVIOUS_CHECKPOINT_NONE,
    PREVIOUS_CHECKPOINT_RECORDED,
    PREVIOUS_CHECKPOINT_UNREADABLE,
)

from ..infrastructure.atomic_io import (
    _canonical_json_digest,
    _fsync_directory,
    _reject_duplicate_json_keys,
    _write_json_atomic,
)
from .models import (
    ConcurrentContextUpdateError,
    ContextDeletionCommittedError,
)


class _ContextLifecycleMixin:
    def _context_lifecycle_events_dir(self) -> Path:
        """Return the active Profile's ledger path without creating it."""
        ledger_dir = self.store_dir / "ledger"
        events_dir = ledger_dir / "context-events"
        for path, label in (
            (ledger_dir, "Context lifecycle ledger"),
            (events_dir, "Context lifecycle event storage"),
        ):
            if path.is_symlink():
                raise ValueError(f"{label} cannot be a symbolic link.")
            if path.exists() and not path.is_dir():
                raise ValueError(f"{label} must be a directory.")
        return events_dir

    def _ensure_context_lifecycle_events_dir(self) -> Path:
        events_dir = self._context_lifecycle_events_dir()
        ledger_dir = events_dir.parent
        ledger_created = not ledger_dir.exists()
        ledger_dir.mkdir(exist_ok=True, mode=0o700)
        if ledger_created:
            _fsync_directory(self.store_dir)
        events_created = not events_dir.exists()
        events_dir.mkdir(exist_ok=True, mode=0o700)
        if events_created:
            _fsync_directory(ledger_dir)
        return events_dir

    @contextmanager
    def _context_lifecycle_ledger_lock(
        self,
        *,
        exclusive: bool,
    ) -> Iterator[None]:
        """Hide provisional event publication from concurrent ledger readers."""
        lock_path = self.store_dir / "context-lifecycle-ledger.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link lifecycle lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
                )
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

    def _write_context_lifecycle_event(
        self,
        event: ContextLifecycleEvent,
    ) -> Path:
        """Publish one immutable Profile-ledger event before destructive work."""
        event.validated()
        validate_context_name(event.last_context_name)
        events_dir = self._ensure_context_lifecycle_events_dir()
        path = events_dir / f"{event.event_uid}.json"
        if path.exists() or path.is_symlink():
            raise FileExistsError("Context lifecycle event already exists.")
        try:
            _write_json_atomic(path, event.to_dict())
            _fsync_directory(events_dir)
        except Exception:
            if path.exists() and not path.is_symlink():
                path.unlink()
                _fsync_directory(events_dir)
            raise
        return path

    @staticmethod
    def _remove_context_lifecycle_event(path: Path) -> None:
        """Roll back an event when deletion fails before its commit boundary."""
        if path.is_symlink() or not path.is_file():
            raise ValueError("Context lifecycle event rollback path is unsafe.")
        path.unlink()
        _fsync_directory(path.parent)

    def list_context_lifecycle_events(
        self,
        *,
        context_name: str | None = None,
        context_uid: str | None = None,
        recursive: bool = False,
    ) -> list[ContextLifecycleEvent]:
        """Read Profile-ledger events, optionally filtering one namespace."""
        if context_name is not None:
            validate_context_name(context_name)
        if context_uid is not None and (
            not isinstance(context_uid, str) or not context_uid
        ):
            raise ValueError("Context lifecycle Context uid must be non-empty.")
        events_dir = self._context_lifecycle_events_dir()
        if not events_dir.exists():
            # An absent ledger has no publication to coordinate with. Returning
            # here also keeps read-only inspection from creating a lock file.
            return []
        with self._context_lifecycle_ledger_lock(exclusive=False):
            events_dir = self._context_lifecycle_events_dir()
            if not events_dir.exists():
                return []
            events: list[ContextLifecycleEvent] = []
            for path in events_dir.iterdir():
                if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                    raise ValueError("Context lifecycle event storage is invalid.")
                try:
                    with open(path, encoding="utf-8") as file:
                        data = json.load(
                            file,
                            object_pairs_hook=_reject_duplicate_json_keys,
                        )
                    event = ContextLifecycleEvent.from_dict(data)
                except (
                    OSError,
                    UnicodeError,
                    json.JSONDecodeError,
                    ValueError,
                ) as error:
                    raise ValueError(
                        f"Context lifecycle event '{path.name}' is invalid."
                    ) from error
                if path.name != f"{event.event_uid}.json":
                    raise ValueError(
                        "Context lifecycle event filename does not match its uid."
                    )
                validate_context_name(event.last_context_name)
                if context_uid is not None and event.context_uid != context_uid:
                    continue
                if context_name is not None:
                    in_scope = event.last_context_name == context_name
                    if recursive:
                        in_scope = in_scope or event.last_context_name.startswith(
                            context_name + "/"
                        )
                    if not in_scope:
                        continue
                events.append(event)
            return sorted(
                events,
                key=lambda event: datetime.fromisoformat(event.timestamp),
                reverse=True,
            )

    def _context_deletion_event_locked(
        self,
        name: str,
        *,
        current: Context | None = None,
    ) -> ContextLifecycleEvent:
        """Freeze deletion metadata while the exact Context lock is held."""
        context = current if current is not None else self.load_direct(name)
        if context.name != name:
            raise ValueError("Context deletion metadata names the wrong Context.")
        try:
            checkpoints = self.list_checkpoints(name)
        except (KeyError, OSError, TypeError, ValueError):
            # Deletion removes the complete history directory regardless. A
            # malformed non-checkpoint artifact must not retarget or prevent
            # an exact-identity deletion; it only means the optional lifecycle
            # ledger cannot name a trustworthy previous checkpoint.
            checkpoints = []
            previous_status = PREVIOUS_CHECKPOINT_UNREADABLE
        else:
            previous_status = (
                PREVIOUS_CHECKPOINT_RECORDED
                if checkpoints
                else PREVIOUS_CHECKPOINT_NONE
            )
        if checkpoints:
            previous = checkpoints[0]
            previous_uid = previous.get("uid")
            if not isinstance(previous_uid, str) or not previous_uid:
                raise ValueError(
                    "Latest Context checkpoint has no valid uid for deletion."
                )
            previous_digest = _canonical_json_digest(previous)
        else:
            previous_uid = None
            previous_digest = None
        from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
            flatten_checkpoint_entries,
        )

        try:
            entries, _warnings = flatten_checkpoint_entries(checkpoints)
        except (KeyError, RuntimeError, TypeError, ValueError):
            entries = checkpoints
        deleted_checkpoint_uids = tuple(
            dict.fromkeys(
                entry["uid"]
                for entry in entries
                if isinstance(entry.get("uid"), str) and entry["uid"]
            )
        )
        return ContextLifecycleEvent.deleted(
            context_uid=context.uid,
            last_context_name=context.name,
            previous_checkpoint_status=previous_status,
            previous_checkpoint_uid=previous_uid,
            previous_checkpoint_digest=previous_digest,
            deleted_checkpoint_uids=deleted_checkpoint_uids,
        )

    def delete(self, name: str) -> ContextLifecycleEvent:
        """Delete one Context and retain metadata in its Profile ledger."""
        # Creators hold the exclusive graph span, so independent leaf deletions may share it.
        with self._context_graph_lock(exclusive=False):
            from ..context_hierarchy import validate_context_hierarchy

            validate_context_hierarchy(set(self.list_context_names()) - {name})
            with self._context_write_lock(name):
                event = self._context_deletion_event_locked(name)
                recorded = self._delete_locked(name, lifecycle_event=event)
                assert recorded is event
                return event

    def delete_context_if(
        self,
        name: str,
        *,
        expected_context_uid: str,
    ) -> ContextLifecycleEvent:
        """Delete only the exact Context identity that was previously reviewed."""
        with self._context_graph_lock(exclusive=False):
            from ..context_hierarchy import validate_context_hierarchy

            validate_context_hierarchy(set(self.list_context_names()) - {name})
            with self._context_write_lock(name):
                try:
                    current = self.load_direct(name)
                except FileNotFoundError as error:
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' no longer exists."
                    ) from error
                if current.uid != expected_context_uid:
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' changed after deletion was reviewed."
                    )
                event = self._context_deletion_event_locked(
                    name,
                    current=current,
                )
                recorded = self._delete_locked(name, lifecycle_event=event)
                assert recorded is event
                return event

    def delete_context_and_descendants(
        self,
        name: str,
        *,
        expected_contexts: tuple[tuple[str, str], ...],
        expected_current: str | None = None,
    ) -> tuple[ContextLifecycleEvent, ...]:
        """Delete one reviewed subtree, retaining metadata but no recovery copy."""
        validate_context_name(name)
        with self._context_graph_lock(exclusive=True):
            names = list_context_and_descendant_names(
                (name,), self.list_context_names()
            )
            with self._context_write_locks(names), self._state_write_lock():
                contexts = tuple(self.load_direct(target) for target in names)
                identities = tuple((context.name, context.uid) for context in contexts)
                if identities != expected_contexts:
                    raise ConcurrentContextUpdateError(
                        "The Context subtree changed after confirmation was prepared; "
                        "nothing was deleted."
                    )
                original_state = self._read_state()
                if (
                    expected_current is not None
                    and original_state.get("current") != expected_current
                ):
                    raise ConcurrentContextUpdateError(
                        "The current Context changed; nothing was deleted."
                    )
                operation_id = str(uuid.uuid4())
                events = tuple(
                    replace(
                        self._context_deletion_event_locked(
                            context.name, current=context
                        ),
                        operation_id=operation_id,
                        descendants_preserved=False,
                    ).validated()
                    for context in contexts
                )
                cleanup_actions = tuple(
                    (f"{context.name}: {label}", action)
                    for context in contexts
                    for label, action in self._context_deletion_cleanup_actions(context)
                )
                source = self._context_dir(name)
                staged = self.store_dir / f".delete-context-{operation_id}"
                following_state = dict(original_state)
                if following_state.get("current") in names:
                    following_state["current"] = None
                published_events: list[Path] = []
                moved = False
                state_write_attempted = False
                with self._context_lifecycle_ledger_lock(exclusive=True):
                    try:
                        for event in events:
                            published_events.append(
                                self._write_context_lifecycle_event(event)
                            )
                        # Move the complete namespace once; a child must not be
                        # permanently removed before a later sibling can fail.
                        source.rename(staged)
                        moved = True
                        if following_state != original_state:
                            state_write_attempted = True
                            self._write_state(following_state)
                        _fsync_directory(source.parent)
                        _fsync_directory(self.store_dir)
                    except Exception as error:
                        rollback_errors: list[Exception] = []
                        if moved:
                            try:
                                staged.rename(source)
                            except Exception as rollback_error:
                                rollback_errors.append(rollback_error)
                        if state_write_attempted:
                            try:
                                _write_json_atomic(self.state_file, original_state)
                            except Exception as rollback_error:
                                rollback_errors.append(rollback_error)
                        for path in reversed(published_events):
                            try:
                                self._remove_context_lifecycle_event(path)
                            except Exception as rollback_error:
                                rollback_errors.append(rollback_error)
                        if rollback_errors:
                            raise RuntimeError(
                                "Context subtree deletion failed and rollback was incomplete."
                            ) from rollback_errors[0]
                        raise error

                cleanup_failures: list[tuple[str, Exception]] = []
                for label, action in (
                    (
                        "Context subtree and checkpoint histories",
                        lambda: shutil.rmtree(staged),
                    ),
                    *cleanup_actions,
                    (
                        "Store directory durability",
                        lambda: _fsync_directory(self.store_dir),
                    ),
                ):
                    try:
                        action()
                    except Exception as error:
                        cleanup_failures.append((label, error))
                self._prune_empty_namespace_dirs(source.parent)
                if cleanup_failures:
                    raise ContextDeletionCommittedError(
                        events[0], tuple(cleanup_failures)
                    ) from cleanup_failures[0][1]
                return events

    def _context_deletion_cleanup_actions(
        self,
        context: Context,
    ) -> tuple[tuple[str, Callable[[], None]], ...]:
        """Preflight Context-owned sidecars before irreversible deletion."""
        name = context.name
        context_uid = context.uid
        # Validate the derived-artifact path before deleting the primary
        # Context so a malformed analysis store cannot turn cleanup into a
        # surprising partial operation.
        try:
            canonical_context_uid = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError):
            canonical_context_uid = None
        from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import (
            comparison_paths_for_context,
            delete_comparison_paths,
        )
        from memcommit.application.operations.rationale.cache import (
            delete_rationale_inference_paths,
            rationale_inference_paths_for_context,
        )

        # Compare artifacts snapshot both sources and derived explanations.
        # Their privacy lifetime therefore ends when either bound source is
        # deleted, regardless of which side was the display reference.
        comparison_paths = (
            comparison_paths_for_context(context_uid)
            if canonical_context_uid == context_uid
            else ()
        )
        rationale_inference_paths = (
            rationale_inference_paths_for_context(context_uid)
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
        atomize_session_history_dir = (
            self.atomize_session_history_dir / context_uid
            if canonical_context_uid == context_uid
            else None
        )
        for artifact, label in (
            (analysis_path, "Atomize analysis"),
            (workbench_path, "Atomize workbench"),
        ):
            if (
                artifact is not None
                and (artifact.exists() or artifact.is_symlink())
                and (not artifact.is_file() or artifact.is_symlink())
            ):
                raise ValueError(f"{label} storage is invalid.")
        review_session = self.load_review_session()
        retained_reviews = self.list_review_sessions()
        delete_review_session = (
            review_session is not None
            and review_session.context_uid == context_uid
            and review_session.context_name == name
        )
        review_history_paths = tuple(
            self._review_session_history_path(session.uid)
            for session in retained_reviews
            if session.uid != getattr(review_session, "uid", None)
            and session.context_uid == context_uid
            and session.context_name == name
        )
        review_source_paths = tuple(
            self._review_session_source_path(session.uid)
            for session in retained_reviews
            if session.context_uid == context_uid and session.context_name == name
        )
        if atomize_session_history_dir is not None and (
            atomize_session_history_dir.exists()
            or atomize_session_history_dir.is_symlink()
        ):
            # Strict loading rejects malformed entries before the primary
            # Context deletion can commit.
            self.list_atomize_session_history()
        actions: list[tuple[str, Callable[[], None]]] = []
        if analysis_path is not None and analysis_path.exists():
            actions.append(("Atomize analysis", analysis_path.unlink))
        if workbench_path is not None and workbench_path.exists():
            # Workbench responses may contain free-form user context. They are
            # scoped to the deleted Context and must not survive it.
            actions.append(("Atomize workbench", workbench_path.unlink))
        actions.append(
            (
                "Compare analyses",
                lambda: delete_comparison_paths(comparison_paths),
            )
        )
        # A contextual explanation is derived from the deleted direct frame,
        # so its cache shares that Context's privacy lifetime.
        actions.append(
            (
                "rationale inference cache",
                lambda: delete_rationale_inference_paths(rationale_inference_paths),
            )
        )
        if (
            atomize_session_history_dir is not None
            and atomize_session_history_dir.exists()
        ):

            def remove_atomize_session_history() -> None:
                shutil.rmtree(atomize_session_history_dir)
                _fsync_directory(atomize_session_history_dir.parent)
                try:
                    self.atomize_session_history_dir.rmdir()
                except OSError:
                    pass

            actions.append(("Atomize session history", remove_atomize_session_history))
        if delete_review_session and self.review_session_file.exists():
            # Review answers may contain user-supplied local context. Once
            # their exact Context is deleted, retaining that global artifact
            # would be both misleading state and an avoidable privacy leak.
            actions.append(("review session", self.review_session_file.unlink))
        for retained_review_path in review_history_paths:
            if retained_review_path.exists():
                actions.append(("review session history", retained_review_path.unlink))
        for review_source_path in review_source_paths:
            if review_source_path.exists():
                actions.append(("review source snapshot", review_source_path.unlink))

        return tuple(actions)

    def _delete_locked(
        self,
        name: str,
        *,
        lifecycle_event: ContextLifecycleEvent | None = None,
        clear_current: bool = True,
    ) -> ContextLifecycleEvent | None:
        """Delete one Context; internal creation rollback passes no event."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        current_context = self.load_direct(name)
        context_uid = current_context.uid
        if lifecycle_event is not None and (
            lifecycle_event.context_uid != context_uid
            or lifecycle_event.last_context_name != name
        ):
            raise ConcurrentContextUpdateError(
                "Context changed before its deletion event could be committed."
            )
        cleanup_actions = self._context_deletion_cleanup_actions(current_context)
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
            _fsync_directory(ctx_dir)
        except OSError:
            if checkpoints_staged:
                staged_checkpoints.rename(checkpoints_dir)
            staged_context.rename(context_file)
            _fsync_directory(ctx_dir)
            raise

        ledger_guard = ExitStack()
        try:
            if lifecycle_event is not None:
                ledger_guard.enter_context(
                    self._context_lifecycle_ledger_lock(exclusive=True)
                )
        except Exception:
            if checkpoints_staged:
                staged_checkpoints.rename(checkpoints_dir)
            staged_context.rename(context_file)
            _fsync_directory(ctx_dir)
            raise

        lifecycle_event_path: Path | None = None
        # A final event is provisional until the primary unlink succeeds.
        # Readers share this lock, so they can never observe an event that a
        # normal pre-commit rollback subsequently removes.
        with ledger_guard:
            try:
                if lifecycle_event is not None:
                    lifecycle_event_path = self._write_context_lifecycle_event(
                        lifecycle_event
                    )
            except Exception:
                if checkpoints_staged:
                    staged_checkpoints.rename(checkpoints_dir)
                staged_context.rename(context_file)
                _fsync_directory(ctx_dir)
                raise

            try:
                staged_context.unlink()
            except OSError as error:
                rollback_error: Exception | None = None
                if lifecycle_event_path is not None:
                    try:
                        self._remove_context_lifecycle_event(lifecycle_event_path)
                    except Exception as candidate:
                        rollback_error = candidate
                try:
                    if checkpoints_staged:
                        staged_checkpoints.rename(checkpoints_dir)
                    staged_context.rename(context_file)
                    _fsync_directory(ctx_dir)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
                if rollback_error is not None:
                    raise RuntimeError(
                        "Context deletion failed before commit and its staged "
                        "Context or lifecycle event could not be restored."
                    ) from rollback_error
                raise error

        cleanup_failures: list[tuple[str, Exception]] = []

        def attempt_cleanup(label: str, action: Callable[[], None]) -> None:
            try:
                action()
            except Exception as error:
                # Primary deletion is already committed. Continue independent
                # privacy cleanup so one sidecar failure cannot retain all
                # remaining Context-owned content.
                cleanup_failures.append((label, error))

        attempt_cleanup(
            "Context directory durability",
            lambda: _fsync_directory(ctx_dir),
        )
        if checkpoints_staged:

            def remove_checkpoint_history() -> None:
                shutil.rmtree(staged_checkpoints)
                _fsync_directory(ctx_dir)

            attempt_cleanup("checkpoint history", remove_checkpoint_history)
        for label, action in cleanup_actions:
            attempt_cleanup(label, action)

        def clear_current_pointer() -> None:
            with self._state_write_lock():
                state = self._read_state()
                if state.get("current") == name:
                    state["current"] = None
                    self._write_state(state)

        if clear_current:
            attempt_cleanup("current pointer", clear_current_pointer)
        self._prune_empty_namespace_dirs(ctx_dir)
        if cleanup_failures:
            if lifecycle_event is not None:
                raise ContextDeletionCommittedError(
                    lifecycle_event,
                    tuple(cleanup_failures),
                ) from cleanup_failures[0][1]
            raise cleanup_failures[0][1]
        return lifecycle_event

    def _prune_empty_namespace_dirs(self, start: Path) -> None:
        """Remove empty namespace directories without removing self.contexts_dir."""
        candidate = start
        while candidate != self.contexts_dir:
            try:
                candidate.rmdir()
            except OSError:
                break
            candidate = candidate.parent
