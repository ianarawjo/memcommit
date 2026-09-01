"""Persist Meld sessions, choices, branches, and history."""

from __future__ import annotations
import json
import uuid
from pathlib import Path
from memcommit.core.context import AutoCheckpoint, Context


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


class _MeldStateStoreMixin:
    """Own Meld-specific persisted working state."""

    def _meld_choice_branches_path(self, session_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(session_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid Meld choice branch session uid.") from error
        if canonical != session_uid:
            raise ValueError("Invalid Meld choice branch session uid.")
        directory = self.meld_choice_branches_dir
        if directory.is_symlink():
            raise ValueError("Meld choice branch storage cannot be a symbolic link.")
        if directory.exists() and not directory.is_dir():
            raise ValueError("Meld choice branch storage is invalid.")
        return directory / f"{canonical}.json"

    def load_meld_choice_branches(self, session):
        """Restore sparse local choices for the exact current assessment."""
        from memcommit.application.operations.meld.model import MeldSession
        from memcommit.application.operations.meld.proposal_choices import (
            MeldChoiceBranchError,
            MeldChoiceBranchSet,
        )

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        path = self._meld_choice_branches_path(session.uid)
        if not path.exists():
            return MeldChoiceBranchSet.empty(session)
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld choice branch storage is invalid.")
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file, object_pairs_hook=_reject_duplicate_json_keys)
            branches = MeldChoiceBranchSet.from_dict(data)
        except (json.JSONDecodeError, MeldChoiceBranchError, ValueError) as error:
            raise ValueError("Saved Meld choice branches are invalid.") from error
        if branches.session_uid != session.uid:
            raise ValueError(
                "Saved Meld choice branches do not match their storage key."
            )
        if branches.target_context_uid != session.target.context_uid:
            raise ValueError("Saved Meld choice branches target a different Context.")
        # A completed reconciliation changes the assessment. Its selections
        # are already retained in the durable user turn, so the old draft set
        # must not leak into a later revision.
        if not branches.matches(session):
            return MeldChoiceBranchSet.empty(session)
        try:
            return branches.validated_for(session)
        except MeldChoiceBranchError as error:
            raise ValueError("Saved Meld choice branches are invalid.") from error

    def save_meld_choice_branches(self, session, branches) -> None:
        """Persist only staged choices; no provider outcome is written here."""
        from memcommit.application.operations.meld.model import (
            MeldSession,
            meld_canonical_digest,
        )
        from memcommit.application.operations.meld.proposal_choices import (
            MeldChoiceBranchError,
            MeldChoiceBranchSet,
        )

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        if not isinstance(branches, MeldChoiceBranchSet):
            raise TypeError("Expected a MeldChoiceBranchSet.")
        try:
            restored = MeldChoiceBranchSet.from_dict(branches.to_dict()).validated_for(
                session
            )
        except MeldChoiceBranchError as error:
            raise ValueError("Meld choice branches are invalid.") from error
        path = self._meld_choice_branches_path(session.uid)
        with self._context_write_lock(session.target.context_name):
            with self.profile_write_guard():
                saved_session = self.load_meld_session(session.target.context_uid)
                if saved_session is None or saved_session.uid != session.uid:
                    raise ConcurrentContextUpdateError(
                        "The Meld session changed before its choices could be saved."
                    )
                if meld_canonical_digest(saved_session.to_dict()) != (
                    meld_canonical_digest(session.to_dict())
                ):
                    raise ConcurrentContextUpdateError(
                        "The Meld assessment changed before its choices could be saved."
                    )
                directory = self.meld_choice_branches_dir
                if directory.exists() and (
                    not directory.is_dir() or directory.is_symlink()
                ):
                    raise ValueError("Meld choice branch storage is invalid.")
                directory.mkdir(parents=True, exist_ok=True)
                if path.exists() and (not path.is_file() or path.is_symlink()):
                    raise ValueError("Meld choice branch storage is invalid.")
                _write_json_atomic(path, restored.to_dict())

    def _meld_resolution_branch_path(self, key: str) -> Path:
        if (
            not isinstance(key, str)
            or len(key) != 64
            or any(character not in "0123456789abcdef" for character in key)
        ):
            raise ValueError("Invalid Meld resolution branch key.")
        directory = self.meld_resolution_branches_dir
        if directory.is_symlink():
            raise ValueError(
                "Meld resolution branch storage cannot be a symbolic link."
            )
        if directory.exists() and not directory.is_dir():
            raise ValueError("Meld resolution branch storage is invalid.")
        return directory / f"{key}.json"

    def load_meld_resolution_branch(self, key: str):
        """Return one exact validated follow-up branch, if it is saved."""
        from memcommit.application.operations.meld.proposal_cache import (
            MeldResolutionBranch,
            MeldResolutionCacheError,
        )

        path = self._meld_resolution_branch_path(key)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld resolution branch storage is invalid.")
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            branch = MeldResolutionBranch.from_dict(data)
        except (
            json.JSONDecodeError,
            MeldResolutionCacheError,
            ValueError,
        ) as error:
            raise ValueError("Saved Meld resolution branch is invalid.") from error
        if branch.key != key:
            raise ValueError(
                "Saved Meld resolution branch does not match its storage key."
            )
        return branch

    def save_meld_resolution_branch(self, branch) -> None:
        """Publish one immutable exact branch without replacing a peer result."""
        from memcommit.application.operations.meld.proposal_cache import (
            MeldResolutionBranch,
            MeldResolutionCacheError,
        )

        if not isinstance(branch, MeldResolutionBranch):
            raise TypeError("Expected a MeldResolutionBranch.")
        try:
            restored = MeldResolutionBranch.from_dict(branch.to_dict())
        except MeldResolutionCacheError as error:
            raise ValueError("Meld resolution branch is invalid.") from error
        path = self._meld_resolution_branch_path(restored.key)
        with self._meld_resolution_branch_write_lock():
            with self.profile_write_guard():
                directory = self.meld_resolution_branches_dir
                if directory.exists() and (
                    not directory.is_dir() or directory.is_symlink()
                ):
                    raise ValueError("Meld resolution branch storage is invalid.")
                directory.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    existing = self.load_meld_resolution_branch(restored.key)
                    assert existing is not None
                    if existing.to_dict() != restored.to_dict():
                        # One exact semantic request has one durable cached
                        # outcome. A concurrent stochastic result must not
                        # silently replace the branch another session reused.
                        raise ValueError(
                            "A different Meld resolution branch already uses "
                            "this exact request key."
                        )
                    return
                _write_json_atomic(path, restored.to_dict())

    def _meld_session_path(self, target_context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(target_context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid meld target Context uid.") from error
        if canonical != target_context_uid:
            raise ValueError("Invalid meld target Context uid.")
        if self.meld_sessions_dir.is_symlink():
            raise ValueError("Meld session storage cannot be a symbolic link.")
        if self.meld_sessions_dir.exists() and not self.meld_sessions_dir.is_dir():
            raise ValueError("Meld session storage is invalid.")
        return self.meld_sessions_dir / f"{canonical}.json"

    def _meld_session_history_path(
        self,
        target_context_uid: str,
        session_uid: str,
    ) -> Path:
        try:
            canonical_target = str(uuid.UUID(target_context_uid))
            canonical_session = str(uuid.UUID(session_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid Meld session history identity.") from error
        if canonical_target != target_context_uid or canonical_session != session_uid:
            raise ValueError("Invalid Meld session history identity.")
        return (
            self.meld_session_history_dir
            / canonical_target
            / f"{canonical_session}.json"
        )

    def _archive_meld_session_locked(self, session) -> None:
        """Retain terminal Meld evidence before replacing the latest slot."""

        path = self._meld_session_history_path(
            session.target.context_uid,
            session.uid,
        )
        if self.meld_session_history_dir.exists() and (
            not self.meld_session_history_dir.is_dir()
            or self.meld_session_history_dir.is_symlink()
        ):
            raise ValueError("Meld session history is invalid.")
        if path.parent.exists() and (
            not path.parent.is_dir() or path.parent.is_symlink()
        ):
            raise ValueError("Meld session history is invalid.")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = session.to_dict()
        if path.exists() or path.is_symlink():
            if not path.is_file() or path.is_symlink():
                raise ValueError("Meld session history is invalid.")
            with open(path, encoding="utf-8") as handle:
                retained = json.load(
                    handle,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if retained != data:
                raise ValueError("Meld session history is immutable.")
            return
        _write_json_atomic(path, data)

    def load_meld_session_history(
        self,
        target_context_uid: str,
        session_uid: str,
    ):
        """Load one immutable displaced terminal Meld session."""

        from memcommit.application.operations.meld.model import MeldError, MeldSession

        path = self._meld_session_history_path(target_context_uid, session_uid)
        if not path.exists():
            raise FileNotFoundError(f"Meld session '{session_uid}' is unavailable.")
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld session history is invalid.")
        try:
            with open(path, encoding="utf-8") as handle:
                value = json.load(
                    handle,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = MeldSession.from_dict(value)
        except (json.JSONDecodeError, MeldError, ValueError) as error:
            raise ValueError("Meld session history is invalid.") from error
        if (
            session.uid != session_uid
            or session.target.context_uid != target_context_uid
            or session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}
        ):
            raise ValueError("Meld session history identity is invalid.")
        return session

    def list_meld_session_history(self) -> tuple:
        """Return terminal Meld histories with their exact record paths."""

        root = self.meld_session_history_dir
        if not root.exists():
            return ()
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Meld session history is invalid.")
        records = []
        for target_dir in sorted(root.iterdir(), key=lambda item: item.name):
            if not target_dir.is_dir() or target_dir.is_symlink():
                raise ValueError("Meld session history is invalid.")
            for path in sorted(target_dir.glob("*.json")):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Meld session history is invalid.")
                if path != self._meld_session_history_path(
                    target_dir.name,
                    path.stem,
                ):
                    raise ValueError("Meld session history is invalid.")
                records.append(
                    (
                        self.load_meld_session_history(
                            target_dir.name,
                            path.stem,
                        ),
                        path,
                    )
                )
        return tuple(records)

    def load_meld_session(self, target_context_uid: str):
        """Return the saved meld for one target Context, if present."""
        from memcommit.application.operations.meld.model import MeldError, MeldSession

        path = self._meld_session_path(target_context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = MeldSession.from_dict(data)
        except (
            json.JSONDecodeError,
            MeldError,
            ValueError,
        ) as error:
            raise ValueError("Saved meld session is invalid.") from error
        if session.target.context_uid != target_context_uid:
            raise ValueError(
                "Saved meld session does not match its target storage key."
            )
        return session

    def save_meld_session(
        self,
        session,
        *,
        expected_session_digest: str | None = None,
    ) -> None:
        """Persist one meld session with target-scoped optimistic concurrency."""
        from memcommit.application.operations.meld.model import (
            MeldError,
            MeldSession,
            meld_canonical_digest,
        )

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        path = self._meld_session_path(session.target.context_uid)
        data = session.to_dict()
        try:
            restored = MeldSession.from_dict(data)
        except MeldError as error:
            raise ValueError("Meld session is invalid.") from error
        if restored.uid != session.uid:
            raise ValueError("Meld session identity changed during save.")

        # The Context lock coordinates the target artifact with its Context
        # transaction.  The session digest separately prevents two semantic
        # replies from silently replacing one another.
        with self._context_write_lock(session.target.context_name):
            with self.profile_write_guard():
                if self.meld_sessions_dir.exists() and (
                    not self.meld_sessions_dir.is_dir()
                    or self.meld_sessions_dir.is_symlink()
                ):
                    raise ValueError("Meld session storage is invalid.")
                self.meld_sessions_dir.mkdir(parents=True, exist_ok=True)
                if path.exists() and (not path.is_file() or path.is_symlink()):
                    raise ValueError("Meld session storage is invalid.")
                if path.exists():
                    with open(path, encoding="utf-8") as file:
                        current = json.load(
                            file,
                            object_pairs_hook=_reject_duplicate_json_keys,
                        )
                    current_digest = meld_canonical_digest(current)
                    if expected_session_digest is None:
                        raise ConcurrentContextUpdateError(
                            "A meld session already exists for this target."
                        )
                    if current_digest != expected_session_digest:
                        raise ConcurrentContextUpdateError(
                            "The meld session changed before it could be saved."
                        )
                    current_session = MeldSession.from_dict(current)
                    if (
                        current_session.uid != restored.uid
                        and current_session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}
                    ):
                        self._archive_meld_session_locked(current_session)
                elif expected_session_digest is not None:
                    raise ConcurrentContextUpdateError(
                        "The meld session no longer exists."
                    )
                _write_json_atomic(path, data)

    def create_meld_target_with_session(
        self,
        ctx: Context,
        session,
        auto_checkpoint: AutoCheckpoint,
    ) -> None:
        """Atomically publish a new empty symmetric target and its session.

        ``meld --to`` must not leave a selectable empty Context when session
        publication fails. Both records therefore share the command and target
        locks, and the exact new Context is rolled back before either lock is
        released if the session cannot be written.
        """
        from memcommit.application.operations.meld.model import MeldError, MeldSession

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        if session.mode != "SYMMETRIC":
            raise ValueError("A new Meld result requires a symmetric session.")
        if (
            session.target.context_uid != ctx.uid
            or session.target.context_name != ctx.name
            or context_record_digest(ctx) != session.target.context_digest
        ):
            raise ValueError("Meld session does not bind the new target exactly.")
        if tuple(ctx.iter_items()):
            raise ValueError("A new symmetric Meld target must be empty.")

        path = self._meld_session_path(ctx.uid)
        data = session.to_dict()
        try:
            restored = MeldSession.from_dict(data)
        except MeldError as error:
            raise ValueError("Meld session is invalid.") from error
        if restored.uid != session.uid:
            raise ValueError("Meld session identity changed during save.")

        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_lock(ctx.name):
                    with self.profile_write_guard():
                        if self.meld_sessions_dir.exists() and (
                            not self.meld_sessions_dir.is_dir()
                            or self.meld_sessions_dir.is_symlink()
                        ):
                            raise ValueError("Meld session storage is invalid.")
                        if path.exists() or path.is_symlink():
                            raise ConcurrentContextUpdateError(
                                "A meld session already exists for the new "
                                "target identity."
                            )
                        self._save_locked(
                            ctx,
                            auto_checkpoint,
                            expected_context_digest=None,
                            require_new=True,
                        )
                        try:
                            self.meld_sessions_dir.mkdir(parents=True, exist_ok=True)
                            _write_json_atomic(path, data)
                        except Exception as error:
                            try:
                                # No lifecycle deletion is recorded: the new
                                # result was never a successfully committed
                                # command outcome.
                                self._delete_locked(ctx.name)
                            except Exception as rollback_error:
                                raise RuntimeError(
                                    "Meld result creation failed and its exact "
                                    "new Context could not be rolled back."
                                ) from rollback_error
                            raise error
        ctx._store_digest = context_record_digest(ctx)

    def save_meld_candidate_target_with_session(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpoint,
        *,
        expected_context_digest: str,
        expected_session_digest: str,
        source_bindings,
        finalize_session,
    ):
        """Publish one candidate Target and its applied receipt as one command.

        The Context record, automatic checkpoint, and Target-scoped Meld
        session use separate files. Keep their locks together and roll every
        file back when any later publication raises, so a process exception
        cannot expose a Target whose reviewed session still says unresolved.
        Durable crash journaling remains a separate boundary.
        """
        from memcommit.application.operations.meld.model import (
            MeldSession,
            meld_canonical_digest,
        )

        if not isinstance(ctx, Context) or not isinstance(
            auto_checkpoint,
            AutoCheckpoint,
        ):
            raise TypeError("Candidate Meld publication requires Context evidence.")
        if not isinstance(expected_session_digest, str):
            raise TypeError("Candidate Meld publication requires a session digest.")
        if not callable(finalize_session):
            raise TypeError("Candidate Meld publication requires a session finalizer.")
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _uid, _digest in bindings)
        if len(source_names) != len(set(source_names)) or ctx.name in source_names:
            raise ValueError("Invalid candidate Meld source lock set.")
        path = self._meld_session_path(ctx.uid)

        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks((*source_names, ctx.name)):
                    with self.profile_write_guard():
                        if not path.exists() or not path.is_file() or path.is_symlink():
                            raise ConcurrentContextUpdateError(
                                "The candidate Meld session no longer exists."
                            )
                        with open(path, encoding="utf-8") as handle:
                            prior_data = json.load(
                                handle,
                                object_pairs_hook=_reject_duplicate_json_keys,
                            )
                        prior = MeldSession.from_dict(prior_data)
                        if (
                            prior.target.context_uid != ctx.uid
                            or meld_canonical_digest(prior_data)
                            != expected_session_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                "The candidate Meld session changed before Apply."
                            )
                        self._assert_source_bindings_locked(
                            bindings,
                            result_label="candidate Meld target",
                        )
                        current_target = self.load_direct(ctx.name)
                        original_target = current_target.to_dict()
                        checkpoint = self._save_locked(
                            ctx,
                            auto_checkpoint,
                            expected_context_digest=expected_context_digest,
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Candidate Meld Apply produced no checkpoint."
                            )
                        try:
                            session = finalize_session(checkpoint)
                            if not isinstance(session, MeldSession):
                                raise TypeError(
                                    "Candidate Meld finalizer returned no session."
                                )
                            data = session.to_dict()
                            restored = MeldSession.from_dict(data)
                            if (
                                restored.uid != prior.uid
                                or restored.target.context_uid != ctx.uid
                                or restored.state != "APPLIED"
                            ):
                                raise ValueError(
                                    "Candidate Meld finalizer returned an invalid receipt."
                                )
                            _write_json_atomic(path, data)
                        except Exception as error:
                            rollback_error: Exception | None = None
                            try:
                                _write_json_atomic(
                                    self._context_file(ctx.name),
                                    original_target,
                                )
                            except Exception as candidate:
                                rollback_error = candidate
                            try:
                                self._remove_checkpoint_uid_locked(
                                    ctx.name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                            try:
                                _write_json_atomic(path, prior_data)
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                            if rollback_error is not None:
                                raise RuntimeError(
                                    "Candidate Meld Apply failed and could not be "
                                    "fully rolled back."
                                ) from rollback_error
                            raise error
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    @_profile_write_guarded
    def delete_meld_session(self, target_context_uid: str) -> None:
        """Remove one exact target-bound meld artifact."""
        path = self._meld_session_path(target_context_uid)
        if not path.exists():
            return
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld session storage is invalid.")
        path.unlink()
