"""Reviewed repair of locator metadata missed by an earlier Context rename."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from memcommit.application.capabilities.command_recovery import CommandStacks, build_command_stacks
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import HistoryError, flatten_checkpoint_entries
from memcommit.persistence.store import (
    MemoryStore,
    _rewrite_checkpoint_record,
    _write_bytes_atomic,
    _write_json_atomic,
    validate_context_name,
)


@dataclass(frozen=True)
class RenameHistoryRepairPlan:
    """Freshness-bound preview for one exact UID/name locator repair."""

    context_uid: str
    old_name: str
    new_name: str
    current_owner: str
    checkpoint_files_scanned: int
    changed_checkpoint_files: tuple[tuple[str, str], ...]
    changed_reference_count: int
    context_graph_digest: str
    checkpoint_graph_digest: str
    plan_digest: str


@dataclass(frozen=True)
class RenameHistoryRepairResult:
    """Committed repair and the command stacks verified before release."""

    plan: RenameHistoryRepairPlan
    undo_depth: int
    redo_depth: int


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_context_uid(value: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Repair Context uid is invalid.") from error
    if value != canonical:
        raise ValueError("Repair Context uid must be a canonical UUID.")
    return canonical


def _has_exact_rename_evidence(
    checkpoints: dict[str, dict[str, dict[str, object]]],
    *,
    context_uid: str,
    old_name: str,
    new_name: str,
) -> bool:
    for entries in checkpoints.values():
        try:
            flattened, _ = flatten_checkpoint_entries(list(entries.values()))
        except HistoryError as error:
            raise ValueError(str(error)) from error
        for entry in flattened:
            args = entry.get("args")
            if (
                entry.get("command") == "rename"
                and isinstance(args, dict)
                and args.get("old_name") == old_name
                and args.get("new_name") == new_name
                and args.get("context_uid") == context_uid
            ):
                return True
    return False


def _prepare_locked(
    store: MemoryStore,
    *,
    context_uid: str,
    old_name: str,
    new_name: str,
) -> tuple[RenameHistoryRepairPlan, dict[Path, dict[str, object]]]:
    records, checkpoints = store._read_context_graph_for_rename()
    owners = [
        name for name, record in records.items() if record.get("uid") == context_uid
    ]
    if owners != [new_name]:
        if not owners:
            raise ValueError("Repair Context uid has no live ordinary owner.")
        raise ValueError(
            "Repair Context uid is not currently owned by the exact new name."
        )
    if not _has_exact_rename_evidence(
        checkpoints,
        context_uid=context_uid,
        old_name=old_name,
        new_name=new_name,
    ):
        raise ValueError(
            "Checkpoint history has no exact rename receipt for this repair."
        )

    moved_names_by_uid = {context_uid: (old_name, new_name)}
    writes: dict[Path, dict[str, object]] = {}
    changed_files: list[tuple[str, str]] = []
    changed_references = 0
    file_count = 0
    for owner_name, entries in checkpoints.items():
        for filename, before in entries.items():
            file_count += 1
            _same, _same_count, before_collisions = _rewrite_checkpoint_record(
                before,
                moved_names_by_uid={},
            )
            after, count, after_collisions = _rewrite_checkpoint_record(
                before,
                moved_names_by_uid=moved_names_by_uid,
            )
            introduced = set(after_collisions) - set(before_collisions)
            if introduced:
                raise ValueError(
                    f"Repairing checkpoint '{filename}' in '{owner_name}' would "
                    "make ordinary and query-only Context selectors collide: "
                    + ", ".join(repr(name) for name in sorted(introduced))
                    + "."
                )
            if after == before:
                continue
            path = store._checkpoints_dir(owner_name) / filename
            writes[path] = after
            changed_files.append((owner_name, filename))
            changed_references += count

    context_graph_digest = _canonical_digest(records)
    checkpoint_graph_digest = _canonical_digest(checkpoints)
    plan_body = {
        "version": 1,
        "context_uid": context_uid,
        "old_name": old_name,
        "new_name": new_name,
        "current_owner": new_name,
        "checkpoint_files_scanned": file_count,
        "changed_checkpoint_files": sorted(changed_files),
        "changed_reference_count": changed_references,
        "context_graph_digest": context_graph_digest,
        "checkpoint_graph_digest": checkpoint_graph_digest,
    }
    plan = RenameHistoryRepairPlan(
        context_uid=context_uid,
        old_name=old_name,
        new_name=new_name,
        current_owner=new_name,
        checkpoint_files_scanned=file_count,
        changed_checkpoint_files=tuple(sorted(changed_files)),
        changed_reference_count=changed_references,
        context_graph_digest=context_graph_digest,
        checkpoint_graph_digest=checkpoint_graph_digest,
        plan_digest=_canonical_digest(plan_body),
    )
    return plan, writes


def _locked_context_names(store: MemoryStore) -> tuple[str, ...]:
    return tuple(sorted(store._read_direct_context_records_strict()))


def plan_rename_history_repair(
    store: MemoryStore,
    *,
    context_uid: str,
    old_name: str,
    new_name: str,
) -> RenameHistoryRepairPlan:
    """Preview an exact typed-locator repair without changing storage."""

    context_uid = _validate_context_uid(context_uid)
    validate_context_name(old_name)
    validate_context_name(new_name)
    if old_name == new_name:
        raise ValueError("Repair old and new Context names must differ.")
    with store._context_graph_lock(exclusive=True):
        names = _locked_context_names(store)
        with store._context_write_locks(names):
            plan, _writes = _prepare_locked(
                store,
                context_uid=context_uid,
                old_name=old_name,
                new_name=new_name,
            )
            return plan


def _rollback_checkpoint_files(original_bytes: dict[Path, bytes]) -> None:
    rollback_error: Exception | None = None
    for path, content in original_bytes.items():
        try:
            _write_bytes_atomic(path, content)
        except Exception as error:
            rollback_error = rollback_error or error
    if rollback_error is not None:
        raise RuntimeError(
            "Checkpoint repair failed and original history could not be restored."
        ) from rollback_error


def apply_rename_history_repair(
    store: MemoryStore,
    *,
    context_uid: str,
    old_name: str,
    new_name: str,
    expected_plan_digest: str,
) -> RenameHistoryRepairResult:
    """Apply one reviewed repair and reject any stale checkpoint graph."""

    context_uid = _validate_context_uid(context_uid)
    validate_context_name(old_name)
    validate_context_name(new_name)
    if old_name == new_name:
        raise ValueError("Repair old and new Context names must differ.")
    if len(expected_plan_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_plan_digest
    ):
        raise ValueError("Expected repair plan digest is invalid.")

    with store._command_write_lock():
        store._assert_profile_write_allowed()
        with store._context_graph_lock(exclusive=True):
            names = _locked_context_names(store)
            with store._context_write_locks(names):
                plan, writes = _prepare_locked(
                    store,
                    context_uid=context_uid,
                    old_name=old_name,
                    new_name=new_name,
                )
                if plan.plan_digest != expected_plan_digest:
                    raise ValueError(
                        "Checkpoint history changed after the repair was reviewed."
                    )
                original_bytes = {path: path.read_bytes() for path in writes}
                try:
                    for path, record in writes.items():
                        _write_json_atomic(path, record)
                    stacks: CommandStacks = build_command_stacks(store)
                except Exception:
                    _rollback_checkpoint_files(original_bytes)
                    raise
                return RenameHistoryRepairResult(
                    plan=plan,
                    undo_depth=len(stacks.undo),
                    redo_depth=len(stacks.redo),
                )
