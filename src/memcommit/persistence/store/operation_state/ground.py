"""Persist Ground sessions with optimistic concurrency checks."""

from __future__ import annotations
from contextlib import ExitStack
import hashlib
import json
import uuid
from pathlib import Path
from memcommit.core.context import Memory


from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)


class ConcurrentGroundUpdateError(RuntimeError):
    """A named Ground changed after a caller captured its expected record."""


def ground_session_record_digest(value: object) -> str:
    """Hash one complete validated Ground record canonically."""
    from memcommit.application.operations.ground.model import GroundSession

    record = (
        value.to_dict()
        if isinstance(value, GroundSession)
        else GroundSession.from_dict(value).to_dict()
    )
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class _GroundStateStoreMixin:
    """Focused slice of the temporary Store assembly."""

    def _ground_session_path(self, contract_name: str) -> Path:
        """Resolve one portable contract ID without creating active state."""
        from memcommit.application.operations.ground.model import (
            validate_ground_contract_name,
        )

        canonical = validate_ground_contract_name(contract_name)
        if self.ground_sessions_dir.is_symlink():
            raise ValueError("Grounding session storage cannot be a symbolic link.")
        if self.ground_sessions_dir.exists() and not self.ground_sessions_dir.is_dir():
            raise ValueError("Grounding session storage is invalid.")
        return self.ground_sessions_dir / f"{canonical}.json"

    def load_ground_session(self, contract_name: str):
        """Return one named grounding session, or None when it does not exist."""
        from memcommit.application.operations.ground.model import (
            GroundError,
            GroundSession,
        )

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

    def save_ground_session(
        self,
        session,
        *,
        replace: bool = False,
        expected_uid: str | None = None,
        expected_revision: int | None = None,
        expected_digest: str | None = None,
        verify_bound_frames: bool = False,
    ) -> None:
        """Persist one validated Ground, optionally using save-boundary CAS.

        The three expected-state fields are intentionally all-or-none.  A
        caller that presents them gets a compare-and-swap whose comparison
        and atomic file replacement occur under the same per-Ground process
        lock.  This closes the gap left by a UI-side freshness check followed
        by a separately launched CLI mutation.  Interactive mutations may
        additionally lock and verify every bound Context frame before taking
        the Ground lock; ordinary setup saves keep that stricter check off.
        """
        from memcommit.application.operations.ground.model import (
            GroundError,
            GroundSession,
        )

        if not isinstance(session, GroundSession):
            raise TypeError("Expected a GroundSession.")
        if not isinstance(verify_bound_frames, bool):
            raise ValueError("Ground frame verification flag is invalid.")
        # Fail before Ground lock storage is created when the Profile is
        # already read-only. The later shared guard is still authoritative
        # against a concurrent Profile lock.
        self._assert_profile_write_allowed()
        path = self._ground_session_path(session.contract_name)
        expected_values = (
            expected_uid,
            expected_revision,
            expected_digest,
        )
        if any(value is not None for value in expected_values) and any(
            value is None for value in expected_values
        ):
            raise ValueError(
                "Expected Ground uid, revision, and digest must be supplied together."
            )
        if expected_uid is not None:
            try:
                canonical_expected_uid = str(uuid.UUID(expected_uid))
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError("Expected Ground uid is invalid.") from error
            if canonical_expected_uid != expected_uid:
                raise ValueError("Expected Ground uid is invalid.")
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ValueError("Expected Ground revision is invalid.")
        if expected_digest is not None and (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(character not in "0123456789abcdef" for character in expected_digest)
        ):
            raise ValueError("Expected Ground digest is invalid.")
        data = session.to_dict()
        try:
            restored = GroundSession.from_dict(data)
        except GroundError as error:
            raise ValueError("Grounding session is invalid.") from error
        if restored.contract_name != session.contract_name:
            raise ValueError("Grounding session identity changed during save.")
        with ExitStack() as locks:
            if session.frames:
                # Bound Ground files are part of Context-rename freshness.
                # Enter the graph lock before any Context/Ground locks so a
                # newly created or revised binding cannot escape a concurrent
                # namespace scan. An unbound Ground has no Context locator and
                # retains its deliberate ability to exist without ~/.mem
                # Context state.
                locks.enter_context(self._context_graph_lock(exclusive=False))
            if verify_bound_frames:
                if not session.frames:
                    raise ValueError(
                        "Bound Ground frame verification requires a bound Ground."
                    )
                # Context locks always precede the Ground lock. Future
                # operations that need both must retain this order.
                locks.enter_context(
                    self._context_write_locks(
                        frame.context_name for frame in session.frames
                    )
                )
            locks.enter_context(self._ground_session_write_lock(session.contract_name))
            # Keep the existing graph -> Context -> artifact -> registry lock
            # order. Context lock/unlock also takes Context before registry.
            locks.enter_context(self.profile_write_guard())
            if self.ground_sessions_dir.exists() and (
                not self.ground_sessions_dir.is_dir()
                or self.ground_sessions_dir.is_symlink()
            ):
                raise ValueError("Grounding session storage is invalid.")
            self.ground_sessions_dir.mkdir(parents=True, exist_ok=True)
            if path.exists() and (not path.is_file() or path.is_symlink()):
                raise ValueError("Grounding session storage is invalid.")
            if verify_bound_frames:
                self._verify_ground_frames_locked(session)
            existing = (
                self.load_ground_session(session.contract_name)
                if expected_uid is not None or not replace
                else None
            )
            if expected_uid is not None:
                if existing is None:
                    raise ConcurrentGroundUpdateError(
                        "The named Ground no longer exists."
                    )
                if (
                    existing.uid != expected_uid
                    or existing.revision != expected_revision
                    or ground_session_record_digest(existing) != expected_digest
                ):
                    raise ConcurrentGroundUpdateError(
                        "The named Ground changed before it could be saved."
                    )
            elif existing is not None and not replace and existing.uid != session.uid:
                raise ValueError(
                    "A different grounding session already uses this contract name."
                )
            _write_json_atomic(path, data)

    def _verify_ground_frames_locked(self, session) -> None:
        """Require every bound frame to match while its Context lock is held."""
        from memcommit.application.operations.ground.model import context_frame_digest

        for frame in session.frames:
            try:
                context = self.load_direct(frame.context_name)
            except FileNotFoundError as error:
                raise ConcurrentGroundUpdateError(
                    f"Bound Context '{frame.context_name}' no longer exists."
                ) from error
            direct_items = tuple(context.iter_items())
            if (
                context.uid != frame.context_uid
                or context_frame_digest(context) != frame.context_digest
                or sum(isinstance(item, Memory) for item in direct_items)
                != frame.direct_memory_count
                or len(direct_items) != frame.direct_item_count
            ):
                raise ConcurrentGroundUpdateError(
                    f"Bound Context '{frame.context_name}' changed before "
                    "the Ground could be saved."
                )
