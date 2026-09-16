"""Project verified operation records into source/result relations."""

from __future__ import annotations

from ...model.memory_event import MemoryHistoryRelation
from ...verification.checkpoint import _checkpoint_fields
from ...verification.frame import _Frame
from ...verification.model import (
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
        MemoryHistoryRelation(
            kind="DERIVED_FROM",
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
    return EffectDerivation(relations=events)


def translation_events(
    evidence: TranslationEvidence, *, before: _Frame, after: _Frame, entry: dict
) -> EffectDerivation:
    checkpoint_uid, timestamp, command, description, _ = _checkpoint_fields(entry)
    events = [
        MemoryHistoryRelation(
            kind="DERIVED_FROM",
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
    return EffectDerivation(relations=events)


def atomize_events(
    changes: list[AtomizeChangeEvidence], *, before: _Frame, after: _Frame, entry: dict
) -> EffectDerivation:
    checkpoint_uid, timestamp, command, description, _ = _checkpoint_fields(entry)
    result = EffectDerivation()
    for change in changes:
        relation_kind = (
            "CONTINUES_AS"
            if change.source_uids == change.effective_result_uids
            else "DERIVED_FROM"
        )
        review_evidence = change.review_evidence
        result.relations.append(
            MemoryHistoryRelation(
                kind=relation_kind,
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=tuple(before.memories[uid] for uid in change.source_uids),
                after=tuple(
                    after.memories[uid] for uid in change.effective_result_uids
                ),
                reason=change.reason,
                reason_codes=(change.kind, *change.reason_codes),
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
    return result


def _branch_transition_events(
    *,
    transition: _RecordedBranchTransition,
    before: _Frame,
    after: _Frame,
    entry: dict,
) -> list[MemoryHistoryRelation]:
    """Project stable direct Memories across one recorded Context Branch."""

    checkpoint_uid, timestamp, command, description, _args = _checkpoint_fields(entry)
    context_transition = MemoryHistoryContextTransition(
        source=transition.source,
        target=transition.target,
    )
    events: list[MemoryHistoryRelation] = []
    sources = branch_source_states(transition=transition, before=before, after=after)
    for uid in after.order:
        target_state = after.memories[uid]
        retained_source = sources[uid]
        events.append(
            MemoryHistoryRelation(
                kind="DERIVED_FROM",
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
