"""Reconstruct ordered Memory history across retained checkpoints and current state."""

from __future__ import annotations

from memcommit.core.context import Context

from ..history_evidence_source import HistoryEvidenceSource
from ..model.memory_event import MemoryHistoryRecord
from ..verification.checkpoint import _checkpoint_entries, _checkpoint_fields
from ..verification.frame import (
    _empty_frame,
    _Frame,
    _frame_equal,
    _frame_from_context,
    _frame_from_snapshot,
)
from ..verification.validators.branch import (
    _recorded_branch_transition,
    _RecordedBranchTransition,
)
from ..verification.validators.command_operation import _command_restore_operation
from .memory_effects.derivation import _transition_events
from .memory_effects.recorded import _branch_transition_events


def derive_memory_history_events(
    store: HistoryEvidenceSource,
    ctx: Context,
) -> tuple[list[MemoryHistoryRecord], list[str], list[_Frame]]:
    entries = _checkpoint_entries(store, ctx.name)
    frames_by_checkpoint: dict[str, _Frame] = {}
    for entry in entries:
        frames_by_checkpoint[entry["uid"]] = _frame_from_snapshot(
            entry["snapshot"],
            label=f"Checkpoint [{entry['uid'][:8]}]",
        )

    recorded_branches: dict[str, _RecordedBranchTransition] = {}
    branch_warnings: list[str] = []
    branch_sources_by_target: dict[str, set[str]] = {}
    for entry in entries:
        frame = frames_by_checkpoint[entry["uid"]]
        transition, warning = _recorded_branch_transition(entry=entry, frame=frame)
        if warning is not None:
            branch_warnings.append(warning)
        if transition is None:
            continue
        recorded_branches[entry["uid"]] = transition
        branch_sources_by_target.setdefault(
            transition.target.uid,
            set(),
        ).add(transition.source.uid)

    # A target can inherit a Source that was itself branched. Walk the complete
    # recorded chain so earlier Source checkpoints remain lineage rather than
    # being misreported as separate missing creation events.
    explained_owner_uids = {ctx.uid}
    pending_owner_uids = [ctx.uid]
    while pending_owner_uids:
        target_uid = pending_owner_uids.pop()
        for source_uid in branch_sources_by_target.get(target_uid, ()):
            if source_uid in explained_owner_uids:
                continue
            explained_owner_uids.add(source_uid)
            pending_owner_uids.append(source_uid)

    events: list[MemoryHistoryRecord] = []
    warnings: list[str] = list(branch_warnings)
    frames: list[_Frame] = []
    previous: _Frame | None = None
    warned_inherited_owners: set[tuple[str, str]] = set()
    for entry in entries:
        frame = frames_by_checkpoint[entry["uid"]]
        frame_owner = (frame.context_uid, frame.context_name)
        if frame.context_uid not in explained_owner_uids and (
            frame_owner not in warned_inherited_owners
        ):
            warnings.append(
                f"Checkpoint [{entry['uid'][:8]}] was inherited from "
                f"'{frame.context_name}'; its branch relation is not "
                "available in the supplied records."
            )
            warned_inherited_owners.add(frame_owner)
        if previous is None:
            command_before = entry.get("command_before")
            if isinstance(command_before, dict):
                # The first retained command may replace a Context that was
                # initially saved without its own checkpoint. Its exact
                # command pre-image is still sufficient to validate lineage;
                # treating the frame as empty would erase every removed Source.
                previous = _frame_from_snapshot(
                    command_before,
                    label=f"Checkpoint [{entry['uid'][:8]}] command pre-image",
                )
            else:
                # A first observed snapshot does not prove that its Memories
                # were created here. Init alone declares an empty new Context.
                previous = (
                    _empty_frame(frame.context_uid, frame.context_name)
                    if entry.get("command") == "init" else frame
                )

        recorded_branch = recorded_branches.get(entry["uid"])
        if recorded_branch is not None:
            direct, messages = _transition_events(
                before=_empty_frame(frame.context_uid, frame.context_name),
                after=frame, entry=entry, source=store,
            )
            events.extend(direct)
            warnings.extend(messages)
            events.extend(
                _branch_transition_events(
                    transition=recorded_branch,
                    before=previous,
                    after=frame,
                    entry=entry,
                )
            )
            frames.append(frame)
            previous = frame
            continue

        _, _, command, _, args = _checkpoint_fields(entry)
        command_operation = _command_restore_operation(
            command=command,
            args=args,
            context_uid=frame.context_uid,
            context_name=frame.context_name,
        )
        if (
            command in {"undo", "redo"}
            and args.get("command_restore") is not None
            and command_operation is None
        ):
            warnings.append(
                f"Checkpoint [{entry['uid'][:8]}] has invalid command "
                "restoration metadata; snapshot differences were used instead."
            )
        # A selected command owns its pre-image even if earlier checkpoints
        # are outside the supplied window. Do not attribute intervening changes.
        raw_before = entry.get("command_before")
        command_before = (
            _frame_from_snapshot(raw_before, label=f"Checkpoint [{entry['uid'][:8]}] pre-image")
            if isinstance(raw_before, dict) else previous
        )
        if command == "revert":
            command_before = frame
        transition, transition_warnings = _transition_events(
            before=command_before,
            after=frame,
            entry=entry,
            restoration=command_operation or False,
            source=store,
        )
        events.extend(transition)
        warnings.extend(transition_warnings)
        frames.extend((command_before, frame))
        previous = frame

        if command == "revert":
            target_uid = args.get("target_uid")
            recorded_restoration = entry.get("restored_snapshot")
            target = (
                _frame_from_snapshot(
                    recorded_restoration,
                    label=f"Checkpoint [{entry['uid'][:8]}] restored post-image",
                )
                if isinstance(recorded_restoration, dict)
                else (
                    frames_by_checkpoint.get(target_uid)
                    if isinstance(target_uid, str)
                    else None
                )
            )
            if target is None:
                warnings.append(
                    f"Revert checkpoint [{entry['uid'][:8]}] does not retain "
                    "its target snapshot."
                )
                continue
            restored_events, restored_warnings = _transition_events(
                before=frame,
                after=target,
                entry=entry,
                restoration=True,
                source=store,
            )
            events.extend(restored_events)
            warnings.extend(restored_warnings)
            frames.append(target)
            previous = target

    current = _frame_from_context(ctx)
    if previous is None:
        previous = _empty_frame(ctx.uid, ctx.name)
    if not _frame_equal(previous, current):
        warnings.append(
            "Current Context differs from the last observed checkpoint state; "
            "that comparison is not attributed to a recorded command."
        )
    frames.append(current)
    return events, warnings, frames
