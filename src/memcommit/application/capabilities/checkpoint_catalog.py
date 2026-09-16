"""Profile-wide resolution of persisted checkpoint recovery units.

A checkpoint UID identifies one physical Context checkpoint.  Recursive manual
Checkpoint records additionally describe one indivisible recovery unit across
several physical checkpoints.  This module is the shared read-only boundary
that resolves either form without making Revert, Diff, or History parse raw
checkpoint arguments independently.
"""

from __future__ import annotations

import copy
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from memcommit.core.context import Checkpoint
from memcommit.persistence.store import (
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
)


_UID_PREFIX = re.compile(r"[0-9a-fA-F-]{8,64}")


class CheckpointCatalogError(ValueError):
    """The Profile checkpoint catalog cannot resolve one safe recovery unit."""


class CheckpointNotFoundError(CheckpointCatalogError):
    """No checkpoint identity matches one otherwise valid selector."""


@dataclass(frozen=True)
class ResolvedCheckpointMember:
    """One physical checkpoint and its freshness-bound live owner."""

    context_uid: str
    context_name: str
    checkpoint_uid: str
    checkpoint: dict[str, Any]
    expected_context_digest: str
    expected_history_digest: str


@dataclass(frozen=True)
class ResolvedCheckpointUnit:
    """One globally resolved single- or multi-Context recovery unit."""

    canonical_uid: str
    selected_uid: str
    root_context_uid: str
    root_context_name: str
    members: tuple[ResolvedCheckpointMember, ...]
    checkpoint_set_uid: str | None = None
    legacy_aliases: tuple[str, ...] = ()

    @property
    def is_recursive_set(self) -> bool:
        return self.checkpoint_set_uid is not None


@dataclass(frozen=True)
class CheckpointUnitRevertMember:
    """One member result published by an atomic checkpoint-unit Revert."""

    context_name: str
    target: Checkpoint
    recovery: Checkpoint


@dataclass(frozen=True)
class CheckpointUnitRevertResult:
    """The complete result of one atomic recursive checkpoint Revert."""

    unit: ResolvedCheckpointUnit
    receipt_uid: str
    members: tuple[CheckpointUnitRevertMember, ...]


@dataclass(frozen=True)
class _FrozenHistory:
    context_uid: str
    context_name: str
    context_digest: str
    history_digest: str
    checkpoints: tuple[dict[str, Any], ...]


def _canonical_uuid(value: object, *, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise CheckpointCatalogError(f"{label} is invalid.") from error
    if value != canonical:
        raise CheckpointCatalogError(f"{label} is invalid.")
    return canonical


def _checkpoint_set(checkpoint: Mapping[str, object]) -> Mapping[str, object] | None:
    args = checkpoint.get("args")
    if not isinstance(args, Mapping):
        return None
    value = args.get("checkpoint_set")
    return value if isinstance(value, Mapping) else None


def _command_contexts(
    checkpoint: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    args = checkpoint.get("args")
    raw = args.get("command_contexts") if isinstance(args, Mapping) else None
    if not isinstance(raw, list) or not raw:
        raise CheckpointCatalogError(
            "Recursive checkpoint membership is missing or invalid."
        )
    members: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != {"uid", "name"}:
            raise CheckpointCatalogError(
                "Recursive checkpoint membership is missing or invalid."
            )
        context_uid = item.get("uid")
        context_name = item.get("name")
        if (
            not isinstance(context_uid, str)
            or not context_uid
            or not isinstance(context_name, str)
            or not context_name
        ):
            raise CheckpointCatalogError(
                "Recursive checkpoint membership is missing or invalid."
            )
        members.append((context_uid, context_name))
    if len(members) != len(set(members)):
        raise CheckpointCatalogError("Recursive checkpoint membership is duplicated.")
    return tuple(members)


class CheckpointCatalog:
    """One command-local frozen view of every ordinary local checkpoint."""

    def __init__(self, histories: Sequence[_FrozenHistory]):
        self._histories = tuple(histories)
        self._history_by_name = {
            history.context_name: history for history in self._histories
        }
        self._history_by_uid = {
            history.context_uid: history for history in self._histories
        }
        if len(self._history_by_uid) != len(self._histories):
            raise CheckpointCatalogError("Ordinary Context identity is duplicated.")

    @classmethod
    def freeze(cls, store: MemoryStore) -> "CheckpointCatalog":
        """Freeze the complete direct local graph and every retained history."""

        histories: list[_FrozenHistory] = []
        for context in sorted(
            store.load_direct_context_graph_strict(), key=lambda value: value.name
        ):
            checkpoints = store.list_checkpoints(context.name)
            copied: list[dict[str, Any]] = []
            for checkpoint in checkpoints:
                uid = checkpoint.get("uid")
                if not isinstance(uid, str) or not uid:
                    raise CheckpointCatalogError(
                        f"Checkpoint history for '{context.name}' has no valid uid."
                    )
                copied.append(copy.deepcopy(checkpoint))
            histories.append(
                _FrozenHistory(
                    context_uid=context.uid,
                    context_name=context.name,
                    context_digest=context_record_digest(context),
                    history_digest=checkpoint_history_digest(checkpoints),
                    checkpoints=tuple(copied),
                )
            )
        return cls(histories)

    def resolve(
        self,
        selector: str,
        *,
        context_name: str | None = None,
    ) -> ResolvedCheckpointUnit:
        """Resolve one UID prefix globally, optionally at one exact location."""

        selector = selector.strip()
        if (
            _UID_PREFIX.fullmatch(selector) is None
            or sum(character != "-" for character in selector) < 8
        ):
            raise CheckpointCatalogError(
                "Checkpoint UID selectors require at least eight hexadecimal digits."
            )
        if context_name is not None and context_name not in self._history_by_name:
            raise CheckpointCatalogError(
                f"Context '{context_name}' is not available in the checkpoint catalog."
            )

        physical: list[tuple[_FrozenHistory, dict[str, Any]]] = []
        legacy_set_uids: set[str] = set()
        histories = (
            (self._history_by_name[context_name],)
            if context_name is not None
            else self._histories
        )
        for history in histories:
            for checkpoint in history.checkpoints:
                uid = checkpoint["uid"]
                snapshot = checkpoint.get("snapshot")
                directly_owned = (
                    isinstance(snapshot, Mapping)
                    and snapshot.get("uid") == history.context_uid
                )
                if uid.startswith(selector) and (
                    context_name is not None or directly_owned
                ):
                    physical.append((history, checkpoint))
                metadata = _checkpoint_set(checkpoint)
                if metadata is None or metadata.get("version") != 1:
                    continue
                set_uid = metadata.get("uid")
                if (
                    isinstance(set_uid, str)
                    and set_uid.startswith(selector)
                    and (context_name is not None or directly_owned)
                ):
                    legacy_set_uids.add(set_uid)

        candidate_uids = {checkpoint["uid"] for _history, checkpoint in physical}
        candidate_uids.update(legacy_set_uids)
        if not candidate_uids:
            raise CheckpointNotFoundError(
                f"no checkpoint with uid prefix '{selector}' exists in the "
                "ordinary local Profile."
            )
        if len(candidate_uids) > 1:
            raise CheckpointCatalogError(
                f"Ambiguous prefix '{selector}' matches {len(candidate_uids)} "
                "global checkpoint identities."
            )

        selected_uid = next(iter(candidate_uids))
        if selected_uid in legacy_set_uids and not any(
            checkpoint["uid"] == selected_uid for _history, checkpoint in physical
        ):
            return self._resolve_legacy_set(selected_uid)

        matching = [
            (history, checkpoint)
            for history, checkpoint in physical
            if checkpoint["uid"] == selected_uid
        ]
        if len(matching) != 1:
            raise CheckpointCatalogError(
                f"Checkpoint uid '{selected_uid}' has no unique live location."
            )
        history, checkpoint = matching[0]
        metadata = _checkpoint_set(checkpoint)
        if metadata is None:
            return self._single_unit(history, checkpoint)
        if metadata.get("version") == 1:
            return self._resolve_legacy_set(
                _canonical_uuid(metadata.get("uid"), label="Checkpoint set uid"),
                selected_uid=selected_uid,
                selected_context_uid=history.context_uid,
            )
        if metadata.get("version") == 2:
            return self._resolve_version_two_set(
                metadata,
                selected_uid=selected_uid,
                selected_context_uid=history.context_uid,
            )
        raise CheckpointCatalogError("Checkpoint set version is unsupported.")

    def _single_unit(
        self,
        history: _FrozenHistory,
        checkpoint: dict[str, Any],
    ) -> ResolvedCheckpointUnit:
        member = self._member(history, checkpoint)
        return ResolvedCheckpointUnit(
            canonical_uid=member.checkpoint_uid,
            selected_uid=member.checkpoint_uid,
            root_context_uid=member.context_uid,
            root_context_name=member.context_name,
            members=(member,),
        )

    @staticmethod
    def _member(
        history: _FrozenHistory,
        checkpoint: dict[str, Any],
    ) -> ResolvedCheckpointMember:
        return ResolvedCheckpointMember(
            context_uid=history.context_uid,
            context_name=history.context_name,
            checkpoint_uid=checkpoint["uid"],
            checkpoint=copy.deepcopy(checkpoint),
            expected_context_digest=history.context_digest,
            expected_history_digest=history.history_digest,
        )

    def _resolve_version_two_set(
        self,
        metadata: Mapping[str, object],
        *,
        selected_uid: str,
        selected_context_uid: str,
    ) -> ResolvedCheckpointUnit:
        expected = {"version", "uid", "root", "include_descendants", "members"}
        if set(metadata) != expected or metadata.get("include_descendants") is not True:
            raise CheckpointCatalogError("Recursive checkpoint manifest is invalid.")
        set_uid = _canonical_uuid(metadata.get("uid"), label="Checkpoint set uid")
        root = metadata.get("root")
        raw_members = metadata.get("members")
        if (
            not isinstance(root, Mapping)
            or set(root) != {"uid", "name"}
            or not isinstance(raw_members, list)
            or not raw_members
        ):
            raise CheckpointCatalogError("Recursive checkpoint manifest is invalid.")
        root_uid = root.get("uid")
        root_name = root.get("name")
        if (
            not isinstance(root_uid, str)
            or not root_uid
            or not isinstance(root_name, str)
            or not root_name
        ):
            raise CheckpointCatalogError("Recursive checkpoint root is invalid.")

        manifest_members: list[tuple[str, str, str]] = []
        for item in raw_members:
            if not isinstance(item, Mapping) or set(item) != {
                "context_uid",
                "context_name",
                "checkpoint_uid",
            }:
                raise CheckpointCatalogError(
                    "Recursive checkpoint member manifest is invalid."
                )
            context_uid = item.get("context_uid")
            context_name = item.get("context_name")
            checkpoint_uid = item.get("checkpoint_uid")
            if (
                not isinstance(context_uid, str)
                or not context_uid
                or not isinstance(context_name, str)
                or not context_name
            ):
                raise CheckpointCatalogError(
                    "Recursive checkpoint member manifest is invalid."
                )
            manifest_members.append(
                (
                    context_uid,
                    context_name,
                    _canonical_uuid(
                        checkpoint_uid,
                        label="Recursive member checkpoint uid",
                    ),
                )
            )
        if (
            len({item[0] for item in manifest_members}) != len(manifest_members)
            or len({item[1] for item in manifest_members}) != len(manifest_members)
            or len({item[2] for item in manifest_members}) != len(manifest_members)
        ):
            raise CheckpointCatalogError(
                "Recursive checkpoint member manifest contains duplicates."
            )
        if (selected_context_uid, selected_uid) not in {
            (context_uid, checkpoint_uid)
            for context_uid, _context_name, checkpoint_uid in manifest_members
        }:
            raise CheckpointCatalogError(
                "An inherited recursive checkpoint cannot retarget its Source unit."
            )
        root_members = [
            item
            for item in manifest_members
            if item[0] == root_uid and item[1] == root_name
        ]
        if len(root_members) != 1 or root_members[0][2] != set_uid:
            raise CheckpointCatalogError(
                "Recursive checkpoint root is not its canonical checkpoint."
            )

        manifest_record = copy.deepcopy(dict(metadata))
        members: list[ResolvedCheckpointMember] = []
        for context_uid, _historical_name, checkpoint_uid in manifest_members:
            history = self._history_by_uid.get(context_uid)
            if history is None:
                raise CheckpointCatalogError(
                    "A recursive checkpoint member no longer has a live Context."
                )
            matches = [
                checkpoint
                for checkpoint in history.checkpoints
                if checkpoint.get("uid") == checkpoint_uid
            ]
            if len(matches) != 1:
                raise CheckpointCatalogError(
                    f"Recursive checkpoint member '{history.context_name}' is missing."
                )
            checkpoint = matches[0]
            snapshot = checkpoint.get("snapshot")
            if (
                checkpoint.get("command") != "checkpoint"
                or not isinstance(snapshot, Mapping)
                or snapshot.get("uid") != context_uid
                or dict(_checkpoint_set(checkpoint) or {}) != manifest_record
            ):
                raise CheckpointCatalogError(
                    "Recursive checkpoint member manifests are inconsistent."
                )
            members.append(self._member(history, checkpoint))

        root_history = self._history_by_uid.get(root_uid)
        if root_history is None:
            raise CheckpointCatalogError(
                "Recursive checkpoint root no longer has a live Context."
            )
        return ResolvedCheckpointUnit(
            canonical_uid=set_uid,
            selected_uid=selected_uid,
            root_context_uid=root_uid,
            root_context_name=root_history.context_name,
            members=tuple(members),
            checkpoint_set_uid=set_uid,
        )

    def _resolve_legacy_set(
        self,
        set_uid: str,
        *,
        selected_uid: str | None = None,
        selected_context_uid: str | None = None,
    ) -> ResolvedCheckpointUnit:
        seeds: list[tuple[_FrozenHistory, dict[str, Any]]] = []
        for history in self._histories:
            for checkpoint in history.checkpoints:
                metadata = _checkpoint_set(checkpoint)
                if (
                    metadata is not None
                    and metadata.get("version") == 1
                    and metadata.get("uid") == set_uid
                ):
                    seeds.append((history, checkpoint))
        if not seeds:
            raise CheckpointCatalogError("Legacy checkpoint set is unavailable.")
        metadata = dict(_checkpoint_set(seeds[0][1]) or {})
        expected = {"version", "uid", "root", "include_descendants"}
        root_name = metadata.get("root")
        if (
            set(metadata) != expected
            or metadata.get("include_descendants") is not True
            or not isinstance(root_name, str)
            or not root_name
        ):
            raise CheckpointCatalogError("Legacy checkpoint set metadata is invalid.")
        membership = _command_contexts(seeds[0][1])
        if selected_context_uid is not None and selected_context_uid not in {
            context_uid for context_uid, _name in membership
        }:
            raise CheckpointCatalogError(
                "An inherited legacy checkpoint cannot retarget its Source unit."
            )
        if any(
            dict(_checkpoint_set(checkpoint) or {}) != metadata
            or _command_contexts(checkpoint) != membership
            for _history, checkpoint in seeds
        ):
            raise CheckpointCatalogError(
                "Legacy checkpoint set member manifests are inconsistent."
            )
        roots = [item for item in membership if item[1] == root_name]
        if len(roots) != 1:
            raise CheckpointCatalogError("Legacy checkpoint set root is invalid.")

        members: list[ResolvedCheckpointMember] = []
        root_checkpoint_uid: str | None = None
        for context_uid, historical_name in membership:
            history = self._history_by_uid.get(context_uid)
            if history is None:
                raise CheckpointCatalogError(
                    "A legacy checkpoint set member no longer has a live Context."
                )
            matches = []
            for checkpoint in history.checkpoints:
                if (
                    checkpoint.get("command") == "checkpoint"
                    and dict(_checkpoint_set(checkpoint) or {}) == metadata
                    and _command_contexts(checkpoint) == membership
                ):
                    matches.append(checkpoint)
            if len(matches) != 1:
                raise CheckpointCatalogError(
                    f"Legacy checkpoint member '{history.context_name}' is missing."
                )
            checkpoint = matches[0]
            snapshot = checkpoint.get("snapshot")
            if not isinstance(snapshot, Mapping) or snapshot.get("uid") != context_uid:
                raise CheckpointCatalogError(
                    "Legacy checkpoint set member identity is inconsistent."
                )
            member = self._member(history, checkpoint)
            members.append(member)
            if historical_name == root_name:
                root_checkpoint_uid = member.checkpoint_uid

        if root_checkpoint_uid is None:
            raise CheckpointCatalogError("Legacy checkpoint set root is unavailable.")
        root_uid = roots[0][0]
        root_history = self._history_by_uid[root_uid]
        return ResolvedCheckpointUnit(
            canonical_uid=root_checkpoint_uid,
            selected_uid=selected_uid or set_uid,
            root_context_uid=root_uid,
            root_context_name=root_history.context_name,
            members=tuple(members),
            checkpoint_set_uid=set_uid,
            legacy_aliases=(set_uid,),
        )


def freeze_checkpoint_catalog(store: MemoryStore) -> CheckpointCatalog:
    """Return the shared command-local Profile checkpoint catalog."""

    return CheckpointCatalog.freeze(store)


def resolve_checkpoint_unit(
    store: MemoryStore,
    selector: str,
    *,
    context_name: str | None = None,
) -> ResolvedCheckpointUnit:
    """Freeze and resolve one globally meaningful checkpoint selector."""

    return freeze_checkpoint_catalog(store).resolve(
        selector,
        context_name=context_name,
    )
