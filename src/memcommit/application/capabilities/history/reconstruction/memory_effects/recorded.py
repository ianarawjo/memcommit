"""Project validated operation evidence into the canonical Memory event vocabulary."""

from __future__ import annotations

from ...model.memory_event import MemoryHistoryEvent, MemoryHistoryEventKind
from ...verification.checkpoint import _checkpoint_fields
from ...verification.frame import _Frame, _ordered_states
from ...verification.model import (
    MemoryHistoryCommandOperation,
    MemoryHistoryContextTransition,
)
from ...verification.validators.atomize import AtomizeChangeEvidence
from ...verification.validators.branch import (
    _RecordedBranchTransition,
    branch_source_states,
)
from ...verification.validators.chunk import ChunkEvidence
from ...verification.validators.translate import TranslationEvidence
from .model import EffectDerivation


def chunk_events(
    evidence: ChunkEvidence, *, before: _Frame, after: _Frame, entry: dict
) -> EffectDerivation:
    checkpoint_uid, timestamp, command, description, _ = _checkpoint_fields(entry)
    events = [
        MemoryHistoryEvent(
            kind="SPLIT",
            evidence="RECORDED" if evidence.recorded else "RECONSTRUCTED",
            timestamp=timestamp,
            checkpoint_uid=checkpoint_uid,
            command=command,
            description=description,
            before=(before.memories[source_uid],),
            after=tuple(after.memories[uid] for uid in children),
            reason=f"{'Context' if evidence.recorded else 'Legacy'} structural split using method '{evidence.method}'.",
        )
        for source_uid, children in evidence.splits
    ]
    return EffectDerivation(
        events,
        {source for source, _ in evidence.splits},
        {uid for _, children in evidence.splits for uid in children},
    )


def translation_events(
    evidence: TranslationEvidence, *, before: _Frame, after: _Frame, entry: dict
) -> EffectDerivation:
    checkpoint_uid, timestamp, command, description, _ = _checkpoint_fields(entry)
    events = [
        MemoryHistoryEvent(
            kind="TRANSLATED",
            evidence="RECORDED",
            timestamp=timestamp,
            checkpoint_uid=checkpoint_uid,
            command=command,
            description=description,
            before=(before.memories[source],),
            after=(after.memories[result],),
            reason=(
                f"Created a translated copy in {evidence.target_language}."
                if evidence.schema_version == 1
                else "Replaced the source occurrence in this derived "
                f"Context with a translation in {evidence.target_language}."
            ),
            reason_codes=("TRANSLATION",),
            operation_id=evidence.operation_uid,
        )
        for source, result in evidence.pairs
    ]
    return EffectDerivation(
        events,
        {source for source, _ in evidence.pairs}
        if evidence.schema_version == 2
        else set(),
        {result for _, result in evidence.pairs},
    )


def atomize_events(
    changes: list[AtomizeChangeEvidence], *, before: _Frame, after: _Frame, entry: dict
) -> EffectDerivation:
    checkpoint_uid, timestamp, command, description, _ = _checkpoint_fields(entry)
    result = EffectDerivation()
    for change in changes:
        event_kind: MemoryHistoryEventKind = {
            "KEEP": "ATOMIZE_KEEP",
            "PRESERVE": "ATOMIZE_PRESERVED",
            "SPLIT": "SPLIT",
            "ABSORB": "ABSORBED",
        }[change.kind]
        if (
            change.kind in {"KEEP", "PRESERVE"}
            and change.result_uids != change.effective_result_uids
        ):
            event_kind = "ABSORBED"
        review_evidence = change.review_evidence
        result.events.append(
            MemoryHistoryEvent(
                kind=event_kind,
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=tuple(before.memories[uid] for uid in change.source_uids),
                after=tuple(
                    after.memories[uid] for uid in change.effective_result_uids
                ),
                reason=change.reason,
                reason_codes=change.reason_codes,
                operation_id=change.operation_id,
                child_evidence=change.child_evidence,
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
        result.consumed_before.update(change.source_uids)
        result.consumed_after.update(change.effective_result_uids)
    return result


def _branch_transition_events(
    *,
    transition: _RecordedBranchTransition,
    before: _Frame,
    after: _Frame,
    entry: dict,
) -> list[MemoryHistoryEvent]:
    """Project stable direct Memories across one recorded Context Branch."""

    checkpoint_uid, timestamp, command, description, _args = _checkpoint_fields(entry)
    context_transition = MemoryHistoryContextTransition(
        source=transition.source,
        target=transition.target,
    )
    events: list[MemoryHistoryEvent] = []
    sources = branch_source_states(transition=transition, before=before, after=after)
    for uid in after.order:
        target_state = after.memories[uid]
        retained_source = sources[uid]
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


def restoration_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    affected: set[str],
    restoration: MemoryHistoryCommandOperation | bool,
) -> list[MemoryHistoryEvent]:
    """Represent the restored frame as one effect of the recorded command."""
    checkpoint_uid, timestamp, command, description, _ = _checkpoint_fields(entry)
    command_operation = (
        restoration if isinstance(restoration, MemoryHistoryCommandOperation) else None
    )
    events: list[MemoryHistoryEvent] = []
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
    return events


def atomize_baseline_events(
    *, trace_before: _Frame, entry: dict
) -> list[MemoryHistoryEvent]:
    """Expose the retained Save As baseline before its reviewed transformation."""
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    receipt = args["atomize_save_as"]
    source_context = receipt.get("source_context")
    source_name = (
        source_context.get("name") if isinstance(source_context, dict) else None
    )
    return [
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
    ]
