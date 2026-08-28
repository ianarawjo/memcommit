"""Construct target-specific Memory histories from derived events.

This stage selects the requested historical occurrence, follows its connected
lineage across retained Contexts, and returns the immutable history consumed
by Trace, Rationale, and other read-only callers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Iterable, Literal, Sequence

from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryHistoryContextTransition,
    MemoryHistoryReconstructionError,
    MemoryState,
    _Frame,
    _RecordedMergeEdge,
    _RecordedMergeTransition,
    _checkpoint_entries,
    _frame_equal,
    _frame_from_context,
    _frame_from_snapshot,
    _recorded_merge_transition,
)
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.memory_history_event_derivation import (
    MemoryHistoryEvent,
    derive_memory_history_events,
)


@dataclass(frozen=True)
class MemoryHistoryCandidate:
    """One full-UID Memory choice for trace/rationale selection."""

    uid: str
    content: str
    position: int
    status: Literal["CURRENT", "HISTORICAL"]
    # ``None`` is an authority boundary, not a zero: granted READ content may
    # be selectable for Rationale without exposing its owner's retained log.
    change_count: int | None = None


@dataclass(frozen=True)
class MemoryHistoryAnalysisChild:
    content: str
    source_spans: tuple[str, ...]
    frame_spans: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "source_spans": list(self.source_spans),
            "frame_spans": list(self.frame_spans),
        }


@dataclass(frozen=True)
class MemoryHistoryAnalysis:
    """Saved semantic analysis attached to, but not changing, a lineage."""

    kind: str
    status: Literal["CURRENT", "STALE", "APPLIED"]
    analysis_uid: str
    created_at: str
    memory_uid: str
    classification: str
    action: str
    reason: str
    reason_codes: tuple[str, ...]
    children: tuple[MemoryHistoryAnalysisChild, ...]
    lint: tuple[str, ...]
    declared_frame: str | None
    declared_frame_reason: str | None
    source_review_uid: str | None
    source_review_digest: str | None
    source_review_analysis_uid: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "status": self.status,
            "analysis_uid": self.analysis_uid,
            "created_at": self.created_at,
            "memory_uid": self.memory_uid,
            "classification": self.classification,
            "action": self.action,
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "children": [child.to_dict() for child in self.children],
            "lint": list(self.lint),
            "declared_frame": self.declared_frame,
            "declared_frame_reason": self.declared_frame_reason,
            "source_review_uid": self.source_review_uid,
            "source_review_digest": self.source_review_digest,
            "source_review_analysis_uid": self.source_review_analysis_uid,
        }


@dataclass(frozen=True)
class MemoryHistory:
    context_uid: str
    context_name: str
    selected_uid: str
    component_uids: tuple[str, ...]
    originals: tuple[MemoryState, ...]
    current: tuple[MemoryState, ...]
    events: tuple[MemoryHistoryEvent, ...]
    analyses: tuple[MemoryHistoryAnalysis, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "context": {
                "uid": self.context_uid,
                "name": self.context_name,
            },
            "selected_uid": self.selected_uid,
            "component_uids": list(self.component_uids),
            "originals": [state.to_dict() for state in self.originals],
            "current": [state.to_dict() for state in self.current],
            "events": [event.to_dict() for event in self.events],
            "analyses": [analysis.to_dict() for analysis in self.analyses],
            "warnings": list(self.warnings),
        }


def _known_historical_uids(
    events: Iterable[MemoryHistoryEvent],
    frames: Iterable[_Frame],
) -> set[str]:
    """Return the exact UID domain accepted by trace/rationale selectors."""
    known = {uid for frame in frames for uid in frame.memories}
    known.update(
        state.uid for event in events for state in (*event.before, *event.after)
    )
    return known


def _resolve_historical_uid(
    selector: str,
    events: Iterable[MemoryHistoryEvent],
    frames: Iterable[_Frame],
) -> str:
    if not isinstance(selector, str) or not selector:
        raise MemoryHistoryReconstructionError("Memory selector must be non-empty.")
    known = _known_historical_uids(events, frames)
    matches = sorted(uid for uid in known if uid.startswith(selector))
    if not matches:
        raise MemoryHistoryReconstructionError(
            f"No direct Memory with uid starting with '{selector}' exists "
            "in the current or retained history."
        )
    if len(matches) > 1:
        raise MemoryHistoryReconstructionError(
            f"Ambiguous prefix '{selector}' matches {len(matches)} Memories: "
            + ", ".join(uid[:8] for uid in matches)
        )
    return matches[0]


def _lineage_component(
    selected_uid: str, events: Iterable[MemoryHistoryEvent]
) -> set[str]:
    adjacency: dict[str, set[str]] = {}
    for event in events:
        if event.kind not in {
            "SPLIT",
            "ABSORBED",
            "TRANSLATED",
            "BRANCHED",
            "MERGED_IN",
        }:
            continue
        sources = {state.uid for state in event.before}
        results = {state.uid for state in event.after}
        for source in sources:
            adjacency.setdefault(source, set()).update(results)
        for result in results:
            adjacency.setdefault(result, set()).update(sources)
    component = {selected_uid}
    pending = [selected_uid]
    while pending:
        uid = pending.pop()
        for neighbor in adjacency.get(uid, ()):
            if neighbor in component:
                continue
            component.add(neighbor)
            pending.append(neighbor)
    return component


def _original_states(
    component: set[str],
    events: Iterable[MemoryHistoryEvent],
    frames: Iterable[_Frame],
) -> tuple[MemoryState, ...]:
    parented = {
        state.uid
        for event in events
        if event.kind in {"SPLIT", "ABSORBED", "TRANSLATED", "BRANCHED", "MERGED_IN"}
        for state in event.after
        if state.uid not in {item.uid for item in event.before}
    }
    roots = component - parented
    earliest: dict[str, MemoryState] = {}
    for frame in frames:
        for uid in frame.order:
            if uid in roots and uid not in earliest:
                earliest[uid] = frame.memories[uid]
    for event in events:
        if event.kind == "HISTORY_GAP":
            # The uncheckpointed current frame proves only that the state is
            # present now, not that it is the lineage's retained origin.
            continue
        for state in (*event.before, *event.after):
            if state.uid in roots and state.uid not in earliest:
                earliest[state.uid] = state
    return tuple(
        sorted(earliest.values(), key=lambda state: (state.position, state.uid))
    )


def _analysis_attachments(
    store: MemoryStore,
    ctx: Context,
    component: set[str],
    events: Iterable[MemoryHistoryEvent],
) -> tuple[tuple[MemoryHistoryAnalysis, ...], list[str]]:
    from memcommit.application.operations.atomize.domain import atomize_analysis_matches_context

    try:
        session = store.load_atomize_analysis(ctx.uid)
    except ValueError as error:
        return (), [f"Saved atomize analysis could not be read: {error}"]
    if session is None:
        return (), []
    if session.context_uid != ctx.uid or session.context_name != ctx.name:
        return (), []
    current_frame = _frame_from_context(ctx)
    applied = False
    for checkpoint in store.list_checkpoints(ctx.name):
        args = checkpoint.get("args")
        trace = args.get("trace") if isinstance(args, dict) else None
        if not (isinstance(trace, dict) and trace.get("operation_id") == session.uid):
            continue
        try:
            checkpoint_frame = _frame_from_snapshot(
                checkpoint.get("snapshot"),
                label=f"Checkpoint [{checkpoint.get('uid', '')[:8]}]",
            )
        except MemoryHistoryReconstructionError:
            continue
        if (
            checkpoint_frame.context_uid == current_frame.context_uid
            and checkpoint_frame.context_name == current_frame.context_name
            and _frame_equal(checkpoint_frame, current_frame)
        ):
            applied = True
            break
    status: Literal["CURRENT", "STALE", "APPLIED"]
    if applied:
        status = "APPLIED"
    elif atomize_analysis_matches_context(session, ctx):
        status = "CURRENT"
    else:
        status = "STALE"
    declared_frame_by_memory_uid = {
        frame.memory_uid: frame for frame in session.declared_frames
    }
    analyses = tuple(
        MemoryHistoryAnalysis(
            kind="ATOMIZE_PREVIEW",
            status=status,
            analysis_uid=session.uid,
            created_at=session.created_at,
            memory_uid=item.memory_uid,
            classification=item.classification,
            action=item.action,
            reason=item.reason,
            reason_codes=item.reason_codes,
            children=tuple(
                MemoryHistoryAnalysisChild(
                    content=child.content,
                    source_spans=child.source_spans,
                    frame_spans=child.frame_spans,
                )
                for child in item.children
            ),
            lint=item.lint,
            declared_frame=(
                declared_frame_by_memory_uid[item.memory_uid].text
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
            declared_frame_reason=(
                declared_frame_by_memory_uid[item.memory_uid].uncertainty_reason
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
            source_review_uid=session.source_review_uid,
            source_review_digest=session.source_review_digest,
            source_review_analysis_uid=(
                declared_frame_by_memory_uid[item.memory_uid].source_analysis_uid
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
        )
        for item in session.items
        if item.memory_uid in component
    )
    return analyses, []


def _lineage_operation_counts(
    selected_uids: Iterable[str],
    events: Sequence[MemoryHistoryEvent],
) -> dict[str, int]:
    """Count recorded temporal operations for every candidate in one pass."""

    candidates = tuple(dict.fromkeys(selected_uids))
    operations_by_uid: dict[str, set[tuple[str, str]]] = {
        uid: set() for uid in candidates
    }
    adjacency: dict[str, set[str]] = {uid: set() for uid in candidates}
    for event_index, event in enumerate(events):
        if event.kind == "HISTORY_GAP":
            # A gap proves that the current state is not reconstructable from
            # retained history. It is a visible Trace row, but not evidence of
            # one recorded creation or modification. Excluding it directly
            # keeps the count naturally nonnegative instead of subtracting a
            # synthetic row after aggregation.
            continue
        if event.command_operation is not None:
            key = ("command", event.command_operation.uid)
        elif event.operation_id is not None:
            key = ("operation", event.operation_id)
        elif event.checkpoint_uid is not None:
            key = ("checkpoint", event.checkpoint_uid)
        else:
            # Unidentified reconstructed events remain independently visible
            # in the Trace workbench, so they must not collapse by text/time.
            key = ("event", str(event_index))
        event_uids = event.uids
        for uid in event_uids:
            operations_by_uid.setdefault(uid, set()).add(key)
            adjacency.setdefault(uid, set())
        if event.kind in {"SPLIT", "ABSORBED", "TRANSLATED", "BRANCHED"}:
            related = tuple(event_uids)
            for uid in related:
                adjacency[uid].update(
                    candidate for candidate in related if candidate != uid
                )

    counts: dict[str, int] = {}
    visited: set[str] = set()
    for selected_uid in candidates:
        if selected_uid in visited:
            continue
        component = {selected_uid}
        pending = [selected_uid]
        while pending:
            uid = pending.pop()
            for neighbor in adjacency.get(uid, ()):
                if neighbor in component:
                    continue
                component.add(neighbor)
                pending.append(neighbor)
        visited.update(component)
        count = len(
            set().union(*(operations_by_uid.get(uid, set()) for uid in component))
        )
        for uid in component:
            if uid in operations_by_uid:
                counts[uid] = count
    return counts


def collect_memory_history_candidates(
    store: MemoryStore,
    ctx: Context,
) -> tuple[MemoryHistoryCandidate, ...]:
    """List each selectable current or historical direct Memory once.

    Current Memories retain canonical Context order. Historical-only Memories
    use their last retained state, with the most recently observed frame first.
    The UID set intentionally shares the resolver's exact provenance domain so
    opening the picker cannot narrow what an explicit selector can trace.
    """
    events, _, frames = derive_memory_history_events(store, ctx)
    current_frame = frames[-1]
    current_uids = set(current_frame.memories)
    known_uids = _known_historical_uids(events, frames)
    change_counts = _lineage_operation_counts(known_uids, events)
    current = tuple(
        MemoryHistoryCandidate(
            uid=uid,
            content=current_frame.memories[uid].content,
            position=current_frame.memories[uid].position,
            status="CURRENT",
            change_count=change_counts[uid],
        )
        for uid in current_frame.order
    )

    last_frame_state: dict[str, tuple[int, MemoryState]] = {}
    for frame_index, frame in enumerate(frames):
        for uid in frame.order:
            last_frame_state[uid] = (frame_index, frame.memories[uid])

    # Valid explicit metadata normally names states also present in a retained
    # frame. Keep an event fallback so the picker and explicit selector still
    # share one domain when only an event retains the selected UID.
    last_event_state: dict[str, tuple[int, MemoryState]] = {}
    for event_index, event in enumerate(events):
        for state in (*event.before, *event.after):
            last_event_state[state.uid] = (event_index, state)

    historical: list[tuple[int, int, MemoryHistoryCandidate]] = []
    for uid in known_uids - current_uids:
        frame_observation = last_frame_state.get(uid)
        if frame_observation is not None:
            rank, state = frame_observation
            frame_backed = 1
        else:
            # Event-only choices sort after frame-backed history. The event
            # index is retained only as a deterministic tie breaker.
            rank, state = last_event_state[uid]
            frame_backed = 0
        historical.append(
            (
                frame_backed,
                rank,
                MemoryHistoryCandidate(
                    uid=uid,
                    content=state.content,
                    position=state.position,
                    status="HISTORICAL",
                    change_count=change_counts[uid],
                ),
            )
        )
    historical.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2].position,
            item[2].uid,
        )
    )
    return (*current, *(candidate for _, _, candidate in historical))


def _construct_local_memory_history(
    store: MemoryStore,
    ctx: Context,
    selector: str,
) -> MemoryHistory:
    """Reconstruct lineage retained by one exact owner Context."""
    events, warnings, frames = derive_memory_history_events(store, ctx)
    selected_uid = _resolve_historical_uid(selector, events, frames)
    component = _lineage_component(selected_uid, events)
    relevant_events = tuple(event for event in events if event.uids & component)
    current_frame = frames[-1]
    current = tuple(
        current_frame.memories[uid] for uid in current_frame.order if uid in component
    )
    # derive_memory_history_events always appends the live Context as its final frame.  Origins
    # must come from retained checkpoints or recorded/reconstructed events,
    # never solely from that live frame.
    originals = _original_states(component, relevant_events, frames[:-1])
    analyses, analysis_warnings = _analysis_attachments(
        store,
        ctx,
        component,
        relevant_events,
    )
    return MemoryHistory(
        context_uid=ctx.uid,
        context_name=ctx.name,
        selected_uid=selected_uid,
        component_uids=tuple(sorted(component)),
        originals=originals,
        current=current,
        events=relevant_events,
        analyses=analyses,
        warnings=tuple(dict.fromkeys((*warnings, *analysis_warnings))),
    )


def _merge_transition_catalog(
    store: MemoryStore,
) -> tuple[
    tuple[_RecordedMergeTransition, ...],
    dict[tuple[str, str], tuple[str, ...]],
]:
    """Freeze validated local Merge receipts without opening sibling content."""

    transitions: list[_RecordedMergeTransition] = []
    warnings_by_node: dict[tuple[str, str], list[str]] = {}
    seen_checkpoints: set[str] = set()
    for context_name in store.list_context_names():
        try:
            entries = _checkpoint_entries(store, context_name)
        except MemoryHistoryReconstructionError:
            # An unrelated broken history must not make an exact Trace fail.
            continue
        for entry in entries:
            checkpoint_uid = entry.get("uid")
            if (
                not isinstance(checkpoint_uid, str)
                or checkpoint_uid in seen_checkpoints
            ):
                continue
            seen_checkpoints.add(checkpoint_uid)
            transition, warning = _recorded_merge_transition(entry)
            if transition is not None:
                transitions.append(transition)
                continue
            if warning is None:
                continue
            snapshot = entry.get("snapshot")
            context_uid = snapshot.get("uid") if isinstance(snapshot, dict) else None
            after_memories = (
                snapshot.get("memories") if isinstance(snapshot, dict) else None
            )
            command_before = entry.get("command_before")
            before_memories = (
                command_before.get("memories")
                if isinstance(command_before, dict)
                else {}
            )
            if (
                isinstance(context_uid, str)
                and context_uid
                and isinstance(after_memories, dict)
                and isinstance(before_memories, dict)
            ):
                changed_uids = {
                    uid
                    for uid in set(after_memories) | set(before_memories)
                    if isinstance(uid, str)
                    and after_memories.get(uid) != before_memories.get(uid)
                }
                for uid in changed_uids:
                    warnings_by_node.setdefault((context_uid, uid), []).append(warning)
    return (
        tuple(transitions),
        {node: tuple(dict.fromkeys(items)) for node, items in warnings_by_node.items()},
    )


def _context_for_uid(
    store: MemoryStore,
    context_uid: str,
    *,
    hints: Iterable[str],
    cache: dict[str, Context],
) -> Context | None:
    """Resolve a current local owner by identity, tolerating a later rename."""

    cached = cache.get(context_uid)
    if cached is not None:
        return cached
    names = tuple(dict.fromkeys((*hints, *store.list_context_names())))
    for name in names:
        try:
            context = store.load_direct(name)
        except (FileNotFoundError, ValueError):
            continue
        cache.setdefault(context.uid, context)
        if context.uid == context_uid:
            return context
    return None


def _matching_state(
    report: MemoryHistory | None,
    *,
    uid: str,
    content_digest: str,
) -> MemoryState | None:
    if report is None:
        return None
    candidates = (
        *report.current,
        *(
            state
            for event in reversed(report.events)
            for state in (*event.after, *event.before)
        ),
        *report.originals,
    )
    return next(
        (
            state
            for state in candidates
            if state.uid == uid and state.content_digest == content_digest
        ),
        None,
    )


def _merge_transition_event(
    transition: _RecordedMergeTransition,
    mapping: _RecordedMergeEdge,
    *,
    source_report: MemoryHistory | None,
) -> MemoryHistoryEvent | None:
    """Project one exact Merge mapping into the existing Trace event grammar."""

    edge = mapping.edge
    target_after = transition.after.memories[edge.target_memory_uid]
    source_state = _matching_state(
        source_report,
        uid=edge.source_memory_uid,
        content_digest=edge.source_content_sha256,
    )
    if source_state is None and (
        edge.source_content_sha256 == edge.target_content_sha256
    ):
        # A same-value Merge receipt is written while Source and Target are
        # locked, so the target post-image also proves the copied Source value.
        source_state = MemoryState(
            uid=edge.source_memory_uid,
            content=target_after.content,
            position=target_after.position,
        )
    if source_state is None:
        return None
    target_before = transition.before.memories.get(edge.target_memory_uid)
    before = (source_state,) + ((target_before,) if target_before is not None else ())
    return MemoryHistoryEvent(
        kind="MERGED_IN",
        evidence="RECORDED",
        timestamp=transition.timestamp,
        checkpoint_uid=transition.checkpoint_uid,
        command="merge",
        description=transition.description,
        before=before,
        after=(target_after,),
        reason_codes=("MERGE", mapping.disposition),
        context_transition=MemoryHistoryContextTransition(
            source=transition.source,
            target=transition.target,
        ),
    )


def _deduplicated_events(
    events: Iterable[MemoryHistoryEvent],
) -> tuple[MemoryHistoryEvent, ...]:
    distinct: list[MemoryHistoryEvent] = []
    seen: set[str] = set()
    for event in events:
        identity = json.dumps(
            event.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        distinct.append(event)
    indexed = tuple(enumerate(distinct))
    return tuple(
        event
        for _index, event in sorted(
            indexed,
            key=lambda item: (
                item[1].timestamp is None,
                item[1].timestamp or "",
                item[0],
            ),
        )
    )


def reconstruct_memory_history(
    store: MemoryStore,
    ctx: Context,
    selector: str,
) -> MemoryHistory:
    """Reconstruct one Memory's local history and recorded Merge uses."""

    selected = _construct_local_memory_history(store, ctx, selector)
    transitions, merge_warnings = _merge_transition_catalog(store)
    start_warning_key = (ctx.uid, selected.selected_uid)
    if not transitions and start_warning_key not in merge_warnings:
        return selected

    adjacency: dict[
        tuple[str, str],
        set[tuple[str, str]],
    ] = {}
    recorded_mappings: list[
        tuple[
            tuple[str, str],
            tuple[str, str],
            _RecordedMergeTransition,
            _RecordedMergeEdge,
        ]
    ] = []
    for transition in transitions:
        for mapping in transition.edges:
            source_node = mapping.edge.source_node
            target_node = mapping.edge.target_node
            adjacency.setdefault(source_node, set()).add(target_node)
            adjacency.setdefault(target_node, set()).add(source_node)
            recorded_mappings.append((source_node, target_node, transition, mapping))

    start = (ctx.uid, selected.selected_uid)
    nodes = {start}
    pending = [start]
    while pending:
        node = pending.pop()
        for neighbor in adjacency.get(node, ()):
            if neighbor in nodes:
                continue
            nodes.add(neighbor)
            pending.append(neighbor)
    if len(nodes) == 1:
        extra_warnings = merge_warnings.get(start, ())
        return replace(
            selected,
            warnings=tuple(dict.fromkeys((*selected.warnings, *extra_warnings))),
        )

    hints_by_uid: dict[str, list[str]] = {}
    for transition in transitions:
        hints_by_uid.setdefault(transition.source.uid, []).append(
            transition.source.name
        )
        hints_by_uid.setdefault(transition.target.uid, []).append(
            transition.target.name
        )
    context_cache = {ctx.uid: ctx}
    reports: dict[tuple[str, str], MemoryHistory] = {start: selected}
    for context_uid, memory_uid in sorted(nodes):
        node = (context_uid, memory_uid)
        if node in reports:
            continue
        owner = _context_for_uid(
            store,
            context_uid,
            hints=hints_by_uid.get(context_uid, ()),
            cache=context_cache,
        )
        if owner is None:
            continue
        try:
            reports[node] = _construct_local_memory_history(store, owner, memory_uid)
        except MemoryHistoryReconstructionError:
            # The receipt still proves the immediate copied value. Older
            # Source history remains absent rather than being guessed.
            continue

    merge_events: list[MemoryHistoryEvent] = []
    replacement_targets: set[tuple[str, str]] = set()
    for source_node, target_node, transition, mapping in recorded_mappings:
        if source_node not in nodes or target_node not in nodes:
            continue
        event = _merge_transition_event(
            transition,
            mapping,
            source_report=reports.get(source_node),
        )
        if event is None:
            continue
        merge_events.append(event)
        replacement_targets.add(
            (transition.checkpoint_uid, mapping.edge.target_memory_uid)
        )

    local_events = [
        event
        for report in reports.values()
        for event in report.events
        if not (
            event.command == "merge"
            and event.checkpoint_uid is not None
            and any(
                (event.checkpoint_uid, state.uid) in replacement_targets
                for state in (*event.before, *event.after)
            )
        )
    ]
    events = _deduplicated_events((*local_events, *merge_events))
    component = {uid for report in reports.values() for uid in report.component_uids}
    component.update(memory_uid for _context_uid, memory_uid in nodes)
    current_by_uid: dict[str, MemoryState] = {}
    for report in reports.values():
        for state in report.current:
            current_by_uid[state.uid] = state
    current = tuple(
        sorted(current_by_uid.values(), key=lambda state: (state.position, state.uid))
    )
    originals = _original_states(component, events, ())

    analyses: list[MemoryHistoryAnalysis] = []
    analysis_ids: set[tuple[str, str]] = set()
    for report in reports.values():
        for analysis in report.analyses:
            identity = (analysis.kind, analysis.analysis_uid)
            if identity in analysis_ids:
                continue
            analysis_ids.add(identity)
            analyses.append(analysis)
    warnings = tuple(
        dict.fromkeys(
            (
                *(
                    warning
                    for report in reports.values()
                    for warning in report.warnings
                ),
                *(
                    warning
                    for node in nodes
                    for warning in merge_warnings.get(node, ())
                ),
            )
        )
    )
    return MemoryHistory(
        context_uid=selected.context_uid,
        context_name=selected.context_name,
        selected_uid=selected.selected_uid,
        component_uids=tuple(sorted(component)),
        originals=originals,
        current=current,
        events=events,
        analyses=tuple(analyses),
        warnings=warnings,
    )
