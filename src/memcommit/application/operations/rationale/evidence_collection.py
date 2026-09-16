"""Retained Trace and saved-analysis evidence for Rationale reports."""

from __future__ import annotations

import json
import unicodedata

from memcommit.application.capabilities.history.model.memory_event import (
    MemoryHistoryEvent,
    MemoryHistoryRecord,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
)
from memcommit.application.capabilities.history.verification import MemoryState
from memcommit.application.operations.rationale.model import (
    RATIONALE_FALLBACK_RADIUS,
    RATIONALE_INPUT_CHAR_LIMIT,
    RATIONALE_PROVENANCE_CHAR_LIMIT,
    ContextEvidence,
    RationaleError,
    SavedAnalysis,
    UpdateProposalEvidence,
)
from memcommit.application.operations.review.model import (
    atomize_review_matches_analysis,
    review_matches_context,
)
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore


def _target_state(trace: MemoryHistory) -> MemoryState:
    for state in trace.current:
        if state.uid == trace.selected_uid:
            return state
    for event in reversed(trace.records):
        for state in reversed((*event.after, *event.before)):
            if state.uid == trace.selected_uid:
                return state
    for state in trace.originals:
        if state.uid == trace.selected_uid:
            return state
    raise RationaleError("The selected Memory has no retained content.")


def _origin_events(trace: MemoryHistory) -> tuple[MemoryHistoryEvent, ...]:
    root_uids = {state.uid for state in trace.originals}
    return tuple(
        event
        for event in trace.events
        if event.kind == "ADD" and any(state.uid in root_uids for state in event.after)
    )


def _recorded_reason_events(trace: MemoryHistory) -> tuple[MemoryHistoryRecord, ...]:
    return tuple(event for event in trace.records if event.reason)


def _saved_analysis(
    store: MemoryStore,
    ctx: Context,
    trace: MemoryHistory,
) -> tuple[SavedAnalysis | None, bool, list[str]]:
    warnings: list[str] = []
    try:
        session = store.load_review_session()
    except ValueError as error:
        warnings.append(f"Saved review could not be read: {error}")
        return None, False, warnings
    if session is None:
        return None, False, warnings
    component = set(trace.component_uids)
    item = next(
        (
            candidate
            for candidate in session.items
            if set(candidate.source_uids) & component
        ),
        None,
    )
    if item is None:
        return None, False, warnings
    if session.kind == "atomize":
        try:
            atomize_analysis = store.load_atomize_analysis(ctx.uid)
        except ValueError as error:
            warnings.append(f"Saved atomize analysis could not be read: {error}")
            return None, True, warnings
        matches_current = (
            atomize_analysis is not None
            and atomize_review_matches_analysis(
                session,
                ctx,
                atomize_analysis,
            )
        )
    else:
        matches_current = review_matches_context(session, ctx)
    if (
        session.context_uid != ctx.uid
        or session.context_name != ctx.name
        or not matches_current
    ):
        # Stale semantic text is not repeated because doing so can make an old
        # interpretation look current after any part of its local frame changed.
        return None, True, warnings

    response = session.responses.get(item.uid)
    selected_reading: str | None = None
    response_text = ""
    if response is not None:
        response_text = response.text
        if response.selected_choice_uid is not None:
            selected = next(
                (
                    choice
                    for choice in item.choices
                    if choice.uid == response.selected_choice_uid
                ),
                None,
            )
            selected_reading = selected.text if selected is not None else None
    return (
        SavedAnalysis(
            session_uid=session.uid,
            interpretation=item.interpretation,
            clarification=item.clarification,
            reason=item.reason,
            question=item.question,
            readings=tuple((choice.label, choice.text) for choice in item.choices),
            selected_reading=selected_reading,
            response=response_text,
        ),
        False,
        warnings,
    )


def _proposal_evidence(
    store: MemoryStore,
    ctx: Context,
    trace: MemoryHistory,
) -> tuple[tuple[UpdateProposalEvidence, ...], list[str]]:
    warnings: list[str] = []
    sessions = []
    for label, loader in (
        ("impact", store.load_impact_plan),
        ("active update", store.load_staged_update),
    ):
        try:
            session = loader()
        except ValueError as error:
            warnings.append(f"Saved {label} could not be read: {error}")
            continue
        if session is not None:
            sessions.append(session)

    component = set(trace.component_uids)
    by_key: dict[
        tuple[str, str, str, str],
        UpdateProposalEvidence,
    ] = {}
    for session in sessions:
        for operation in session.operations:
            source_uids = tuple(source.memory_uid for source in operation.source_refs)
            roles: list[str] = []
            if (
                operation.owner_context_uid == ctx.uid
                and operation.memory_uid in component
            ):
                roles.append("TARGET")
            if any(
                source.context_uid == ctx.uid and source.memory_uid in component
                for source in operation.source_refs
            ):
                roles.append("SOURCE")
            for role in roles:
                evidence = UpdateProposalEvidence(
                    session_uid=session.uid,
                    status=session.status,
                    role=role,
                    operation=operation.operation,
                    reason=operation.reason,
                    owner_context_name=operation.owner_context_name,
                    memory_uid=operation.memory_uid,
                    source_memory_uids=source_uids,
                )
                key = (
                    session.uid,
                    role,
                    operation.owner_context_uid,
                    operation.memory_uid,
                )
                # A staged artifact supersedes the same impact artifact in the
                # display, but remains explicitly an unapplied proposal.
                previous = by_key.get(key)
                if previous is None or session.status == "staged":
                    by_key[key] = evidence
    return tuple(by_key.values()), warnings


def _context_candidates(
    contexts: tuple[Context, ...],
    target: MemoryState,
) -> tuple[list[ContextEvidence], bool]:
    memories = [
        (context.name, item)
        for context in contexts
        for item in context.iter_items()
        if isinstance(item, Memory)
    ]
    current_position = next(
        (
            index
            for index, (_context_name, memory) in enumerate(memories)
            if memory.uid == target.uid
        ),
        target.position,
    )
    candidates = [
        ContextEvidence(
            candidate_id=f"m{index + 1:06d}",
            memory=memory,
            context_name=context_name,
            position=index,
            distance=abs(index - current_position),
        )
        for index, (context_name, memory) in enumerate(memories)
        if memory.uid != target.uid
    ]
    payload_size = len(
        json.dumps(
            [
                {
                    "candidate_id": candidate.candidate_id,
                    "context_name": candidate.context_name,
                    "position": candidate.position,
                    "content": candidate.memory.content,
                }
                for candidate in candidates
            ],
            ensure_ascii=False,
        )
    )
    if payload_size <= RATIONALE_INPUT_CHAR_LIMIT:
        return candidates, False

    selected: list[ContextEvidence] = []
    size = 0
    for candidate in sorted(
        candidates,
        key=lambda item: (item.distance, item.position),
    ):
        contribution = len(candidate.memory.content) + 200
        if size + contribution > RATIONALE_INPUT_CHAR_LIMIT // 2:
            continue
        selected.append(candidate)
        size += contribution
    return sorted(selected, key=lambda item: item.position), True


def _fallback_evidence(
    candidates: list[ContextEvidence],
) -> tuple[ContextEvidence, ...]:
    return tuple(
        sorted(
            sorted(
                candidates,
                key=lambda item: (item.distance, item.position),
            )[: RATIONALE_FALLBACK_RADIUS * 2],
            key=lambda item: item.position,
        )
    )


def _normalized_semantic_text(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _semantic_character_count(values: list[str]) -> int:
    """Count unique authored/typed evidence without JSON or UI overhead."""

    unique: set[str] = set()
    total = 0
    for value in values:
        normalized = _normalized_semantic_text(value)
        if not normalized or normalized in unique:
            continue
        unique.add(normalized)
        total += len(normalized)
    return total


def _relative_character_limit(source_count: int, absolute_limit: int) -> int:
    """Keep generated or projected prose strictly smaller than its evidence."""

    if source_count <= 1:
        return 0
    return min(absolute_limit, source_count - 1)


def _provenance_character_budget(trace: MemoryHistory) -> tuple[int, int]:
    if not trace.records:
        # Endpoint content without a retained event is current state, not
        # evidence that can support a provenance claim.
        return 0, 0
    values: list[str] = [trace.context_name, *trace.warnings]
    for event in trace.records:
        values.extend((event.kind, event.command))
        if event.reason is not None:
            values.append(event.reason)
        if event.context_transition is not None:
            values.extend(
                (
                    event.context_transition.source.name,
                    event.context_transition.target.name,
                )
            )
        values.extend(state.content for state in (*event.before, *event.after))
    values.extend(state.content for state in (*trace.originals, *trace.current))
    source_count = _semantic_character_count(values)
    return source_count, _relative_character_limit(
        source_count,
        RATIONALE_PROVENANCE_CHAR_LIMIT,
    )
