"""Revert one Context or checkpoint unit to a selected snapshot."""

from __future__ import annotations
import copy
import json
import uuid
from datetime import datetime
from memcommit.core.context import Checkpoint, Context
from memcommit.application.retained_history.memory_lineage import (
    checkpoint_memory_lineage_edges,
    remap_restoration_snapshot,
)
from ..context_memory.models import ConcurrentContextUpdateError
from ..context_memory.records import (
    checkpoint_history_digest,
    context_record_digest,
)
from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
    _write_bytes_atomic,
    _write_json_atomic,
)


class _CheckpointRevertMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    @staticmethod
    def _context_for_restoration(
        snapshot: dict[str, object],
        *,
        context_uid: str,
        context_name: str,
        expected_context_digest: str,
    ) -> Context:
        """Build one exact direct restore target under its current owner.

        Revert may select an inherited checkpoint whose serialized owner is a
        branch source, while Undo/Redo carries already-normalized command
        images. Both paths must preserve the live Context identity and attach
        the same compare-and-set digest before publishing through
        ``_save_locked``.
        """

        restored = Context.from_dict(
            {
                **snapshot,
                "uid": context_uid,
                "name": context_name,
            }
        )
        restored._store_digest = expected_context_digest
        return restored

    def revert(
        self,
        ctx_name: str,
        uid_prefix: str,
        keep_history: bool = True,
        *,
        expected_context_uid: str | None = None,
        expected_context_digest: str | None = None,
        expected_history_digest: str | None = None,
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert one Context while holding its cooperative write lock."""
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            with self._context_write_lock(ctx_name):
                return self._revert_locked(
                    ctx_name,
                    uid_prefix,
                    keep_history=keep_history,
                    expected_context_uid=expected_context_uid,
                    expected_context_digest=expected_context_digest,
                    expected_history_digest=expected_history_digest,
                    revert_unit=None,
                )

    def revert_checkpoint_unit(
        self,
        unit,
        keep_history: bool = True,
    ):
        """Atomically restore every physical member of one checkpoint set.

        The globally resolved unit is freshness-bound, but selection happens
        before the write locks are held.  Revalidate every member before the
        first publication, retain exact Context/history bytes for the outer
        exception rollback, and record one shared Revert command identity so
        Undo/Redo cannot split the recovery unit later.
        """

        from memcommit.application.retained_history.checkpoint_catalog import (
            CheckpointUnitRevertMember,
            CheckpointUnitRevertResult,
            ResolvedCheckpointUnit,
        )

        if not isinstance(unit, ResolvedCheckpointUnit) or not unit.is_recursive_set:
            raise TypeError("Expected one resolved recursive checkpoint unit.")
        if not unit.members:
            raise ValueError("Recursive checkpoint unit has no members.")
        names = tuple(member.context_name for member in unit.members)
        if len(names) != len(set(names)):
            raise ValueError("Recursive checkpoint unit repeats a Context owner.")

        receipt_uid = str(uuid.uuid4())
        command_contexts = [
            {"uid": member.context_uid, "name": member.context_name}
            for member in unit.members
        ]
        revert_unit = {
            "version": 1,
            "receipt_uid": receipt_uid,
            "checkpoint_unit_uid": unit.canonical_uid,
            "checkpoint_set_uid": unit.checkpoint_set_uid,
            "root_context_uid": unit.root_context_uid,
            "root_context_name": unit.root_context_name,
            "contexts": command_contexts,
        }

        with self._command_write_lock():
            self._assert_profile_write_allowed()
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks(names):
                    original_context_bytes: dict[str, bytes] = {}
                    original_checkpoint_bytes: dict[str, dict[str, bytes]] = {}
                    for member in unit.members:
                        current = self.load_direct(member.context_name)
                        entries = self.list_checkpoints(member.context_name)
                        if (
                            current.uid != member.context_uid
                            or context_record_digest(current)
                            != member.expected_context_digest
                            or checkpoint_history_digest(entries)
                            != member.expected_history_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                "A recursive checkpoint member changed after "
                                "the recovery unit was selected."
                            )
                        matches = [
                            entry
                            for entry in entries
                            if entry.get("uid") == member.checkpoint_uid
                        ]
                        if len(matches) != 1 or matches[0] != member.checkpoint:
                            raise ConcurrentContextUpdateError(
                                "A recursive checkpoint member changed after "
                                "the recovery unit was selected."
                            )
                        context_path = self._context_file(member.context_name)
                        checkpoint_dir = self._checkpoints_dir(member.context_name)
                        checkpoint_paths = tuple(sorted(checkpoint_dir.glob("*.json")))
                        if any(
                            path.is_symlink() or not path.is_file()
                            for path in checkpoint_paths
                        ):
                            raise ValueError(
                                f"Checkpoint history for '{member.context_name}' "
                                "is unsafe."
                            )
                        original_context_bytes[member.context_name] = (
                            context_path.read_bytes()
                        )
                        original_checkpoint_bytes[member.context_name] = {
                            path.name: path.read_bytes() for path in checkpoint_paths
                        }

                    published: list[CheckpointUnitRevertMember] = []
                    try:
                        for member in unit.members:
                            recovery, target = self._revert_locked(
                                member.context_name,
                                member.checkpoint_uid,
                                keep_history=keep_history,
                                expected_context_uid=member.context_uid,
                                expected_context_digest=(
                                    member.expected_context_digest
                                ),
                                expected_history_digest=(
                                    member.expected_history_digest
                                ),
                                revert_unit=revert_unit,
                            )
                            published.append(
                                CheckpointUnitRevertMember(
                                    context_name=member.context_name,
                                    target=target,
                                    recovery=recovery,
                                )
                            )
                    except Exception as error:
                        rollback_error: Exception | None = None
                        for member in unit.members:
                            name = member.context_name
                            checkpoint_dir = self._checkpoints_dir(name)
                            originals = original_checkpoint_bytes[name]
                            try:
                                for path in checkpoint_dir.glob("*.json"):
                                    if path.is_symlink() or not path.is_file():
                                        raise ValueError(
                                            f"Checkpoint rollback for '{name}' "
                                            "encountered an unsafe path."
                                        )
                                    if path.name not in originals:
                                        path.unlink()
                                for filename, content in originals.items():
                                    _write_bytes_atomic(
                                        checkpoint_dir / filename,
                                        content,
                                    )
                                _write_bytes_atomic(
                                    self._context_file(name),
                                    original_context_bytes[name],
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Recursive Revert failed and its complete "
                                "Context/history unit could not be restored."
                            ) from rollback_error
                        raise error

        return CheckpointUnitRevertResult(
            unit=unit,
            receipt_uid=receipt_uid,
            members=tuple(published),
        )

    def _revert_locked(
        self,
        ctx_name: str,
        uid_prefix: str,
        *,
        keep_history: bool,
        expected_context_uid: str | None,
        expected_context_digest: str | None,
        expected_history_digest: str | None,
        revert_unit: dict[str, object] | None,
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert context to a checkpoint. Returns (pre_revert_cp, target_cp).

        By default, all checkpoint files remain active and the pre-revert
        snapshot is appended as the new head. Pass ``keep_history=False`` to
        remove checkpoints newer than the target. If that target is itself a
        pre-revert checkpoint carrying a log_snapshot, discard mode rebuilds
        the full original log from that snapshot instead of just truncating.
        """
        entries = self.list_checkpoints(ctx_name)  # captured before any mutations
        # Preconditions and the recovery snapshot concern the directly owned
        # Context record. Do not resolve MemoryRef targets or embedded
        # Contexts merely to decide whether a reviewed frame is still fresh.
        ctx = self.load_direct(ctx_name)
        if expected_context_uid is not None and ctx.uid != expected_context_uid:
            raise ConcurrentContextUpdateError(
                "Context identity changed before the reviewed revert."
            )
        if (
            expected_context_digest is not None
            and context_record_digest(ctx) != expected_context_digest
        ):
            raise ConcurrentContextUpdateError(
                "Context content changed before the reviewed revert."
            )
        if (
            expected_history_digest is not None
            and checkpoint_history_digest(entries) != expected_history_digest
        ):
            raise ConcurrentContextUpdateError(
                "Checkpoint history changed before the reviewed revert."
            )
        matches = [e for e in entries if e["uid"].startswith(uid_prefix)]
        if not matches:
            raise KeyError(f"No checkpoint with uid prefix '{uid_prefix}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous prefix '{uid_prefix}' matches {len(matches)} checkpoints."
            )

        target_data = matches[0]
        target_ts = target_data["timestamp"]
        cp_dir = self._checkpoints_dir(ctx_name)
        checkpoint_paths = tuple(sorted(cp_dir.glob("*.json")))
        if any(path.is_symlink() or not path.is_file() for path in checkpoint_paths):
            raise ValueError(f"Checkpoint history for '{ctx_name}' is unsafe.")
        original_checkpoint_bytes = {
            path.name: path.read_bytes() for path in checkpoint_paths
        }
        physical_records: dict[str, dict[str, object]] = {}
        for path in checkpoint_paths:
            try:
                with open(path, encoding="utf-8") as file:
                    record = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(
                    f"Checkpoint history for '{ctx_name}' is invalid."
                ) from error
            if not isinstance(record, dict):
                raise ValueError(f"Checkpoint history for '{ctx_name}' is invalid.")
            physical_records[path.name] = record

        restoration_snapshot = target_data["snapshot"]
        if restoration_snapshot.get("uid") != ctx.uid:
            lineage_edges = checkpoint_memory_lineage_edges((entries,))
            restoration_snapshot = remap_restoration_snapshot(
                restoration_snapshot,
                target=ctx,
                edges=lineage_edges,
            )
        restored = self._context_for_restoration(
            restoration_snapshot,
            context_uid=ctx.uid,
            context_name=ctx.name,
            expected_context_digest=context_record_digest(ctx),
        )
        restored_snapshot = restored.to_dict()

        # Strip nested log snapshots so the recovery frame remains bounded.
        thin_entries: list[dict] = []
        for entry in entries:
            args = entry.get("args") or {}
            if "log_snapshot" in args:
                entry = {
                    **entry,
                    "args": {
                        key: value
                        for key, value in args.items()
                        if key != "log_snapshot"
                    },
                }
            thin_entries.append(entry)

        message = f"Pre-revert to [{target_data['uid'][:8]}] — revert here to undo"
        pre_args: dict[str, object] = {
            "target_uid": target_data["uid"],
            "keep_history": keep_history,
            "log_snapshot": thin_entries,
        }
        if revert_unit is not None:
            pre_args["revert_unit"] = copy.deepcopy(revert_unit)
            contexts = revert_unit.get("contexts")
            if not isinstance(contexts, list):
                raise ValueError("Recursive Revert membership is invalid.")
            pre_args["command_contexts"] = copy.deepcopy(contexts)
        pre_cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command="revert",
            args=pre_args,
            description=message,
            auto=True,
        )
        pre_slug = message[:24].replace(" ", "-").replace("/", "-")
        pre_name = (
            f"{pre_cp.timestamp.strftime('%Y%m%dT%H%M%S')}-"
            f"{pre_slug}-{pre_cp.uid[:8]}.json"
        )
        pre_record: dict[str, object] = {
            "uid": pre_cp.uid,
            "message": pre_cp.message,
            "timestamp": pre_cp.timestamp.isoformat(),
            "snapshot": pre_cp.snapshot,
            "command": pre_cp.command,
            "args": pre_cp.args,
            "description": pre_cp.description,
            "auto": pre_cp.auto,
        }
        if restored_snapshot != target_data["snapshot"]:
            # The selected inherited checkpoint remains authentic Source
            # evidence. Retain the exact Branch-namespace post-image beside
            # the Revert receipt so History, Trace, Undo, Rename, and a later
            # Revert all reconstruct the state that was actually published.
            pre_record["restored_snapshot"] = restored_snapshot

        desired_records: dict[str, dict[str, object]]
        if keep_history:
            desired_records = dict(physical_records)
        else:
            log_snapshot = (target_data.get("args") or {}).get("log_snapshot")
            if log_snapshot is not None:
                if not isinstance(log_snapshot, list):
                    raise ValueError("Checkpoint log snapshot is invalid.")
                desired_records = {}
                for entry in sorted(
                    log_snapshot,
                    key=lambda value: value["timestamp"],
                ):
                    if not isinstance(entry, dict):
                        raise ValueError("Checkpoint log snapshot is invalid.")
                    timestamp = datetime.fromisoformat(entry["timestamp"])
                    uid = entry.get("uid")
                    if not isinstance(uid, str) or not uid:
                        raise ValueError("Checkpoint log snapshot is invalid.")
                    filename = f"{timestamp.strftime('%Y%m%dT%H%M%S')}-{uid[:8]}.json"
                    if filename in desired_records:
                        raise ValueError(
                            "Checkpoint log snapshot contains duplicate entries."
                        )
                    desired_records[filename] = entry
            else:
                desired_records = {
                    filename: record
                    for filename, record in physical_records.items()
                    if record["timestamp"] <= target_ts
                }
        if pre_name in desired_records:
            raise ValueError("Recovery checkpoint filename collided with history.")
        desired_records[pre_name] = pre_record

        context_path = self._context_file(ctx_name)
        original_context_bytes = context_path.read_bytes()
        written_names: set[str] = set()
        try:
            # Prepare every replacement with the normal atomic writer before
            # removing obsolete history. The command lock keeps other history
            # operations outside this exception-rollback boundary.
            for filename, record in desired_records.items():
                destination = cp_dir / filename
                if destination.is_symlink():
                    raise ValueError(
                        f"Refusing to restore checkpoint for '{ctx_name}' "
                        "through a symbolic link."
                    )
                _write_json_atomic(destination, record)
                written_names.add(filename)
            for filename in original_checkpoint_bytes:
                if filename not in desired_records:
                    (cp_dir / filename).unlink()
            self._save_locked(
                restored,
                None,
                expected_context_digest=ctx._store_digest,
            )
        except Exception as error:
            rollback_error: Exception | None = None
            for filename in written_names:
                if filename in original_checkpoint_bytes:
                    continue
                try:
                    path = cp_dir / filename
                    if path.exists() and not path.is_symlink():
                        path.unlink()
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            for filename, content in original_checkpoint_bytes.items():
                try:
                    _write_bytes_atomic(cp_dir / filename, content)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            try:
                _write_bytes_atomic(context_path, original_context_bytes)
            except Exception as candidate:
                rollback_error = rollback_error or candidate
            if rollback_error is not None:
                raise RuntimeError(
                    "Revert failed and its original Context/history could not "
                    "be fully restored."
                ) from rollback_error
            raise error
        restored._store_digest = context_record_digest(restored)

        target_cp = Checkpoint(
            uid=target_data["uid"],
            message=target_data.get("message", ""),
            timestamp=datetime.fromisoformat(target_data["timestamp"]),
            snapshot=restored_snapshot,
            command=target_data.get("command"),
            args=target_data.get("args"),
            description=target_data.get("description"),
            auto=target_data.get("auto", False),
        )
        return pre_cp, target_cp
