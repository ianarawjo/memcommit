"""Derive common Memory-history events from verified retained records.

Operation-specific records and adjacent snapshot differences are projected
into one event vocabulary without erasing whether a relation was recorded,
reconstructed, inferred, or left unrecorded.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Any, Literal
import uuid

from memcommit.core.context import Context
from memcommit.application.capabilities.retained_history.memory_lineage import memory_content_sha256
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.application.capabilities.retained_history.temporal import direct_memory_deltas
from memcommit.application.operations.translate.runtime import TRANSLATION_TARGET_CHAR_LIMIT
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryHistoryChildEvidence,
    MemoryHistoryCommandContext,
    MemoryHistoryCommandOperation,
    MemoryHistoryContextTransition,
    MemoryHistoryEvidence,
    MemoryState,
    SourceOccurrence,
    TRACE_METADATA_LEGACY_SCHEMA_VERSION,
    TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION,
    TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
    TRACE_METADATA_SCHEMA_VERSION,
    _Frame,
    _RecordedBranchTransition,
    _atomize_evidence,
    _atomize_save_as_source_frame,
    _checkpoint_chunk_options,
    _checkpoint_entries,
    _checkpoint_fields,
    _empty_frame,
    _frame_equal,
    _frame_from_context,
    _frame_from_snapshot,
    _history_change_matches_snapshot,
    _meld_change_evidence,
    _ordered_states,
    _recorded_branch_transition,
    _replay_checkpoint_chunk,
    _source_occurrences,
)


MemoryHistoryEventKind = Literal[
    "CREATED",
    "EDITED",
    "REMOVED",
    "SPLIT",
    "ABSORBED",
    "MERGED_IN",
    "RESTORED",
    "TRANSLATED",
    "ATOMIZE_KEEP",
    "ATOMIZE_PRESERVED",
    "MELDED",
    "BRANCHED",
    "REORDERED",
    "HISTORY_GAP",
]


@dataclass(frozen=True)
class MemoryHistoryEvent:
    kind: MemoryHistoryEventKind
    evidence: MemoryHistoryEvidence
    timestamp: str | None
    checkpoint_uid: str | None
    command: str
    description: str
    before: tuple[MemoryState, ...] = ()
    after: tuple[MemoryState, ...] = ()
    reason: str | None = None
    reason_codes: tuple[str, ...] = ()
    source_occurrence: SourceOccurrence | None = None
    operation_id: str | None = None
    command_operation: MemoryHistoryCommandOperation | None = None
    context_transition: MemoryHistoryContextTransition | None = None
    child_evidence: tuple[MemoryHistoryChildEvidence, ...] = ()
    declared_frame: str | None = None
    declared_frame_digest: str | None = None
    uncertainty_reason: str | None = None
    source_review_uid: str | None = None
    source_review_digest: str | None = None
    source_analysis_uid: str | None = None

    @property
    def uids(self) -> set[str]:
        return {state.uid for state in (*self.before, *self.after)}

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "checkpoint_uid": self.checkpoint_uid,
            "command": self.command,
            "description": self.description,
            "before": [state.to_dict() for state in self.before],
            "after": [state.to_dict() for state in self.after],
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "source_occurrence": (
                self.source_occurrence.to_dict()
                if self.source_occurrence is not None
                else None
            ),
            "operation_id": self.operation_id,
            "command_operation": (
                self.command_operation.to_dict()
                if self.command_operation is not None
                else None
            ),
            "context_transition": (
                self.context_transition.to_dict()
                if self.context_transition is not None
                else None
            ),
            "child_evidence": [evidence.to_dict() for evidence in self.child_evidence],
            "declared_frame": self.declared_frame,
            "declared_frame_digest": self.declared_frame_digest,
            "uncertainty_reason": self.uncertainty_reason,
            "source_review_uid": self.source_review_uid,
            "source_review_digest": self.source_review_digest,
            "source_analysis_uid": self.source_analysis_uid,
        }


def _legacy_chunk_event(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
) -> MemoryHistoryEvent | None:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    if command != "chunk":
        return None
    source_uid = args.get("uid")
    method = args.get("method")
    if (
        not isinstance(source_uid, str)
        or source_uid not in before.memories
        or removed != {source_uid}
        or not added
        or not isinstance(method, str)
    ):
        return None
    options = _checkpoint_chunk_options(args)
    if options is None:
        return None

    children = [after.memories[uid] for uid in after.order if uid in added]
    source_position = before.order.index(source_uid)
    child_positions = [child.position for child in children]
    if child_positions != list(range(source_position, source_position + len(children))):
        return None
    before_without_source = [uid for uid in before.order if uid != source_uid]
    after_without_children = [uid for uid in after.order if uid not in added]
    if before_without_source != after_without_children:
        return None
    try:
        expected_contents = _replay_checkpoint_chunk(
            before.memories[source_uid].content,
            method,
            args,
        )
    except ValueError:
        return None
    if expected_contents != [child.content for child in children]:
        return None

    return MemoryHistoryEvent(
        kind="SPLIT",
        evidence="RECONSTRUCTED",
        timestamp=timestamp,
        checkpoint_uid=checkpoint_uid,
        command=command,
        description=description,
        before=(before.memories[source_uid],),
        after=tuple(children),
        reason=f"Legacy structural split using method '{method}'.",
    )


def _recorded_context_chunk_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
) -> list[MemoryHistoryEvent]:
    """Validate a Context-scoped chunk checkpoint without content guessing."""

    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    records = args.get("splits")
    method = args.get("method")
    if command != "chunk" or not isinstance(records, list) or not records:
        return []
    if not isinstance(method, str):
        return []
    options = _checkpoint_chunk_options(args)
    if options is None:
        return []

    parsed: list[tuple[str, tuple[str, ...]]] = []
    source_uids: set[str] = set()
    chunk_uids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"uid", "chunk_uids"}:
            return []
        source_uid = record.get("uid")
        children = record.get("chunk_uids")
        if (
            not isinstance(source_uid, str)
            or source_uid in source_uids
            or source_uid not in before.memories
            or not isinstance(children, list)
            or len(children) < 2
            or not all(isinstance(uid, str) for uid in children)
            or len(children) != len(set(children))
            or any(uid in chunk_uids for uid in children)
        ):
            return []
        child_uids = tuple(children)
        source_uids.add(source_uid)
        chunk_uids.update(child_uids)
        parsed.append((source_uid, child_uids))

    if removed != source_uids or added != chunk_uids:
        return []
    replacements = dict(parsed)
    expected_after_order: list[str] = []
    for uid in before.order:
        expected_after_order.extend(replacements.get(uid, (uid,)))
    if tuple(expected_after_order) != after.order:
        return []

    events: list[MemoryHistoryEvent] = []
    for source_uid, child_uids in parsed:
        try:
            expected_contents = _replay_checkpoint_chunk(
                before.memories[source_uid].content,
                method,
                args,
            )
        except ValueError:
            return []
        children = tuple(after.memories.get(uid) for uid in child_uids)
        if any(child is None for child in children) or expected_contents != [
            child.content for child in children if child is not None
        ]:
            return []
        events.append(
            MemoryHistoryEvent(
                kind="SPLIT",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[source_uid],),
                after=tuple(child for child in children if child is not None),
                reason=f"Context structural split using method '{method}'.",
            )
        )
    return events


def _translation_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
    changed: set[str],
) -> tuple[list[MemoryHistoryEvent], set[str], set[str], list[str]]:
    """Validate legacy sibling copies or derived-Context replacements."""
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    if command != "translate":
        return [], set(), set(), []

    def valid_digest(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    operation_uid = args.get("operation_uid")
    target_language = args.get("target_language")
    source_context = args.get("source_context")
    destination_context = args.get("destination_context")
    scope = args.get("scope")
    response_digest = args.get("provider_response_sha256")
    records = args.get("translations")
    schema_version = args.get("schema_version")
    required_keys = {
        "schema_version",
        "operation_uid",
        "target_language",
        "source_context",
        "scope",
        "provider_response_sha256",
        "translations",
    }
    if schema_version == 2:
        required_keys.add("destination_context")
    valid = (
        set(args) == required_keys
        and schema_version in {1, 2}
        and isinstance(operation_uid, str)
        and isinstance(target_language, str)
        and bool(target_language.strip())
        # Trace validation must accept the same semantic target that the
        # translation boundary accepted.  A second, shorter limit here would
        # make a valid checkpoint look unrecorded merely because its audience
        # or terminology guidance was descriptive.
        and len(target_language) <= TRANSLATION_TARGET_CHAR_LIMIT
        and all(character.isprintable() for character in target_language)
        and isinstance(source_context, dict)
        and set(source_context) == {"uid", "name", "digest"}
        and isinstance(source_context.get("uid"), str)
        and bool(source_context.get("uid"))
        and isinstance(source_context.get("name"), str)
        and bool(source_context.get("name"))
        and valid_digest(source_context.get("digest"))
        and isinstance(scope, dict)
        and valid_digest(response_digest)
        and isinstance(records, list)
        and bool(records)
        and not changed
    )
    if valid and schema_version == 1:
        valid = (
            source_context.get("uid") == before.context_uid
            and source_context.get("name") == before.context_name
            and source_context.get("digest") == before.record_digest
            and not removed
        )
    elif valid and schema_version == 2:
        normalized_source_record = {
            **before.record,
            "uid": source_context.get("uid"),
            "name": source_context.get("name"),
        }
        valid = (
            isinstance(destination_context, dict)
            and set(destination_context) == {"uid", "name", "baseline_digest"}
            and destination_context.get("uid") == before.context_uid
            and destination_context.get("name") == before.context_name
            and valid_digest(destination_context.get("baseline_digest"))
            and destination_context.get("baseline_digest") == before.record_digest
            and source_context.get("uid") != before.context_uid
            and source_context.get("name") != before.context_name
            and source_context.get("digest")
            == context_record_digest(normalized_source_record)
        )
    try:
        uuid.UUID(operation_uid if isinstance(operation_uid, str) else "")
    except ValueError:
        valid = False

    parsed: list[tuple[str, str]] = []
    if valid:
        for record in records:
            if not isinstance(record, dict) or set(record) != {
                "source_uid",
                "result_uid",
                "source_sha256",
                "result_sha256",
            }:
                valid = False
                break
            source_uid = record.get("source_uid")
            result_uid = record.get("result_uid")
            source_digest = record.get("source_sha256")
            result_digest = record.get("result_sha256")
            common_invalid = (
                not isinstance(source_uid, str)
                or not isinstance(result_uid, str)
                or source_uid == result_uid
                or source_uid not in before.memories
                or result_uid in before.memories
                or result_uid not in after.memories
                or not valid_digest(source_digest)
                or not valid_digest(result_digest)
                or before.memories[source_uid].content_digest != source_digest
                or after.memories[result_uid].content_digest != result_digest
            )
            version_invalid = (
                (
                    source_uid not in after.memories
                    or before.memories[source_uid].content
                    != after.memories[source_uid].content
                )
                if schema_version == 1
                else source_uid in after.memories
            )
            if common_invalid or version_invalid:
                valid = False
                break
            parsed.append((source_uid, result_uid))

    source_uids = [source_uid for source_uid, _ in parsed]
    result_uids = [result_uid for _, result_uid in parsed]
    if valid and (
        len(source_uids) != len(set(source_uids))
        or len(result_uids) != len(set(result_uids))
        or set(source_uids) & set(result_uids)
    ):
        valid = False
    if valid and schema_version == 1:
        after_memories = after.record.get("memories")
        after_order = after.record.get("order")
        before_order = before.record.get("order")
        after_without_results = (
            {
                **after.record,
                "memories": {
                    uid: item
                    for uid, item in after_memories.items()
                    if uid not in set(result_uids)
                },
                "order": [uid for uid in after_order if uid not in set(result_uids)],
            }
            if (
                isinstance(after_memories, dict)
                and isinstance(after_order, list)
                and isinstance(before_order, list)
            )
            else None
        )
        valid = (
            set(result_uids) == added
            and after_without_results == before.record
            and [uid for uid in after.order if uid not in set(result_uids)]
            == list(before.order)
            and all(
                after.order.index(result_uid) == after.order.index(source_uid) + 1
                for source_uid, result_uid in parsed
            )
        )
    elif valid and schema_version == 2:
        before_memories = before.record.get("memories")
        before_order = before.record.get("order")
        after_memories = after.record.get("memories")
        source_to_result = dict(parsed)
        expected_memories = (
            {
                source_to_result.get(uid, uid): (
                    after_memories[source_to_result[uid]]
                    if uid in source_to_result
                    else item
                )
                for uid, item in before_memories.items()
            }
            if (
                isinstance(before_memories, dict)
                and isinstance(before_order, list)
                and isinstance(after_memories, dict)
            )
            else None
        )
        expected_after = (
            {
                **before.record,
                "memories": expected_memories,
                "order": [source_to_result.get(uid, uid) for uid in before_order],
            }
            if expected_memories is not None
            else None
        )
        valid = (
            set(source_uids) == removed
            and set(result_uids) == added
            and expected_after == after.record
        )
    if valid and scope == {"kind": "all"} and source_uids == list(before.order):
        pass
    elif (
        valid
        and isinstance(scope, dict)
        and set(scope) == {"kind", "memory_uid"}
        and scope.get("kind") == "memory"
        and len(source_uids) == 1
        and scope.get("memory_uid") == source_uids[0]
    ):
        pass
    else:
        valid = False

    if not valid:
        return (
            [],
            set(),
            set(),
            [
                f"Checkpoint [{checkpoint_uid[:8]}] has invalid translation "
                "lineage metadata; snapshot differences were used instead."
            ],
        )

    return (
        [
            MemoryHistoryEvent(
                kind="TRANSLATED",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[source_uid],),
                after=(after.memories[result_uid],),
                reason=(
                    f"Created a translated copy in {target_language}."
                    if schema_version == 1
                    else (
                        "Replaced the source occurrence in this derived "
                        f"Context with a translation in {target_language}."
                    )
                ),
                reason_codes=("TRANSLATION",),
                operation_id=operation_uid,
            )
            for source_uid, result_uid in parsed
        ],
        set(source_uids) if schema_version == 2 else set(),
        set(result_uids),
        [],
    )


def _explicit_memory_history_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
) -> tuple[list[MemoryHistoryEvent], set[str], set[str], list[str]]:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    metadata = args.get("trace")
    if metadata is None:
        return [], set(), set(), []
    schema_version = (
        metadata.get("schema_version")
        if isinstance(
            metadata,
            dict,
        )
        else None
    )
    if (
        not isinstance(metadata, dict)
        or isinstance(schema_version, bool)
        or schema_version
        not in {
            TRACE_METADATA_LEGACY_SCHEMA_VERSION,
            TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
            TRACE_METADATA_SCHEMA_VERSION,
            TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION,
        }
        or not isinstance(metadata.get("changes"), list)
    ):
        return (
            [],
            set(),
            set(),
            [
                f"Checkpoint [{checkpoint_uid[:8]}] has invalid trace metadata; "
                "snapshot differences were used instead."
            ],
        )
    operation_id = metadata.get("operation_id")
    if operation_id is not None and not isinstance(operation_id, str):
        operation_id = None

    events: list[MemoryHistoryEvent] = []
    consumed_before: set[str] = set()
    consumed_after: set[str] = set()
    warnings: list[str] = []
    normal_form_absorptions: dict[str, str] = {}
    if schema_version == TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION:
        try:
            from memcommit.application.operations.atomize.domain import AtomizeNormalFormAudit

            normal_form = AtomizeNormalFormAudit.from_dict(metadata.get("normal_form"))
        except (RuntimeError, TypeError, ValueError):
            return (
                [],
                set(),
                set(),
                [
                    f"Checkpoint [{checkpoint_uid[:8]}] has invalid Atomize "
                    "normal-form metadata; snapshot differences were used instead."
                ],
            )
        normal_form_absorptions = dict(normal_form.absorbed_to_survivor)
    for record in metadata["changes"]:
        if not isinstance(record, dict):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] contains an invalid trace change."
            )
            continue
        kind = record.get("kind")
        source_uids = record.get("source_uids")
        result_uids = record.get("result_uids")
        reason = record.get("reason")
        reason_codes = record.get("reason_codes", [])
        if (
            kind not in {"KEEP", "PRESERVE", "SPLIT", "ABSORB"}
            or not isinstance(source_uids, list)
            or not source_uids
            or any(not isinstance(uid, str) or not uid for uid in source_uids)
            or not isinstance(result_uids, list)
            or not result_uids
            or any(not isinstance(uid, str) or not uid for uid in result_uids)
            or (reason is not None and not isinstance(reason, str))
            or not isinstance(reason_codes, list)
            or any(not isinstance(code, str) for code in reason_codes)
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] contains an invalid trace change."
            )
            continue

        effective_result_uids = list(
            dict.fromkeys(normal_form_absorptions.get(uid, uid) for uid in result_uids)
        )
        involved_before = set(source_uids)
        involved_after = set(effective_result_uids)
        normal_form_match = (
            schema_version == TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION
            and len(source_uids) == 1
            and source_uids[0] in before.memories
            and (
                (
                    kind == "SPLIT"
                    and source_uids[0] not in after.memories
                    and bool(effective_result_uids)
                    and set(effective_result_uids) <= set(after.memories)
                )
                or (
                    kind in {"KEEP", "PRESERVE"}
                    and len(effective_result_uids) == 1
                    and effective_result_uids[0] in after.memories
                    and (
                        source_uids[0] == effective_result_uids[0]
                        or source_uids[0] not in after.memories
                    )
                )
            )
        )
        if (
            involved_before & consumed_before
            or (
                schema_version != TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION
                and involved_after & consumed_after
            )
            or not (
                normal_form_match
                or _history_change_matches_snapshot(
                    kind=kind,
                    source_uids=source_uids,
                    result_uids=result_uids,
                    before=before,
                    after=after,
                )
            )
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] trace metadata does not "
                "match its snapshot; snapshot differences were used instead."
            )
            continue

        before_states = tuple(before.memories[uid] for uid in source_uids)
        after_states = tuple(after.memories[uid] for uid in effective_result_uids)

        event_kind: MemoryHistoryEventKind = {
            "KEEP": "ATOMIZE_KEEP",
            "PRESERVE": "ATOMIZE_PRESERVED",
            "SPLIT": "SPLIT",
            "ABSORB": "ABSORBED",
        }[kind]
        if kind in {"KEEP", "PRESERVE"} and result_uids != effective_result_uids:
            event_kind = "ABSORBED"
        child_evidence: tuple[MemoryHistoryChildEvidence, ...] = ()
        review_evidence: dict[str, str] | None = None
        if schema_version in {
            TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
            TRACE_METADATA_SCHEMA_VERSION,
            TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION,
        }:
            parsed_evidence = _atomize_evidence(
                record,
                schema_version=schema_version,
                kind=kind,
                source_uids=source_uids,
                result_uids=result_uids,
                before=before,
                args=args,
            )
            if parsed_evidence is None:
                warnings.append(
                    f"Checkpoint [{checkpoint_uid[:8]}] has invalid reviewed "
                    "atomize evidence; lineage was retained without that "
                    "evidence."
                )
            else:
                child_evidence, review_evidence = parsed_evidence
        events.append(
            MemoryHistoryEvent(
                kind=event_kind,
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=before_states,
                after=after_states,
                reason=reason,
                reason_codes=tuple(reason_codes),
                operation_id=operation_id,
                child_evidence=child_evidence,
                declared_frame=(
                    review_evidence["text"] if review_evidence is not None else None
                ),
                declared_frame_digest=(
                    review_evidence["digest"] if review_evidence is not None else None
                ),
                uncertainty_reason=(
                    review_evidence["uncertainty_reason"]
                    if review_evidence is not None
                    else None
                ),
                source_review_uid=(
                    review_evidence["review_uid"]
                    if review_evidence is not None
                    else None
                ),
                source_review_digest=(
                    review_evidence["response_digest"]
                    if review_evidence is not None
                    else None
                ),
                source_analysis_uid=(
                    review_evidence["source_analysis_uid"]
                    if review_evidence is not None
                    else None
                ),
            )
        )
        consumed_before.update(source_uids)
        consumed_after.update(effective_result_uids)

    return events, consumed_before, consumed_after, warnings


def _command_restore_operation(
    *,
    command: str,
    args: dict[str, Any],
    context_uid: str,
    context_name: str,
) -> MemoryHistoryCommandOperation | None:
    """Validate the operation boundary retained by one Undo/Redo checkpoint.

    A Trace is reconstructed one Context at a time, but the receipt deliberately
    repeats the complete affected-Context membership.  Keeping that boundary on
    every resulting Memory event lets traces from different owners correlate the
    same user action without treating each checkpoint as an independent Undo.
    """
    if command not in {"undo", "redo"}:
        return None
    value = args.get("command_restore")
    if not isinstance(value, dict) or set(value) != {
        "version",
        "receipt_uid",
        "direction",
        "source_unit_uid",
        "source_command",
        "contexts",
    }:
        return None
    receipt_uid = value.get("receipt_uid")
    direction = value.get("direction")
    source_uid = value.get("source_unit_uid")
    source_command = value.get("source_command")
    raw_contexts = value.get("contexts")
    if (
        value.get("version") != 1
        or not isinstance(receipt_uid, str)
        or not receipt_uid
        or direction != command
        or not isinstance(source_uid, str)
        or not source_uid
        or not isinstance(source_command, str)
        or not source_command
        or not isinstance(raw_contexts, list)
        or not raw_contexts
    ):
        return None
    contexts: list[MemoryHistoryCommandContext] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict) or set(raw_context) != {"uid", "name"}:
            return None
        uid = raw_context.get("uid")
        name = raw_context.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None
        contexts.append(MemoryHistoryCommandContext(uid=uid, name=name))
    identities = [(context.uid, context.name) for context in contexts]
    if (
        len(identities) != len(set(identities))
        or (context_uid, context_name) not in identities
    ):
        return None
    return MemoryHistoryCommandOperation(
        uid=receipt_uid,
        command=command,
        contexts=tuple(contexts),
        source_uid=source_uid,
        source_command=source_command,
    )


def _update_command_operation(
    *,
    command: str,
    args: dict[str, Any],
    context_uid: str,
    context_name: str,
) -> MemoryHistoryCommandOperation | None:
    """Recover the shared command unit recorded by a semantic Update."""
    if command != "update":
        return None
    session_uid = args.get("update_session_uid")
    operation_digest = args.get("operation_digest")
    raw_contexts = args.get("command_contexts")
    if (
        not isinstance(session_uid, str)
        or not session_uid
        or not isinstance(operation_digest, str)
        or not operation_digest
        or not isinstance(raw_contexts, list)
        or not raw_contexts
    ):
        return None
    contexts: list[MemoryHistoryCommandContext] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict) or set(raw_context) != {"uid", "name"}:
            return None
        uid = raw_context.get("uid")
        name = raw_context.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None
        contexts.append(MemoryHistoryCommandContext(uid=uid, name=name))
    identities = [(context.uid, context.name) for context in contexts]
    if (
        len(identities) != len(set(identities))
        or (context_uid, context_name) not in identities
    ):
        return None
    return MemoryHistoryCommandOperation(
        uid=f"update:{session_uid}:{operation_digest}",
        command=command,
        contexts=tuple(contexts),
    )


def _transition_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    restoration: MemoryHistoryCommandOperation | bool = False,
) -> tuple[list[MemoryHistoryEvent], list[str]]:
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

    if restoration:
        command_operation = (
            restoration
            if isinstance(restoration, MemoryHistoryCommandOperation)
            else None
        )
        events: list[MemoryHistoryEvent] = []
        affected = removed | added | changed
        if affected:
            events.append(
                MemoryHistoryEvent(
                    kind="RESTORED",
                    evidence="RECORDED",
                    timestamp=timestamp,
                    checkpoint_uid=checkpoint_uid,
                    command=command,
                    description=description,
                    before=_ordered_states(before, affected),
                    after=_ordered_states(after, affected),
                    operation_id=(
                        command_operation.uid if command_operation is not None else None
                    ),
                    command_operation=command_operation,
                )
            )
        return events, []

    trace_before = (
        _atomize_save_as_source_frame(args, after) if command == "atomize" else None
    )
    events, consumed_before, consumed_after, warnings = _explicit_memory_history_events(
        before=trace_before or before,
        after=after,
        entry=entry,
    )
    if trace_before is not None:
        receipt = args["atomize_save_as"]
        source_context = receipt.get("source_context")
        source_name = (
            source_context.get("name") if isinstance(source_context, dict) else None
        )
        events = [
            MemoryHistoryEvent(
                kind="CREATED",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                after=(trace_before.memories[uid],),
                reason=(
                    f"Copied into this Context from '{source_name}' before "
                    "the reviewed Atomize transform."
                    if isinstance(source_name, str)
                    else "Copied into this Context before Atomize."
                ),
                operation_id=(
                    args.get("analysis_uid")
                    if isinstance(args.get("analysis_uid"), str)
                    else None
                ),
            )
            for uid in trace_before.order
        ] + events
    command_operation = _update_command_operation(
        command=command,
        args=args,
        context_uid=after.context_uid,
        context_name=after.context_name,
    )
    if (
        command == "update"
        and any(
            key in args
            for key in (
                "update_session_uid",
                "operation_digest",
                "command_contexts",
            )
        )
        and command_operation is None
    ):
        warnings.append(
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Update command-unit "
            "metadata; its changes cannot be correlated across Contexts."
        )
    removed -= consumed_before
    added -= consumed_after
    changed -= consumed_before | consumed_after

    meld_changes: dict[str, dict[str, Any]] = {}
    if command == "meld":
        meld_changes, meld_error = _meld_change_evidence(
            args=args,
            before=before,
            after=after,
        )
        if meld_error is not None:
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] {meld_error}; "
                "its results were reconstructed from snapshots."
            )

    (
        translation_events,
        translation_sources,
        translation_results,
        translation_warnings,
    ) = _translation_events(
        before=before,
        after=after,
        entry=entry,
        removed=removed,
        added=added,
        changed=changed,
    )
    events.extend(translation_events)
    removed -= translation_sources
    added -= translation_results
    warnings.extend(translation_warnings)

    chunk_event = None
    context_chunk_events = _recorded_context_chunk_events(
        before=before,
        after=after,
        entry=entry,
        removed=removed,
        added=added,
    )
    if context_chunk_events:
        events.extend(context_chunk_events)
        removed -= {
            state.uid for event in context_chunk_events for state in event.before
        }
        added -= {state.uid for event in context_chunk_events for state in event.after}
    else:
        chunk_event = _legacy_chunk_event(
            before=before,
            after=after,
            entry=entry,
            removed=removed,
            added=added,
        )
    if not context_chunk_events and chunk_event is not None:
        events.append(chunk_event)
        removed -= {state.uid for state in chunk_event.before}
        added -= {state.uid for state in chunk_event.after}
    elif not context_chunk_events and command == "chunk" and (removed or added):
        warnings.append(
            f"Checkpoint [{checkpoint_uid[:8]}] is a legacy chunk whose "
            "parent-child mapping could not be reconstructed safely."
        )

    for uid in sorted(changed, key=lambda item: after.memories[item].position):
        meld = meld_changes.get(uid)
        events.append(
            MemoryHistoryEvent(
                kind="EDITED",
                evidence=(
                    "RECORDED"
                    if (command == "edit" or meld is not None)
                    else "RECONSTRUCTED"
                ),
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[uid],),
                after=(after.memories[uid],),
                reason=meld["reason"] if meld is not None else None,
                reason_codes=(
                    ("MELD", "EDIT", meld["disposition"])
                    if meld is not None
                    else ()
                ),
                operation_id=meld["session_uid"] if meld is not None else None,
                declared_frame=(
                    meld["declared_frame"] if meld is not None else None
                ),
                declared_frame_digest=(
                    hashlib.sha256(
                        meld["declared_frame"].encode("utf-8")
                    ).hexdigest()
                    if meld is not None
                    else None
                ),
                uncertainty_reason=(
                    "Edited by an accepted directional Context meld."
                    if meld is not None
                    else None
                ),
                source_review_uid=meld["session_uid"] if meld is not None else None,
                source_review_digest=(
                    meld["change_set_digest"] if meld is not None else None
                ),
            )
        )

    occurrences = (
        _source_occurrences(
            args=args,
            after=after,
            added_uids=added,
        )
        if command == "add"
        else {}
    )
    if command == "add":
        source = args.get("source")
        if isinstance(source, dict):
            raw_text = source.get("raw_text")
            declared_hash = source.get("sha256")
            if not (
                isinstance(raw_text, str)
                and isinstance(declared_hash, str)
                and hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                == declared_hash
            ):
                warnings.append(
                    f"Checkpoint [{checkpoint_uid[:8]}] has an invalid add "
                    "source hash; source occurrence evidence was reconstructed."
                )
        declared_uids = args.get("memory_uids")
        added_in_context_order = [uid for uid in after.order if uid in added]
        if (
            isinstance(declared_uids, list)
            and set(uid for uid in declared_uids if isinstance(uid, str)) == added
            and declared_uids != added_in_context_order
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] records add Memory UIDs "
                "out of Context order; occurrence order was reconstructed."
            )
    source_context = args.get("source_context")
    init_memory_uids = args.get("memory_uids")
    recorded_init_copy = (
        command == "init"
        and isinstance(source_context, dict)
        and isinstance(source_context.get("uid"), str)
        and isinstance(source_context.get("name"), str)
        and isinstance(init_memory_uids, list)
        and all(isinstance(uid, str) for uid in init_memory_uids)
        and len(init_memory_uids) == len(set(init_memory_uids))
        and set(init_memory_uids) == added
    )
    for uid in sorted(added, key=lambda item: after.memories[item].position):
        occurrence, occurrence_evidence = occurrences.get(uid, (None, None))
        meld = meld_changes.get(uid)
        event_kind: MemoryHistoryEventKind = (
            "MERGED_IN"
            if command == "merge"
            else ("MELDED" if meld is not None else "CREATED")
        )
        evidence: MemoryHistoryEvidence
        if meld is not None:
            evidence = "RECORDED"
        elif occurrence_evidence is not None:
            evidence = occurrence_evidence
        elif recorded_init_copy:
            evidence = "RECORDED"
        elif command in {"add", "merge", "integrate"}:
            evidence = "RECONSTRUCTED"
        else:
            evidence = "INFERRED"
        events.append(
            MemoryHistoryEvent(
                kind=event_kind,
                evidence=evidence,
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                after=(after.memories[uid],),
                reason=(
                    meld["reason"]
                    if meld is not None
                    else (
                        "Copied into this Context's source-based initial "
                        f"frame from '{source_context['name']}'."
                        if recorded_init_copy
                        else None
                    )
                ),
                reason_codes=(
                    ("MELD", "ADD", meld["disposition"])
                    if meld is not None and meld["mode"] == "DIRECTIONAL"
                    else ("MELD", meld["disposition"])
                    if meld is not None
                    else ()
                ),
                source_occurrence=occurrence,
                operation_id=meld["session_uid"] if meld is not None else None,
                declared_frame=(
                    meld["declared_frame"] if meld is not None else None
                ),
                declared_frame_digest=(
                    hashlib.sha256(
                        meld["declared_frame"].encode("utf-8")
                    ).hexdigest()
                    if meld is not None
                    else None
                ),
                uncertainty_reason=(
                    (
                        "Added by an accepted directional Context meld."
                        if meld["mode"] == "DIRECTIONAL"
                        else "Created by an accepted symmetric Context meld."
                    )
                    if meld is not None
                    else None
                ),
                source_review_uid=meld["session_uid"] if meld is not None else None,
                source_review_digest=(
                    meld["change_set_digest"] if meld is not None else None
                ),
            )
        )

    for uid in sorted(removed, key=lambda item: before.memories[item].position):
        events.append(
            MemoryHistoryEvent(
                kind="REMOVED",
                evidence=(
                    "RECORDED" if command in {"remove", "clear"} else "RECONSTRUCTED"
                ),
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[uid],),
            )
        )
    if set(before.memories) == set(after.memories) and before.order != after.order:
        moved = {
            uid
            for uid in before.memories
            if before.memories[uid].position != after.memories[uid].position
        }
        if moved:
            events.append(
                MemoryHistoryEvent(
                    kind="REORDERED",
                    evidence="RECONSTRUCTED",
                    timestamp=timestamp,
                    checkpoint_uid=checkpoint_uid,
                    command=command,
                    description=description,
                    before=_ordered_states(before, moved),
                    after=_ordered_states(after, moved),
                    reason="Canonical direct Memory order changed.",
                )
            )
    if command_operation is not None:
        events = [
            replace(
                event,
                operation_id=event.operation_id or command_operation.uid,
                command_operation=command_operation,
            )
            for event in events
        ]
    return events, warnings


def _branch_transition_events(
    *,
    transition: _RecordedBranchTransition,
    before: _Frame,
    after: _Frame,
    entry: dict,
) -> list[MemoryHistoryEvent]:
    """Project stable direct Memories across one recorded Context Branch."""

    checkpoint_uid, timestamp, command, description, _args = _checkpoint_fields(entry)
    source_is_preceding_frame = (
        before.context_uid == transition.source.uid
        and before.context_name == transition.source.name
    )
    context_transition = MemoryHistoryContextTransition(
        source=transition.source,
        target=transition.target,
    )
    events: list[MemoryHistoryEvent] = []
    edge_by_target_uid = {
        edge.target_memory_uid: edge for edge in transition.memory_edges
    }
    for uid in after.order:
        target_state = after.memories[uid]
        edge = edge_by_target_uid.get(uid)
        source_uid = edge.source_memory_uid if edge is not None else uid
        source_state = (
            before.memories.get(source_uid) if source_is_preceding_frame else None
        )
        # Branch preserves content across distinct occurrence identities. If
        # the copied Source had uncheckpointed changes, the target snapshot
        # proves the copied result but the older inherited frame must not be
        # presented as its exact input.
        if source_state is not None and source_state.content == target_state.content:
            retained_source = (source_state,)
        elif edge is not None and edge.source_content_sha256 == memory_content_sha256(
            target_state.content
        ):
            # The Branch receipt is written while the Source record is locked.
            # It therefore proves the copied Source value even when that value
            # had not received its own earlier checkpoint.
            retained_source = (
                MemoryState(
                    uid=edge.source_memory_uid,
                    content=target_state.content,
                    position=target_state.position,
                ),
            )
        else:
            retained_source = ()
        events.append(
            MemoryHistoryEvent(
                kind="BRANCHED",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=retained_source,
                after=(target_state,),
                operation_id=transition.operation_uid,
                command_operation=transition.command_operation,
                context_transition=context_transition,
            )
        )
    return events


def derive_memory_history_events(
    store: MemoryStore,
    ctx: Context,
) -> tuple[list[MemoryHistoryEvent], list[str], list[_Frame]]:
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

    events: list[MemoryHistoryEvent] = []
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
                f"'{frame.context_name}'; the branch creation event was not "
                "recorded."
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
                previous = _empty_frame(frame.context_uid, frame.context_name)

        recorded_branch = recorded_branches.get(entry["uid"])
        if recorded_branch is not None:
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
        transition, transition_warnings = _transition_events(
            before=previous,
            after=frame,
            entry=entry,
            restoration=command_operation or False,
        )
        events.extend(transition)
        warnings.extend(transition_warnings)
        frames.append(frame)
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
            )
            events.extend(restored_events)
            warnings.extend(restored_warnings)
            frames.append(target)
            previous = target

    current = _frame_from_context(ctx)
    if previous is None:
        previous = _empty_frame(ctx.uid, ctx.name)
    if not _frame_equal(previous, current):
        synthetic_entry = {
            "uid": "current-unrecorded",
            "timestamp": "",
            "snapshot": ctx.to_dict(),
            "command": "current",
            "args": {},
            "description": (
                "Current Context differs from the last reconstructable "
                "checkpoint state."
            ),
        }
        gap_events, _ = _transition_events(
            before=previous,
            after=current,
            entry=synthetic_entry,
        )
        affected_before = tuple(state for event in gap_events for state in event.before)
        affected_after = tuple(state for event in gap_events for state in event.after)
        if gap_events:
            events.append(
                MemoryHistoryEvent(
                    kind="HISTORY_GAP",
                    evidence="UNRECORDED",
                    timestamp=None,
                    checkpoint_uid=None,
                    command="current",
                    description=synthetic_entry["description"],
                    before=affected_before,
                    after=affected_after,
                )
            )
            warnings.append(
                "The current Context contains changes that no retained "
                "checkpoint explains."
            )
    frames.append(current)
    return events, warnings, frames
