"""Join direct command changes to independently verified operation relations."""

from __future__ import annotations

from dataclasses import replace

from ...history_evidence_source import HistoryEvidenceSource
from ...model.memory_event import MemoryHistoryRecord
from ...verification.checkpoint import _checkpoint_fields
from ...verification.frame import _Frame
from ...verification.model import MemoryHistoryCommandOperation
from ...verification.validators.add import verify_add_occurrences
from ...verification.validators.atomize import (
    _atomize_save_as_source_frame,
    verify_atomize_changes,
)
from ...verification.validators.chunk import verify_context_chunk, verify_legacy_chunk
from ...verification.validators.command_operation import _update_command_operation
from ...verification.validators.meld import _meld_change_evidence
from ...verification.validators.merge_record import merge_change_evidence
from ...verification.validators.translate import verify_translation
from ..memory_state_delta import direct_memory_deltas
from ..operation_record_correlation import (
    operation_record_identity,
    OperationRecordCorrelationError,
)
from .annotations import duplicate_relations, relation_annotations, update_annotations
from .recorded import atomize_events, chunk_events, translation_events
from .snapshot import CommandRevision, snapshot_events


def _transition_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    restoration: MemoryHistoryCommandOperation | bool = False,
    source: HistoryEvidenceSource | None = None,
) -> tuple[list[MemoryHistoryRecord], list[str]]:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    deltas = direct_memory_deltas(
        before.memories,
        after.memories,
        before_order=before.order,
        after_order=after.order,
        content=lambda state: state.content,
    )
    removed = {delta.memory_uid for delta in deltas if delta.kind == "REMOVED"}
    added = {delta.memory_uid for delta in deltas if delta.kind == "CREATED"}
    changed = {delta.memory_uid for delta in deltas if delta.kind == "EDITED"}
    warnings: list[str] = []
    relations = []
    command_operation = (
        restoration
        if isinstance(restoration, MemoryHistoryCommandOperation)
        else _update_command_operation(
            command=command,
            args=args,
            context_uid=after.context_uid,
            context_name=after.context_name,
        )
    )
    try:
        operation_id = operation_record_identity(
            checkpoint_uid=checkpoint_uid, command=command, args=args
        )
    except OperationRecordCorrelationError as error:
        warnings.append(str(error))
        operation_id = checkpoint_uid
    if command_operation is not None:
        operation_id = command_operation.uid

    if not restoration:
        trace_before = (
            _atomize_save_as_source_frame(args, after) if command == "atomize" else None
        )
        changes, messages = verify_atomize_changes(
            before=trace_before or before, after=after, entry=entry
        )
        warnings.extend(messages)
        relations.extend(
            atomize_events(
                changes, before=trace_before or before, after=after, entry=entry
            ).relations
        )
        translation, messages = verify_translation(
            before=before,
            after=after,
            entry=entry,
            removed=removed,
            added=added,
            changed=changed,
        )
        warnings.extend(messages)
        if translation is not None:
            relations.extend(
                translation_events(
                    translation, before=before, after=after, entry=entry
                ).relations
            )
        chunk = verify_context_chunk(
            before=before, after=after, entry=entry, removed=removed, added=added
        )
        if chunk is None:
            chunk = verify_legacy_chunk(
                before=before, after=after, entry=entry, removed=removed, added=added
            )
        if command == "chunk" and chunk is None:
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] chunk relations do not match the command snapshots."
            )
        if chunk is not None:
            relations.extend(
                chunk_events(chunk, before=before, after=after, entry=entry).relations
            )
        try:
            relations.extend(
                duplicate_relations(before=before, after=after, entry=entry)
            )
        except (KeyError, TypeError, ValueError) as error:
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] duplicate relation unavailable: {error}"
            )

    relation_operation_ids = {
        relation.operation_id for relation in relations if relation.operation_id
    }
    if len(relation_operation_ids) == 1 and command_operation is None:
        operation_id = next(iter(relation_operation_ids))
    annotations = {uid: {} for uid in removed | added | changed}
    details = relation_annotations(relations)
    for uid in annotations:
        annotations[uid].update(details.get(uid, {}))
    if command == "add":
        occurrences, messages = verify_add_occurrences(
            args=args, after=after, added=added, checkpoint_uid=checkpoint_uid
        )
        warnings.extend(messages)
        for uid, occurrence in occurrences.items():
            annotations[uid]["source_occurrence"] = occurrence
    if command == "init":
        origin = args.get("source_context")
        init_uids = args.get("memory_uids")
        if (
            isinstance(origin, dict)
            and isinstance(origin.get("uid"), str)
            and isinstance(origin.get("name"), str)
            and isinstance(init_uids, list)
            and all(isinstance(uid, str) for uid in init_uids)
            and len(init_uids) == len(set(init_uids))
            and set(init_uids) == added
        ):
            for uid in added:
                annotations[uid]["reason"] = (
                    f"Copied from Context '{origin.get('name', '')}' into the initial frame."
                )
    if command == "meld" or command == "merge" and "merge" in args:
        meld, message = (
            merge_change_evidence(entry)
            if command == "merge"
            else _meld_change_evidence(args=args, before=before, after=after)
        )
        if message is not None:
            warnings.append(f"Checkpoint [{checkpoint_uid[:8]}] {message}.")
        for uid, detail in meld.items():
            if uid in annotations:
                annotations[uid].update(
                    reason=detail["reason"],
                    source_review_uid=detail["operation_uid"],
                    source_review_digest=detail["change_set_digest"],
                )
    if command == "update" and source is not None:
        try:
            details = update_annotations(
                source=source,
                before=before,
                after=after,
                args=args,
                checkpoint_uid=checkpoint_uid,
            )
        except (FileNotFoundError, ValueError) as error:
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] Update details unavailable: {error}"
            )
        else:
            for uid, detail in details.items():
                annotations[uid].update(detail)
    revision = CommandRevision(
        checkpoint_uid,
        timestamp,
        command,
        description,
        before,
        after,
        operation_id,
        command_operation,
    )
    projected = snapshot_events(revision=revision, annotations=annotations)
    relations = [
        replace(
            relation,
            operation_id=relation.operation_id or operation_id,
            command_operation=relation.command_operation or command_operation,
        )
        for relation in relations
    ]
    return [*projected.events, *relations], warnings
