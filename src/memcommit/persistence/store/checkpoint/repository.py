"""Record and read persisted Context checkpoints."""

from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Iterable, Optional
from memcommit.core.context import Checkpoint, Context
from ..context_memory.models import ConcurrentContextUpdateError
from ..context_memory.records import (
    context_record_digest,
    validate_context_name,
)
from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_json_atomic,
)


class _CheckpointRepositoryMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def checkpoint(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
    ) -> Checkpoint:
        """Save a persisted Context snapshot under its cooperative write lock."""
        with self._command_write_lock():
            with self._context_write_lock(ctx.name):
                if not self.context_exists(ctx.name):
                    raise FileNotFoundError(
                        f"Context '{ctx.name}' must be saved before checkpointing."
                    )
                current = self.load_direct(ctx.name)
                expected_digest = getattr(ctx, "_store_digest", None)
                current_digest = context_record_digest(current)
                if current.uid != ctx.uid or (
                    expected_digest is not None and current_digest != expected_digest
                ):
                    # A checkpoint is part of the same serial history as saves and
                    # reverts. Never append a stale caller's snapshot after a
                    # concurrent state change.
                    raise ConcurrentContextUpdateError(
                        f"Context '{ctx.name}' changed before it could be checkpointed."
                    )
                if context_record_digest(ctx) != current_digest:
                    raise ValueError(
                        f"Context '{ctx.name}' has unsaved changes; save it "
                        "before checkpointing."
                    )
                return self._checkpoint_locked(
                    ctx,
                    message=message,
                    command=command,
                    args=args,
                    description=description,
                    auto=auto,
                )

    def checkpoint_context_batch(
        self,
        entries: Iterable[tuple[Context, str]],
        *,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        expected_context_catalog: Iterable[str] | None = None,
        checkpoint_uids: Iterable[str] | None = None,
    ) -> tuple[Checkpoint, ...]:
        """Append one exception-atomic checkpoint set to existing Contexts.

        Context bytes are unchanged. Every member is locked and revalidated
        before the first history append, and a failed later append removes the
        provisional checkpoints already written by this call. A durable crash
        journal remains outside this prototype boundary.
        """

        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context checkpoint entry is required.")
        if any(
            not isinstance(context, Context)
            or not isinstance(expected_digest, str)
            or not expected_digest
            for context, expected_digest in records
        ):
            raise TypeError("Invalid Context checkpoint batch entry.")
        names = tuple(context.name for context, _expected_digest in records)
        if len(names) != len(set(names)):
            raise ValueError("Context checkpoint batch contains duplicate names.")
        planned_uids = None if checkpoint_uids is None else tuple(checkpoint_uids)
        if planned_uids is not None:
            try:
                canonical_uids = tuple(str(uuid.UUID(value)) for value in planned_uids)
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError(
                    "Context checkpoint batch uid plan is invalid."
                ) from error
            if (
                len(planned_uids) != len(records)
                or len(planned_uids) != len(set(planned_uids))
                or planned_uids != canonical_uids
            ):
                raise ValueError("Context checkpoint batch uid plan is invalid.")
        for name in names:
            validate_context_name(name)
        expected_catalog = (
            None
            if expected_context_catalog is None
            else tuple(expected_context_catalog)
        )
        if expected_catalog is not None and (
            len(expected_catalog) != len(set(expected_catalog))
            or any(not isinstance(name, str) or not name for name in expected_catalog)
        ):
            raise ValueError("Expected Context checkpoint catalog is invalid.")

        with self._command_write_lock():
            with self._context_graph_lock(exclusive=expected_catalog is not None):
                if (
                    expected_catalog is not None
                    and tuple(self.list_context_names()) != expected_catalog
                ):
                    raise ConcurrentContextUpdateError(
                        "The Context namespace changed after the checkpoint "
                        "scope was selected."
                    )
                with self._context_write_locks(names):
                    self._assert_profile_write_allowed()
                    for context, expected_digest in records:
                        try:
                            current = self.load_direct(context.name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' no longer exists."
                            ) from error
                        current_digest = context_record_digest(current)
                        if (
                            current.uid != context.uid
                            or current_digest != expected_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' changed before it "
                                "could be checkpointed."
                            )
                        if context_record_digest(context) != current_digest:
                            raise ValueError(
                                f"Context '{context.name}' has unsaved changes; "
                                "save it before checkpointing."
                            )

                    created: list[tuple[str, Checkpoint]] = []
                    try:
                        for index, (context, _expected_digest) in enumerate(records):
                            checkpoint = self._checkpoint_locked(
                                context,
                                message=message,
                                command=command,
                                args=args,
                                description=description,
                                auto=auto,
                                checkpoint_uid=(
                                    None
                                    if planned_uids is None
                                    else planned_uids[index]
                                ),
                            )
                            created.append((context.name, checkpoint))
                    except Exception:
                        rollback_error: Exception | None = None
                        for name, checkpoint in created:
                            try:
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Context checkpoint batch failed and could not "
                                "be fully rolled back."
                            ) from rollback_error
                        raise
        return tuple(checkpoint for _name, checkpoint in created)

    def _checkpoint_locked(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        command_before: dict[str, object] | None = None,
        checkpoint_uid: str | None = None,
    ) -> Checkpoint:
        """Write one checkpoint while the caller holds the Context lock."""
        self._assert_profile_write_allowed()
        if checkpoint_uid is None:
            checkpoint_uid = str(uuid.uuid4())
        else:
            try:
                canonical_uid = str(uuid.UUID(checkpoint_uid))
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError("Checkpoint uid plan is invalid.") from error
            if checkpoint_uid != canonical_uid:
                raise ValueError("Checkpoint uid plan is invalid.")
        cp = Checkpoint(
            uid=checkpoint_uid,
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command=command,
            args=args,
            description=description,
            auto=auto,
        )
        ts = cp.timestamp.strftime("%Y%m%dT%H%M%S")
        slug = (
            message[:24].replace(" ", "-").replace("/", "-")
            if message
            else (command or "checkpoint")
        )
        cp_dir = self._checkpoints_dir(ctx.name)
        cp_dir.mkdir(parents=True, exist_ok=True)
        cp_file = cp_dir / f"{ts}-{slug}-{cp.uid[:8]}.json"
        if cp_file.exists() or cp_file.is_symlink():
            raise ValueError(
                f"Refusing to replace an existing checkpoint for '{ctx.name}'."
            )
        checkpoint_record = {
            "uid": cp.uid,
            "message": cp.message,
            "timestamp": cp.timestamp.isoformat(),
            "snapshot": cp.snapshot,
            "command": cp.command,
            "args": cp.args,
            "description": cp.description,
            "auto": cp.auto,
        }
        if command_before is not None:
            checkpoint_record["command_before"] = command_before
        _write_json_atomic(cp_file, checkpoint_record)
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

    def _remove_checkpoint_uid_locked(self, name: str, checkpoint_uid: str) -> None:
        """Remove one exact provisional checkpoint while its Context is locked."""
        for path in self._checkpoints_dir(name).glob(f"*-{checkpoint_uid[:8]}.json"):
            if path.is_symlink() or not path.is_file():
                continue
            with open(path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if value.get("uid") == checkpoint_uid:
                path.unlink()
                return
        raise RuntimeError("Provisional restoration checkpoint is unavailable.")
