"""Store, provider, and checkpoint adapters for Atomize Grounding."""
from __future__ import annotations

from contextlib import nullcontext
import hashlib
from dataclasses import dataclass

from memcommit.operations.atomize.domain import AtomizeAnalysisSession
from memcommit.operations.atomize.grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingChangeSet,
    AtomizeGroundingError,
    AtomizeGroundingSession,
    atomize_grounding_canonical_digest,
    atomize_grounding_context_digest,
)
from memcommit.operations.atomize.grounding_provider import (
    assess_atomize_grounding_turn,
)
from memcommit.operations.atomize.grounding_application import (
    AtomizeGroundingApplicationError,
    AtomizeGroundingProviderFactory,
    AtomizeGroundingProviderProgress,
    GroundingAcceptRequest,
    GroundingApplyResult,
    GroundingKeepRequest,
    GroundingReplyRequest,
    GroundingStartRequest,
)
from memcommit.operations.atomize.workbench import (
    AtomizeWorkbenchFinding,
    AtomizeWorkbenchSession,
    atomize_workbench_response_digest,
    project_atomize_workbench_findings,
)
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.store import MemoryStore

def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _analysis_digest(analysis: AtomizeAnalysisSession) -> str:
    return atomize_grounding_canonical_digest(analysis.to_dict())


def _finding_digest(finding: AtomizeWorkbenchFinding) -> str:
    """Bind the complete human-visible issue, not only its selector."""
    return atomize_grounding_canonical_digest(
        {
            "uid": finding.uid,
            "kind": finding.kind,
            "source_uids": list(finding.source_uids),
            "source_order": finding.source_order,
            "priority": finding.priority,
            "classification": finding.classification,
            "reason": finding.reason,
            "question": finding.question,
            "readings": [
                reading.to_dict() for reading in finding.readings
            ],
            "children": [
                {
                    "content": child.content,
                    "source_spans": list(child.source_spans),
                    "frame_spans": list(child.frame_spans),
                }
                for child in finding.children
            ],
        }
    )


def _bindings(
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> AtomizeGroundingBindings:
    # The issue projection is stable across cursor/layout navigation. Response
    # content has its own digest because changing human evidence must stale a
    # dialogue even when the analysis itself is unchanged.
    return AtomizeGroundingBindings(
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=atomize_grounding_context_digest(ctx),
        analysis_uid=analysis.uid,
        analysis_digest=_analysis_digest(analysis),
        workbench_uid=workbench.uid,
        workbench_digest=workbench.issue_digest,
        response_digest=atomize_workbench_response_digest(workbench),
    )


def assert_current_grounding_bindings(
    session: AtomizeGroundingSession,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> None:
    if session.bindings != _bindings(ctx, analysis, workbench):
        raise AtomizeGroundingApplicationError(
            "The atomize grounding session is stale because its Context, "
            "analysis, issue frame, or saved workbench responses changed."
        )
    findings = {
        finding.uid: finding
        for finding in project_atomize_workbench_findings(analysis)
    }
    anchor = findings.get(session.anchor.issue_uid)
    anchor_response = workbench.responses.get(session.anchor.issue_uid)
    selected_reading_uid = (
        anchor_response.selected_choice_uid
        if anchor_response is not None
        else None
    )
    response_text = (
        anchor_response.text if anchor_response is not None else ""
    )
    selected_reading = (
        next(
            (
                reading
                for reading in anchor.readings
                if reading.uid == selected_reading_uid
            ),
            None,
        )
        if anchor is not None and selected_reading_uid is not None
        else None
    )
    if (
        anchor is None
        or anchor.kind != session.anchor.kind
        or anchor.source_uids != session.anchor.source_uids
        or _finding_digest(anchor) != session.anchor.issue_digest
        or selected_reading_uid
        != session.anchor.selected_reading_uid
        or (
            selected_reading.text if selected_reading is not None else ""
        )
        != session.anchor.selected_reading_text
        or response_text != session.anchor.workbench_response
    ):
        raise AtomizeGroundingApplicationError(
            "The issue that anchored this grounding session has changed."
        )


def _assert_persisted_inputs_unchanged(
    store: MemoryStore,
    pending_session: AtomizeGroundingSession,
    *,
    prior_grounding: dict[str, object] | None,
) -> None:
    """Reject a semantic result if any durable input changed during its call."""
    current_ctx = store.load_direct(pending_session.bindings.context_name)
    current_analysis = store.load_atomize_analysis(current_ctx.uid)
    if current_analysis is None:
        raise AtomizeGroundingApplicationError(
            "The atomize analysis disappeared during semantic assessment."
        )
    current_workbench = store.load_atomize_workbench(current_analysis)
    if current_workbench is None:
        raise AtomizeGroundingApplicationError(
            "The atomize workbench disappeared during semantic assessment."
        )
    assert_current_grounding_bindings(
        pending_session,
        current_ctx,
        current_analysis,
        current_workbench,
    )
    current_grounding = store.load_atomize_grounding_session(current_ctx.uid)
    current_snapshot = (
        current_grounding.to_dict()
        if current_grounding is not None
        else None
    )
    if current_snapshot != prior_grounding:
        raise AtomizeGroundingApplicationError(
            "The atomize grounding dialogue changed during semantic "
            "assessment; the stale response was not saved."
        )


def _select_finding(
    selector: str,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> AtomizeWorkbenchFinding:
    normalized = selector.strip()
    findings = project_atomize_workbench_findings(analysis)
    finding_by_uid = {finding.uid: finding for finding in findings}
    ordered = workbench.ordered_issues()
    index = _visible_ordinal_index(normalized, len(ordered))
    if index is not None:
        matches = [finding_by_uid[ordered[index].uid]]
    else:
        matches = [
            finding
            for finding in findings
            if finding.uid.startswith(normalized)
            or any(
                source_uid.startswith(normalized)
                for source_uid in finding.source_uids
            )
        ]
    if not normalized or len(matches) != 1:
        raise AtomizeGroundingApplicationError(
            "The grounding target is missing or ambiguous. Use its visible "
            "1-based issue number or a unique issue/source uid prefix."
        )
    return matches[0]


def _visible_ordinal_index(selector: str, item_count: int) -> int | None:
    """Resolve only canonical visible ordinals; preserve numeric UID prefixes."""

    if not selector.isdecimal():
        return None
    ordinal = int(selector)
    if selector != str(ordinal) or not 1 <= ordinal <= item_count:
        return None
    return ordinal - 1


def _provider_factory_scope(
    progress: AtomizeGroundingProviderProgress | None,
    stage: str,
    provider_factory: AtomizeGroundingProviderFactory,
):
    if progress is None:
        return nullcontext(provider_factory)
    return progress(stage, provider_factory)


def start_grounding(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
    selector: str,
    comment: str,
    provider_factory: AtomizeGroundingProviderFactory,
    provider_progress: AtomizeGroundingProviderProgress | None = None,
) -> AtomizeGroundingSession:
    """Start and assess one dialogue without changing the Context."""
    existing = store.load_atomize_grounding_session(ctx.uid)
    if existing is not None and existing.state in {
        "AWAITING_REPLY",
        "READY_TO_APPLY",
    }:
        raise AtomizeGroundingApplicationError(
            "An atomize grounding dialogue is already open. Reply to it, "
            "apply it, or keep it as review evidence before starting another."
        )
    finding = _select_finding(selector, analysis, workbench)
    response = workbench.responses.get(finding.uid)
    selected_reading_uid = (
        response.selected_choice_uid if response is not None else None
    )
    if (
        selected_reading_uid is not None
        and selected_reading_uid
        not in {reading.uid for reading in finding.readings}
    ):
        raise AtomizeGroundingApplicationError(
            "The selected workbench reading is unavailable for this issue."
        )
    selected_reading = next(
        (
            reading
            for reading in finding.readings
            if reading.uid == selected_reading_uid
        ),
        None,
    )
    prior_grounding = (
        existing.to_dict() if existing is not None else None
    )
    session = AtomizeGroundingSession.create(
        bindings=_bindings(ctx, analysis, workbench),
        anchor=AtomizeGroundingAnchor(
            issue_uid=finding.uid,
            kind=finding.kind,
            arity="UNARY" if len(finding.source_uids) == 1 else "PAIR",
            source_uids=finding.source_uids,
            issue_digest=_finding_digest(finding),
            selected_reading_uid=selected_reading_uid,
            selected_reading_text=(
                selected_reading.text
                if selected_reading is not None
                else ""
            ),
            workbench_response=(
                response.text if response is not None else ""
            ),
        ),
    )
    turn = session.start_turn(comment)
    with _provider_factory_scope(
        provider_progress,
        "grounding selected issue",
        provider_factory,
    ) as progressing_factory:
        assessment = assess_atomize_grounding_turn(
            ctx,
            analysis,
            session,
            progressing_factory,
        )
    _assert_persisted_inputs_unchanged(
        store,
        session,
        prior_grounding=prior_grounding,
    )
    session.record_assessment(turn.uid, assessment)
    store.save_atomize_grounding_session(session)
    return session


def reply_to_grounding(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
    reply: str,
    provider_factory: AtomizeGroundingProviderFactory,
    provider_progress: AtomizeGroundingProviderProgress | None = None,
    revision: str = "EXTEND",
) -> AtomizeGroundingSession:
    """Add a corrective or extending user turn, then reassess once."""
    session = store.load_atomize_grounding_session(ctx.uid)
    if session is None:
        raise AtomizeGroundingApplicationError(
            "No atomize grounding dialogue exists for this Context."
        )
    if session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}:
        raise AtomizeGroundingApplicationError(
            f"The atomize grounding dialogue is already {session.state}."
        )
    assert_current_grounding_bindings(
        session,
        ctx,
        analysis,
        workbench,
    )
    prior_grounding = session.to_dict()
    normalized_revision = revision.strip().upper()
    if normalized_revision not in {
        "CONFIRM",
        "EXTEND",
        "CORRECT",
        "RETRACT",
    }:
        raise AtomizeGroundingApplicationError(
            "Grounding revision must be confirm, extend, correct, or retract."
        )
    revised = (
        (session.current_turn.uid,)
        if normalized_revision in {"CORRECT", "RETRACT"}
        and session.current_turn is not None
        else ()
    )
    turn = session.start_turn(
        reply,
        revision=normalized_revision,  # type: ignore[arg-type]
        revises_turn_uids=revised,
    )
    with _provider_factory_scope(
        provider_progress,
        "reassessing selected issue",
        provider_factory,
    ) as progressing_factory:
        assessment = assess_atomize_grounding_turn(
            ctx,
            analysis,
            session,
            progressing_factory,
        )
    _assert_persisted_inputs_unchanged(
        store,
        session,
        prior_grounding=prior_grounding,
    )
    session.record_assessment(turn.uid, assessment)
    store.save_atomize_grounding_session(session)
    return session


def keep_grounding_review_only(
    *,
    store: MemoryStore,
    context_uid: str,
) -> AtomizeGroundingSession:
    """Close a dialogue as evidence without a Context write or checkpoint."""
    session = store.load_atomize_grounding_session(context_uid)
    if session is None:
        raise AtomizeGroundingApplicationError(
            "No atomize grounding dialogue exists for this Context."
        )
    session.keep_review_only()
    store.save_atomize_grounding_session(session)
    return session


def _apply_change_set(
    ctx: Context,
    change_set: AtomizeGroundingChangeSet,
) -> list[dict[str, object]]:
    """Validate the whole exact batch before mutating the in-memory Context."""
    proposals = change_set.proposals
    targets = [proposal.memory_uid for proposal in proposals]
    if len(set(targets)) != len(targets):
        raise AtomizeGroundingApplicationError(
            "The grounded change set targets one Memory more than once."
        )

    original_order_length = len(ctx.ordered_uids())
    for proposal in proposals:
        existing = ctx.memories.get(proposal.memory_uid)
        if proposal.operation == "EDIT":
            if not isinstance(existing, Memory):
                raise AtomizeGroundingApplicationError(
                    f"EDIT target [{proposal.memory_uid[:8]}] is not a direct "
                    "owned Memory."
                )
            if (
                proposal.expected_content_digest
                != _content_digest(existing.content)
            ):
                raise AtomizeGroundingApplicationError(
                    f"EDIT target [{proposal.memory_uid[:8]}] changed after "
                    "the grounding proposal."
                )
            if existing.content == proposal.content:
                raise AtomizeGroundingApplicationError(
                    f"EDIT target [{proposal.memory_uid[:8]}] is already "
                    "unchanged by the proposal."
                )
        else:
            if existing is not None:
                raise AtomizeGroundingApplicationError(
                    f"ADD target [{proposal.memory_uid[:8]}] already exists."
                )
            if (
                proposal.position is not None
                and proposal.position > original_order_length
            ):
                raise AtomizeGroundingApplicationError(
                    "An ADD proposal has a stale insertion position."
                )

    changes: list[dict[str, object]] = []
    for proposal in proposals:
        if proposal.operation != "EDIT":
            continue
        memory = ctx.memories[proposal.memory_uid]
        assert isinstance(memory, Memory)
        before = memory.content
        memory.content = proposal.content
        changes.append(
            {
                "proposal_uid": proposal.uid,
                "operation": "EDIT",
                "memory_uid": proposal.memory_uid,
                "before_content": before,
                "after_content": proposal.content,
                "reason": proposal.reason,
                "issue_uids": list(proposal.issue_uids),
                "grounded_by_turn_uids": list(
                    proposal.grounded_by_turn_uids
                ),
            }
        )

    positioned = [
        proposal
        for proposal in proposals
        if proposal.operation == "ADD" and proposal.position is not None
    ]
    appended = [
        proposal
        for proposal in proposals
        if proposal.operation == "ADD" and proposal.position is None
    ]
    inserted_positions: list[int] = []
    for proposal in (*positioned, *appended):
        position = proposal.position
        if position is not None:
            offset = sum(
                earlier <= position for earlier in inserted_positions
            )
            actual_position = position + offset
            inserted_positions.append(position)
        else:
            actual_position = None
        ctx.add(
            Memory(uid=proposal.memory_uid, content=proposal.content),
            position=actual_position,
        )
        changes.append(
            {
                "proposal_uid": proposal.uid,
                "operation": "ADD",
                "memory_uid": proposal.memory_uid,
                "before_content": None,
                "after_content": proposal.content,
                "reason": proposal.reason,
                "issue_uids": list(proposal.issue_uids),
                "grounded_by_turn_uids": list(
                    proposal.grounded_by_turn_uids
                ),
            }
        )
    return changes


def _recorded_application_checkpoint(
    store: MemoryStore,
    ctx: Context,
    *,
    change_set: AtomizeGroundingChangeSet,
) -> str | None:
    """Recover a receipt after Context save succeeded but session save failed."""
    current_digest = atomize_grounding_context_digest(ctx)
    for checkpoint in store.list_checkpoints(ctx.name):
        if checkpoint.get("command") != "atomize-grounding":
            continue
        args = checkpoint.get("args")
        grounding = args.get("grounding") if isinstance(args, dict) else None
        if not (
            isinstance(grounding, dict)
            and grounding.get("session_uid") == change_set.session_uid
            and grounding.get("change_set_digest") == change_set.digest
        ):
            continue
        try:
            recorded_change_set = AtomizeGroundingChangeSet.from_dict(
                grounding.get("change_set")
            )
        except (AtomizeGroundingError, TypeError):
            continue
        if recorded_change_set.to_dict() != change_set.to_dict():
            continue
        snapshot = checkpoint.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        try:
            snapshot_ctx = Context.from_dict(snapshot)
        except (KeyError, TypeError):
            continue
        if (
            snapshot_ctx.uid == ctx.uid
            and atomize_grounding_context_digest(snapshot_ctx)
            == current_digest
        ):
            uid = checkpoint.get("uid")
            return uid if isinstance(uid, str) else None
    return None


def _accepted_change_set(
    session: AtomizeGroundingSession,
) -> AtomizeGroundingChangeSet:
    """Reconstruct the exact accepted plan for READY or APPLIED state."""
    turn = session.current_turn
    assessment = session.current_assessment
    if turn is None or assessment is None:
        raise AtomizeGroundingApplicationError(
            "The grounding dialogue has no assessed change proposal."
        )
    accepted_items = []
    for proposal in assessment.proposals:
        decision = session.effective_decision(proposal.uid)
        if decision is not None and decision.action == "ACCEPT":
            accepted_items.append(proposal)
    accepted = tuple(accepted_items)
    if not accepted:
        raise AtomizeGroundingApplicationError(
            "The grounding dialogue has no accepted change proposal."
        )
    return AtomizeGroundingChangeSet.create(
        session_uid=session.uid,
        turn_uid=turn.uid,
        bindings=session.bindings,
        proposals=accepted,
    )


def accept_grounding(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> GroundingApplyResult:
    """Apply the complete ready proposal once, with one checkpoint."""
    session = store.load_atomize_grounding_session(ctx.uid)
    if session is None:
        raise AtomizeGroundingApplicationError(
            "No atomize grounding dialogue exists for this Context."
        )
    if session.state == "APPLIED":
        assert session.application is not None
        applied_change_set = _accepted_change_set(session)
        recorded_checkpoint_uid = _recorded_application_checkpoint(
            store,
            ctx,
            change_set=applied_change_set,
        )
        if recorded_checkpoint_uid != session.application.checkpoint_uid:
            raise AtomizeGroundingApplicationError(
                "The applied grounding receipt no longer matches the current "
                "Context and its recorded checkpoint."
            )
        return GroundingApplyResult(
            checkpoint_uid=session.application.checkpoint_uid,
            change_count=len(session.application.proposal_uids),
            recovered=True,
        )
    if session.state != "READY_TO_APPLY":
        raise AtomizeGroundingApplicationError(
            "The dialogue is not ready to change Memories. Answer its "
            "required follow-up questions first."
        )

    assessment = session.current_assessment
    assert assessment is not None
    for proposal in assessment.proposals:
        if session.effective_decision(proposal.uid) is None:
            session.decide(proposal.uid, "ACCEPT")
    change_set = session.prepare_changes()

    # A previous invocation may have committed the exact Context/checkpoint
    # but failed while saving the small application receipt. The checkpoint is
    # the idempotency authority, so a retry repairs state without applying twice.
    prior_checkpoint_uid = _recorded_application_checkpoint(
        store,
        ctx,
        change_set=change_set,
    )
    if prior_checkpoint_uid is not None:
        session.record_application(
            change_set_digest=change_set.digest,
            checkpoint_uid=prior_checkpoint_uid,
        )
        store.save_atomize_grounding_session(session)
        return GroundingApplyResult(
            checkpoint_uid=prior_checkpoint_uid,
            change_count=len(change_set.proposals),
            recovered=True,
        )

    assert_current_grounding_bindings(
        session,
        ctx,
        analysis,
        workbench,
    )
    # Grounding edits only directly owned Memories and can now retain every
    # reference pointer through the non-resolving load path. Opening child or
    # MemoryRef target content would widen the evidence/privacy boundary
    # without helping this transaction.
    update_ctx = store.load_direct(ctx.name)
    if (
        update_ctx.uid != session.bindings.context_uid
        or atomize_grounding_context_digest(update_ctx)
        != session.bindings.context_digest
    ):
        raise AtomizeGroundingApplicationError(
            "The Context changed immediately before grounding application."
        )
    changes = _apply_change_set(update_ctx, change_set)
    current = session.current_turn
    assert current is not None and current.assessment is not None
    checkpoint = store.save(
        update_ctx,
        AutoCheckpoint(
            command="atomize-grounding",
            args={
                "grounding": {
                    "schema_version": 1,
                    "session_uid": session.uid,
                    "turn_uid": current.uid,
                    "change_set_digest": change_set.digest,
                    "change_set": change_set.to_dict(),
                    "source_analysis_uid": session.bindings.analysis_uid,
                    "source_workbench_uid": session.bindings.workbench_uid,
                    "anchor": session.anchor.to_dict(),
                    "turns": [
                        {
                            **turn.to_dict(),
                            "comment_digest": _content_digest(turn.comment),
                        }
                        for turn in session.turns
                    ],
                    "decisions": [
                        decision.to_dict()
                        for decision in session.decisions
                    ],
                    "active_understanding": list(
                        current.assessment.active_understanding
                    ),
                    "changes": changes,
                }
            },
            description=(
                f"Applied atomize grounding [{session.uid[:8]}]: "
                f"{len(changes)} "
                f"{'change' if len(changes) == 1 else 'changes'}"
            ),
        ),
    )
    if checkpoint is None:
        raise AtomizeGroundingApplicationError(
            "The grounding Context save did not create its required checkpoint."
        )
    session.record_application(
        change_set_digest=change_set.digest,
        checkpoint_uid=checkpoint.uid,
    )
    store.save_atomize_grounding_session(session)
    return GroundingApplyResult(
        checkpoint_uid=checkpoint.uid,
        change_count=len(changes),
    )


@dataclass
class MemoryStoreAtomizeGroundingPort:
    """Run Grounding against durable Store state without a command dependency."""

    store: MemoryStore
    provider_progress: AtomizeGroundingProviderProgress | None = None

    def start(
        self,
        request: GroundingStartRequest,
        *,
        provider_factory: AtomizeGroundingProviderFactory,
    ) -> AtomizeGroundingSession:
        return start_grounding(
            store=self.store,
            ctx=request.context,
            analysis=request.analysis,
            workbench=request.workbench,
            selector=request.selector,
            comment=request.comment,
            provider_factory=provider_factory,
            provider_progress=self.provider_progress,
        )

    def reply(
        self,
        request: GroundingReplyRequest,
        *,
        provider_factory: AtomizeGroundingProviderFactory,
    ) -> AtomizeGroundingSession:
        return reply_to_grounding(
            store=self.store,
            ctx=request.context,
            analysis=request.analysis,
            workbench=request.workbench,
            reply=request.reply,
            revision=request.revision,
            provider_factory=provider_factory,
            provider_progress=self.provider_progress,
        )

    def keep(self, request: GroundingKeepRequest) -> AtomizeGroundingSession:
        return keep_grounding_review_only(
            store=self.store,
            context_uid=request.context_uid,
        )

    def accept(self, request: GroundingAcceptRequest) -> GroundingApplyResult:
        return accept_grounding(
            store=self.store,
            ctx=request.context,
            analysis=request.analysis,
            workbench=request.workbench,
        )


__all__ = [
    "MemoryStoreAtomizeGroundingPort",
    "assert_current_grounding_bindings",
]
