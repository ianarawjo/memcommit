"""Recoverable, read-only Context history reconstruction.

The store persists complete direct-Context snapshots.  This module turns those
snapshots into a small public timeline for semantic history search without
opening embedded Contexts, MemoryRef targets, or query-only sources.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Literal

from memcommit.context import Context, Memory
from memcommit.store import MemoryStore, canonical_context_record
from memcommit.temporal_history import direct_memory_deltas


HistoryTransitionKind = Literal[
    "CREATED",
    "EDITED",
    "REMOVED",
    "RESTORED",
]
HistoryEvidence = Literal["RECORDED", "RECONSTRUCTED", "UNRECORDED"]
_MAX_RETAINED_CHECKPOINTS = 100_000


class HistoryError(RuntimeError):
    """A retained Context history cannot be reconstructed safely."""


@dataclass(frozen=True)
class MemoryVersion:
    """One content version of one directly owned Memory."""

    context_uid: str
    context_name: str
    memory_uid: str
    content: str
    content_digest: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.context_uid, self.memory_uid, self.content_digest)


@dataclass(frozen=True)
class HistoryState:
    """One occurrence of a direct Context state in operation order."""

    index: int
    checkpoint_uid: str | None
    timestamp: str | None
    command: str
    description: str
    memories: tuple[MemoryVersion, ...]
    record_digest: str
    selectable: bool
    current: bool = False
    restored: bool = False

    def version_keys(self) -> frozenset[tuple[str, str, str]]:
        return frozenset(version.key for version in self.memories)


@dataclass(frozen=True)
class HistoryCheckpoint:
    """One retained checkpoint and the exact snapshot it selects."""

    uid: str
    timestamp: str
    command: str
    description: str
    auto: bool
    state_index: int
    record_digest: str
    selectable: bool


@dataclass(frozen=True)
class MemoryTransition:
    """One direct Memory change between two adjacent effective states."""

    index: int
    step_index: int
    context_uid: str
    context_name: str
    checkpoint_uid: str | None
    timestamp: str | None
    command: str
    description: str
    kind: HistoryTransitionKind
    evidence: HistoryEvidence
    memory_uid: str
    before: MemoryVersion | None
    after: MemoryVersion | None
    from_state_index: int
    to_state_index: int


@dataclass(frozen=True)
class HistoryTimeline:
    """Recoverable direct-Memory history for exactly one current Context."""

    context_uid: str
    context_name: str
    states: tuple[HistoryState, ...]
    checkpoints: tuple[HistoryCheckpoint, ...]
    transitions: tuple[MemoryTransition, ...]
    warnings: tuple[str, ...] = ()

    def state(self, index: int) -> HistoryState:
        try:
            state = self.states[index]
        except IndexError as error:
            raise HistoryError("History state index is invalid.") from error
        if state.index != index:
            raise HistoryError("History state ordering is invalid.")
        return state

    @property
    def versions(self) -> tuple[MemoryVersion, ...]:
        """Return content versions once, in first-observed order."""
        seen: set[tuple[str, str, str]] = set()
        versions: list[MemoryVersion] = []
        for state in self.states:
            for version in state.memories:
                if version.key in seen:
                    continue
                seen.add(version.key)
                versions.append(version)
        return tuple(versions)


def _json_digest(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise HistoryError("Checkpoint history is not valid JSON data.") from error
    return hashlib.sha256(encoded).hexdigest()


def _validate_entry(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HistoryError("Checkpoint history contains an invalid record.")
    uid = value.get("uid")
    timestamp = value.get("timestamp")
    snapshot = value.get("snapshot")
    if (
        not isinstance(uid, str)
        or not uid
        or not isinstance(timestamp, str)
        or not timestamp
        or not isinstance(snapshot, dict)
    ):
        raise HistoryError("Checkpoint history contains an invalid record.")
    return value


def _entry_identity_digest(entry: dict[str, Any]) -> str:
    """Compare duplicate records without recursively embedded log history.

    ``MemoryStore.revert`` deliberately strips a nested ``log_snapshot`` when
    one pre-revert checkpoint is copied into a later receipt. Those two
    records are the same checkpoint even though only one retains the older
    nested log.
    """
    args = entry.get("args")
    if isinstance(args, dict) and "log_snapshot" in args:
        entry = {
            **entry,
            "args": {
                key: value
                for key, value in args.items()
                if key != "log_snapshot"
            },
        }
    return _json_digest(entry)


def flatten_checkpoint_entries(
    physical_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], frozenset[str]]:
    """Recover entries retained inside pre-revert ``log_snapshot`` records."""
    physical_uids = frozenset(
        _validate_entry(entry)["uid"] for entry in physical_entries
    )
    pending: list[object] = list(physical_entries)
    by_uid: dict[str, dict[str, Any]] = {}
    record_digests: dict[str, str] = {}
    inspected = 0
    while pending:
        inspected += 1
        if inspected > _MAX_RETAINED_CHECKPOINTS:
            raise HistoryError("Checkpoint history is too large to inspect.")
        entry = _validate_entry(pending.pop())
        uid = entry["uid"]
        args = entry.get("args")
        log_snapshot = (
            args.get("log_snapshot") if isinstance(args, dict) else None
        )
        if log_snapshot is not None:
            if not isinstance(log_snapshot, list):
                raise HistoryError(
                    "A revert checkpoint contains an invalid log snapshot."
                )
            pending.extend(log_snapshot)
        digest = _entry_identity_digest(entry)
        prior_digest = record_digests.get(uid)
        if prior_digest is not None:
            if prior_digest != digest:
                raise HistoryError(
                    f"Checkpoint [{uid[:8]}] has conflicting retained records."
                )
            continue
        by_uid[uid] = entry
        record_digests[uid] = digest
    return (
        sorted(
            by_uid.values(),
            key=lambda entry: (entry["timestamp"], entry["uid"]),
        ),
        physical_uids,
    )


def _normalized_record(
    snapshot: object,
    *,
    context_uid: str,
    context_name: str,
) -> dict[str, object]:
    if not isinstance(snapshot, dict):
        raise HistoryError("Checkpoint contains an invalid Context snapshot.")
    try:
        # Branch checkpoints retain their source identity. Revert restores
        # their direct contents into the requested branch identity as well.
        return canonical_context_record(
            {
                **snapshot,
                "uid": context_uid,
                "name": context_name,
            }
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HistoryError(
            "Checkpoint contains an invalid Context snapshot."
        ) from error


def _versions_from_record(
    record: dict[str, object],
    *,
    context_uid: str,
    context_name: str,
) -> tuple[MemoryVersion, ...]:
    try:
        direct = Context.from_dict(record)
    except (KeyError, TypeError, ValueError) as error:
        raise HistoryError(
            "Checkpoint contains an invalid direct Context state."
        ) from error
    versions: list[MemoryVersion] = []
    # Context.from_dict receives no loaders here. It therefore preserves
    # pointers but never opens a MemoryRef target, embedded Context, or
    # query-only source. Only directly owned Memory content enters the index.
    for item in direct.iter_items():
        if not isinstance(item, Memory):
            continue
        versions.append(
            MemoryVersion(
                context_uid=context_uid,
                context_name=context_name,
                memory_uid=item.uid,
                content=item.content,
                content_digest=hashlib.sha256(
                    item.content.encode("utf-8")
                ).hexdigest(),
            )
        )
    return tuple(versions)


def _state(
    index: int,
    record: dict[str, object],
    *,
    context_uid: str,
    context_name: str,
    checkpoint_uid: str | None,
    timestamp: str | None,
    command: str,
    description: str,
    selectable: bool,
    current: bool = False,
    restored: bool = False,
) -> HistoryState:
    return HistoryState(
        index=index,
        checkpoint_uid=checkpoint_uid,
        timestamp=timestamp,
        command=command,
        description=description,
        memories=_versions_from_record(
            record,
            context_uid=context_uid,
            context_name=context_name,
        ),
        record_digest=_json_digest(record),
        selectable=selectable,
        current=current,
        restored=restored,
    )


def _transition_description(
    kind: HistoryTransitionKind,
    before: MemoryVersion | None,
    after: MemoryVersion | None,
) -> str:
    if kind == "CREATED" and after is not None:
        return f"Created Memory: {after.content}"
    if kind == "REMOVED" and before is not None:
        return f"Removed Memory: {before.content}"
    if kind == "EDITED" and before is not None and after is not None:
        return f"Edited Memory: {before.content} -> {after.content}"
    if before is None and after is not None:
        return f"Restored Memory: {after.content}"
    if before is not None and after is None:
        return f"Restored removal of Memory: {before.content}"
    if before is not None and after is not None:
        return f"Restored Memory: {before.content} -> {after.content}"
    return "Restored Context state."


def _memory_changes(
    before: HistoryState,
    after: HistoryState,
    *,
    checkpoint_uid: str | None,
    timestamp: str | None,
    command: str,
    description: str,
    restoration: bool,
    evidence: HistoryEvidence,
    transition_offset: int,
) -> list[MemoryTransition]:
    before_by_uid = {version.memory_uid: version for version in before.memories}
    after_by_uid = {version.memory_uid: version for version in after.memories}
    changes: list[MemoryTransition] = []
    deltas = direct_memory_deltas(
        before_by_uid,
        after_by_uid,
        before_order=tuple(version.memory_uid for version in before.memories),
        after_order=tuple(version.memory_uid for version in after.memories),
        content=lambda version: version.content_digest,
    )
    for delta in deltas:
        old = delta.before
        new = delta.after
        if restoration:
            kind: HistoryTransitionKind = "RESTORED"
        else:
            kind = delta.kind
        changes.append(
            MemoryTransition(
                index=transition_offset + len(changes),
                step_index=after.index,
                context_uid=after.memories[0].context_uid if after.memories else (
                    before.memories[0].context_uid if before.memories else ""
                ),
                context_name=after.memories[0].context_name if after.memories else (
                    before.memories[0].context_name if before.memories else ""
                ),
                checkpoint_uid=checkpoint_uid,
                timestamp=timestamp,
                command=command,
                description=(
                    description
                    or _transition_description(kind, old, new)
                ),
                kind=kind,
                evidence=evidence,
                memory_uid=delta.memory_uid,
                before=old,
                after=new,
                from_state_index=before.index,
                to_state_index=after.index,
            )
        )
    return changes


def build_history(
    store: MemoryStore,
    context_name: str,
) -> HistoryTimeline:
    """Build one read-only recoverable timeline for ``context_name``.

    ``load_direct`` is an intentional privacy boundary: historical search
    indexes direct Memory text only and never resolves pointers.
    """
    try:
        current_context = store.load_direct(context_name)
        physical = store.list_checkpoints(context_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        raise HistoryError(str(error)) from error
    entries, physical_uids = flatten_checkpoint_entries(physical)
    context_uid = current_context.uid
    empty_record: dict[str, object] = {
        "uid": context_uid,
        "name": context_name,
        "memories": {},
        "order": [],
    }
    states: list[HistoryState] = [
        _state(
            0,
            empty_record,
            context_uid=context_uid,
            context_name=context_name,
            checkpoint_uid=None,
            timestamp=None,
            command="initial",
            description="State before the first retained checkpoint.",
            selectable=False,
        )
    ]
    checkpoints: list[HistoryCheckpoint] = []
    transitions: list[MemoryTransition] = []
    warnings: list[str] = []
    records_by_uid = {
        entry["uid"]: _normalized_record(
            entry["snapshot"],
            context_uid=context_uid,
            context_name=context_name,
        )
        for entry in entries
    }

    for entry in entries:
        uid = entry["uid"]
        command_value = entry.get("command")
        command = (
            command_value
            if isinstance(command_value, str) and command_value
            else "checkpoint"
        )
        description_value = entry.get("description") or entry.get("message")
        description = (
            description_value if isinstance(description_value, str) else ""
        )
        snapshot_state = _state(
            len(states),
            records_by_uid[uid],
            context_uid=context_uid,
            context_name=context_name,
            checkpoint_uid=uid,
            timestamp=entry["timestamp"],
            command=command,
            description=description,
            selectable=uid in physical_uids,
        )
        states.append(snapshot_state)
        args = entry.get("args")
        recorded_restoration = (
            command in {"undo", "redo"}
            and isinstance(args, dict)
            and isinstance(args.get("command_restore"), dict)
        )
        transitions.extend(
            _memory_changes(
                states[-2],
                snapshot_state,
                checkpoint_uid=uid,
                timestamp=entry["timestamp"],
                command=command,
                description=description,
                restoration=recorded_restoration,
                evidence=(
                    "RECORDED" if recorded_restoration else "RECONSTRUCTED"
                ),
                transition_offset=len(transitions),
            )
        )
        checkpoints.append(
            HistoryCheckpoint(
                uid=uid,
                timestamp=entry["timestamp"],
                command=command,
                description=description,
                auto=bool(entry.get("auto", False)),
                state_index=snapshot_state.index,
                record_digest=snapshot_state.record_digest,
                selectable=uid in physical_uids,
            )
        )

        if command != "revert":
            continue
        target_uid = args.get("target_uid") if isinstance(args, dict) else None
        target_record = (
            records_by_uid.get(target_uid)
            if isinstance(target_uid, str)
            else None
        )
        if target_record is None:
            warnings.append(
                f"Revert checkpoint [{uid[:8]}] does not retain its target state."
            )
            continue
        restored_state = _state(
            len(states),
            target_record,
            context_uid=context_uid,
            context_name=context_name,
            checkpoint_uid=target_uid,
            timestamp=entry["timestamp"],
            command="revert",
            description=description,
            selectable=target_uid in physical_uids,
            restored=True,
        )
        states.append(restored_state)
        transitions.extend(
            _memory_changes(
                snapshot_state,
                restored_state,
                checkpoint_uid=uid,
                timestamp=entry["timestamp"],
                command="revert",
                description=description,
                restoration=True,
                evidence="RECORDED",
                transition_offset=len(transitions),
            )
        )

    current_record = canonical_context_record(current_context)
    if _json_digest(current_record) != states[-1].record_digest:
        current_state = _state(
            len(states),
            current_record,
            context_uid=context_uid,
            context_name=context_name,
            checkpoint_uid=None,
            timestamp=None,
            command="current",
            description=(
                "Current Context differs from the last reconstructable "
                "checkpoint state."
            ),
            selectable=False,
            current=True,
        )
        states.append(current_state)
        transitions.extend(
            _memory_changes(
                states[-2],
                current_state,
                checkpoint_uid=None,
                timestamp=None,
                command="current",
                description=current_state.description,
                restoration=False,
                evidence="UNRECORDED",
                transition_offset=len(transitions),
            )
        )
        warnings.append(current_state.description)
    elif states:
        # Mark the effective last occurrence as current without manufacturing
        # a duplicate state or changing its exact checkpoint selector.
        last = states[-1]
        states[-1] = HistoryState(
            **{**last.__dict__, "current": True}
        )

    return HistoryTimeline(
        context_uid=context_uid,
        context_name=context_name,
        states=tuple(states),
        checkpoints=tuple(checkpoints),
        transitions=tuple(transitions),
        warnings=tuple(dict.fromkeys(warnings)),
    )
