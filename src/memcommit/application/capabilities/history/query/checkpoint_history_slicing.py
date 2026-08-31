"""Build exact checkpoint windows and revisions from canonical History evidence."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from memcommit.application.capabilities.history.history_evidence_source import (
    HistoryEvidenceSource,
)
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    HistoryCheckpoint,
    HistoryError,
    HistoryTimeline,
    MemoryTransition,
    flatten_checkpoint_entries,
    reconstruct_checkpoint_timeline,
)


@dataclass(frozen=True, slots=True)
class CheckpointHistoryRevision:
    """One checkpoint's complete direct state before and after its revision."""

    checkpoint: HistoryCheckpoint
    record: Mapping[str, Any]
    before_snapshot: Mapping[str, Any]
    after_snapshot: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CheckpointHistorySlice:
    """One frozen checkpoint catalog and its canonical state timeline.

    ``entries`` includes revert-retained records in chronological order.
    ``physical_entries`` preserves the selectable on-disk catalog in
    newest-first order for Log, Diff, and checkpoint pickers.
    """

    timeline: HistoryTimeline
    entries: tuple[Mapping[str, Any], ...]
    physical_entries: tuple[Mapping[str, Any], ...]
    _records_by_uid: Mapping[str, Mapping[str, Any]] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _before_by_uid: Mapping[str, Mapping[str, Any]] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _checkpoints_by_uid: Mapping[str, HistoryCheckpoint] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        records = {
            entry["uid"]: entry
            for entry in self.entries
            if isinstance(entry.get("uid"), str)
        }
        checkpoints = {item.uid: item for item in self.timeline.checkpoints}
        if set(records) != set(checkpoints):
            raise HistoryError(
                "Checkpoint records do not match their canonical History timeline."
            )
        previous: Mapping[str, Any] = MappingProxyType(
            {"memories": MappingProxyType({}), "order": ()}
        )
        before_by_uid: dict[str, Mapping[str, Any]] = {}
        for entry in self.entries:
            uid = entry["uid"]
            command_before = entry.get("command_before")
            before_by_uid[uid] = (
                command_before
                if isinstance(command_before, Mapping)
                else previous
            )
            snapshot = entry.get("snapshot")
            if not isinstance(snapshot, Mapping):
                raise HistoryError("Checkpoint has no complete Context snapshot.")
            previous = snapshot
        object.__setattr__(self, "_records_by_uid", MappingProxyType(records))
        object.__setattr__(self, "_before_by_uid", MappingProxyType(before_by_uid))
        object.__setattr__(
            self,
            "_checkpoints_by_uid",
            MappingProxyType(checkpoints),
        )

    @property
    def context_uid(self) -> str:
        return self.timeline.context_uid

    @property
    def context_name(self) -> str:
        return self.timeline.context_name

    def checkpoint(self, uid: str) -> HistoryCheckpoint:
        """Return one exact retained checkpoint, including archived evidence."""

        try:
            return self._checkpoints_by_uid[uid]
        except KeyError as error:
            raise HistoryError(f"Checkpoint [{uid[:8]}] is not retained.") from error

    def record(self, uid: str) -> Mapping[str, Any]:
        self.checkpoint(uid)
        return self._records_by_uid[uid]

    def reference(self, checkpoint_uids: tuple[str, ...]) -> tuple[HistoryCheckpoint, ...]:
        """Freeze an exact nonempty checkpoint set in caller-supplied order."""

        if not checkpoint_uids or len(set(checkpoint_uids)) != len(checkpoint_uids):
            raise HistoryError("Checkpoint Reference requires distinct checkpoints.")
        return tuple(self.checkpoint(uid) for uid in checkpoint_uids)

    def after(self, anchor_uid: str) -> tuple[HistoryCheckpoint, ...]:
        """Return the retained same-Context sequence from one anchor onward."""

        self.checkpoint(anchor_uid)
        ordered = self.timeline.checkpoints
        anchor_index = next(
            index for index, checkpoint in enumerate(ordered) if checkpoint.uid == anchor_uid
        )
        return ordered[anchor_index:]

    def transitions(self, checkpoint_uid: str) -> tuple[MemoryTransition, ...]:
        """Return every mechanical transition evidenced by one checkpoint."""

        self.checkpoint(checkpoint_uid)
        return tuple(
            transition
            for transition in self.timeline.transitions
            if transition.checkpoint_uid == checkpoint_uid
        )

    def revision(self, checkpoint_uid: str) -> CheckpointHistoryRevision:
        """Return the full direct-item revision used by Diff and Revert review."""

        checkpoint = self.checkpoint(checkpoint_uid)
        record = self._records_by_uid[checkpoint_uid]
        after = record.get("snapshot")
        if not isinstance(after, Mapping):
            raise HistoryError("Checkpoint has no complete Context snapshot.")
        return CheckpointHistoryRevision(
            checkpoint=checkpoint,
            record=record,
            before_snapshot=self._before_by_uid[checkpoint_uid],
            after_snapshot=after,
        )


def build_checkpoint_history_slice(
    source: HistoryEvidenceSource,
    context_name: str,
) -> CheckpointHistorySlice:
    """Read each raw input once before producing any checkpoint projection."""

    try:
        current = source.load_direct(context_name)
        physical = source.list_checkpoints(context_name)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        raise HistoryError(str(error)) from error
    # Detach the evidence from Store-owned dictionaries before any projection
    # keeps it beyond this application call.
    physical_frozen = copy.deepcopy(physical)
    entries, physical_uids = flatten_checkpoint_entries(physical_frozen)
    timeline = reconstruct_checkpoint_timeline(current, physical_frozen)
    selectable = tuple(
        sorted(
            (
                entry
                for entry in entries
                if entry["uid"] in physical_uids
            ),
            key=lambda entry: (entry["timestamp"], entry["uid"]),
            reverse=True,
        )
    )
    return CheckpointHistorySlice(
        timeline=timeline,
        entries=tuple(entries),
        physical_entries=selectable,
    )


__all__ = [
    "CheckpointHistoryRevision",
    "CheckpointHistorySlice",
    "build_checkpoint_history_slice",
]
