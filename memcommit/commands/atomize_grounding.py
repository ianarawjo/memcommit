"""Command-layer orchestration for conversational atomize grounding."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from memcommit.atomize import AtomizeAnalysisSession
from memcommit.atomize_grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingChangeSet,
    AtomizeGroundingError,
    AtomizeGroundingSession,
    atomize_grounding_canonical_digest,
    atomize_grounding_context_digest,
)
from memcommit.atomize_grounding_provider import (
    assess_atomize_grounding_turn,
)
from memcommit.atomize_workbench import (
    AtomizeWorkbenchFinding,
    AtomizeWorkbenchSession,
    atomize_workbench_response_digest,
    project_atomize_workbench_findings,
)
from memcommit.commands.review_shell import (
    safe_terminal_text,
    visible_ordinal_index,
)
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.query_provider import CodexChatGPTProvider
from memcommit.store import MemoryStore


class AtomizeGroundingCommandError(RuntimeError):
    """Safe command failure at the dialogue/application boundary."""


@dataclass(frozen=True)
class GroundingApplyResult:
    """One successful or recovered grounding application."""

    checkpoint_uid: str
    change_count: int
    recovered: bool = False


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
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
            "The atomize analysis disappeared during semantic assessment."
        )
    current_workbench = store.load_atomize_workbench(current_analysis)
    if current_workbench is None:
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
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
    index = visible_ordinal_index(normalized, len(ordered))
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
        raise AtomizeGroundingCommandError(
            "The grounding target is missing or ambiguous. Use its visible "
            "1-based issue number or a unique issue/source uid prefix."
        )
    return matches[0]


def start_grounding(
    *,
    store: MemoryStore,
    ctx: Context,
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
    selector: str,
    comment: str,
    provider_factory: Callable[[], CodexChatGPTProvider],
) -> AtomizeGroundingSession:
    """Start and assess one dialogue without changing the Context."""
    existing = store.load_atomize_grounding_session(ctx.uid)
    if existing is not None and existing.state in {
        "AWAITING_REPLY",
        "READY_TO_APPLY",
    }:
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
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
    assessment = assess_atomize_grounding_turn(
        ctx,
        analysis,
        session,
        provider_factory,
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
    provider_factory: Callable[[], CodexChatGPTProvider],
    revision: str = "EXTEND",
) -> AtomizeGroundingSession:
    """Add a corrective or extending user turn, then reassess once."""
    session = store.load_atomize_grounding_session(ctx.uid)
    if session is None:
        raise AtomizeGroundingCommandError(
            "No atomize grounding dialogue exists for this Context."
        )
    if session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}:
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
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
    assessment = assess_atomize_grounding_turn(
        ctx,
        analysis,
        session,
        provider_factory,
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
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
            "The grounded change set targets one Memory more than once."
        )

    original_order_length = len(ctx.ordered_uids())
    for proposal in proposals:
        existing = ctx.memories.get(proposal.memory_uid)
        if proposal.operation == "EDIT":
            if not isinstance(existing, Memory):
                raise AtomizeGroundingCommandError(
                    f"EDIT target [{proposal.memory_uid[:8]}] is not a direct "
                    "owned Memory."
                )
            if (
                proposal.expected_content_digest
                != _content_digest(existing.content)
            ):
                raise AtomizeGroundingCommandError(
                    f"EDIT target [{proposal.memory_uid[:8]}] changed after "
                    "the grounding proposal."
                )
            if existing.content == proposal.content:
                raise AtomizeGroundingCommandError(
                    f"EDIT target [{proposal.memory_uid[:8]}] is already "
                    "unchanged by the proposal."
                )
        else:
            if existing is not None:
                raise AtomizeGroundingCommandError(
                    f"ADD target [{proposal.memory_uid[:8]}] already exists."
                )
            if (
                proposal.position is not None
                and proposal.position > original_order_length
            ):
                raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
            "The grounding dialogue has no assessed change proposal."
        )
    accepted_items = []
    for proposal in assessment.proposals:
        decision = session.effective_decision(proposal.uid)
        if decision is not None and decision.action == "ACCEPT":
            accepted_items.append(proposal)
    accepted = tuple(accepted_items)
    if not accepted:
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
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
            raise AtomizeGroundingCommandError(
                "The applied grounding receipt no longer matches the current "
                "Context and its recorded checkpoint."
            )
        return GroundingApplyResult(
            checkpoint_uid=session.application.checkpoint_uid,
            change_count=len(session.application.proposal_uids),
            recovered=True,
        )
    if session.state != "READY_TO_APPLY":
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
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
        raise AtomizeGroundingCommandError(
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


def render_grounding_session(
    session: AtomizeGroundingSession,
    analysis: AtomizeAnalysisSession | None = None,
) -> str:
    """Render a stable provider-free snapshot of one saved conversation."""
    finding = None
    if analysis is not None:
        finding = next(
            (
                candidate
                for candidate in project_atomize_workbench_findings(analysis)
                if candidate.uid == session.anchor.issue_uid
            ),
            None,
        )
    lines = [
        (
            "MEM ATOMIZE · GROUNDING · "
            f"{safe_terminal_text(session.bindings.context_name)}"
        ),
        (
            f"Session [{session.uid[:8]}] · {session.state} · "
            f"{session.anchor.kind} · {session.anchor.arity}"
        ),
        "",
        "ANCHOR",
    ]
    if finding is not None:
        lines.append(safe_terminal_text(finding.reason))
    else:
        lines.append(
            f"Issue {safe_terminal_text(session.anchor.issue_uid)} "
            "(saved source analysis is unavailable or stale)"
        )
    lines.append(
        "Sources: "
        + ", ".join(f"[{uid[:8]}]" for uid in session.anchor.source_uids)
    )
    if (
        session.anchor.selected_reading_uid is not None
        or session.anchor.workbench_response
    ):
        lines.extend(["", "SAVED WORKBENCH EVIDENCE"])
        selected = (
            next(
                (
                    reading
                    for reading in finding.readings
                    if reading.uid
                    == session.anchor.selected_reading_uid
                ),
                None,
            )
            if finding is not None
            else None
        )
        if selected is not None:
            lines.append(
                f"[{safe_terminal_text(selected.role)}] "
                f"{safe_terminal_text(selected.label)} — "
                f"{safe_terminal_text(selected.text)}"
            )
        elif session.anchor.selected_reading_uid is not None:
            lines.append(
                "Selected reading — "
                f"{safe_terminal_text(session.anchor.selected_reading_text)}"
            )
        if session.anchor.workbench_response:
            lines.append(
                safe_terminal_text(session.anchor.workbench_response)
            )

    if not session.turns:
        lines.extend(["", "AWAITING COMMENT"])
    for turn in session.turns:
        lines.extend(
            [
                "",
                f"YOU SAID · TURN {turn.sequence + 1} · {turn.revision}",
                safe_terminal_text(turn.comment),
            ]
        )

    assessment = session.current_assessment
    if assessment is not None:
        lines.extend(["", "MEM UNDERSTANDS"])
        if assessment.active_understanding:
            lines.extend(
                f"- {safe_terminal_text(item)}"
                for item in assessment.active_understanding
            )
        else:
            lines.append("(no active proposition is yet supported)")
        lines.extend(
            [
                "",
                f"CURRENT · {assessment.direct.status}",
                safe_terminal_text(assessment.direct.explanation),
            ]
        )
        if assessment.downstream or assessment.follow_ups:
            lines.extend(["", "THEN"])
        for effect in assessment.downstream:
            # Schema v1 can load early sessions that recorded explicit
            # UNCHANGED rows. They are retained as evidence but hidden from
            # the conversational view: listing every unaffected issue obscures
            # the few consequences the reviewer must actually ground.
            if effect.effect == "UNCHANGED":
                continue
            label = {
                "REQUIRES_CHANGE": "REQUIRED CHANGE",
                "NEEDS_CONFIRMATION": "FOLLOW-UP",
                "RESOLVES": "APPEARS RESOLVED",
                "PARTIALLY_RESOLVES": "PARTIAL",
            }[effect.effect]
            lines.append(
                f"[{label}] {safe_terminal_text(effect.issue_uid)} · "
                f"{safe_terminal_text(effect.explanation)}"
            )
        for question in assessment.follow_ups:
            role = (
                "REQUIRED CHANGE"
                if question.kind == "REQUIRED_CHANGE"
                else (
                    "FOLLOW-UP"
                    if question.priority == "REQUIRED"
                    else "HELPFUL CHECK"
                )
            )
            kind = question.kind.replace("_", " ")
            label = role if kind == role else f"{role} · {kind}"
            lines.append(
                f"[{label}] {safe_terminal_text(question.text)}"
            )
            lines.append(
                f"  Why: {safe_terminal_text(question.reason)}"
            )

        if assessment.proposals:
            if session.state == "READY_TO_APPLY":
                proposal_heading = "READY TO CHANGE"
            elif session.state == "APPLIED":
                proposal_heading = "APPLIED CHANGES"
            elif session.state == "KEPT_REVIEW_ONLY":
                proposal_heading = "REVIEW-ONLY PROPOSALS — not applied"
            elif assessment.has_required_follow_up:
                proposal_heading = (
                    "PROVISIONAL CHANGES — blocked by required follow-up"
                )
            else:
                proposal_heading = (
                    "PROVISIONAL CHANGES — continue grounding before "
                    "application"
                )
            lines.extend(
                [
                    "",
                    proposal_heading,
                ]
            )
            for index, proposal in enumerate(
                assessment.proposals,
                start=1,
            ):
                target = (
                    f"[{proposal.memory_uid[:8]}]"
                    if proposal.operation == "EDIT"
                    else "new Memory"
                )
                lines.append(
                    f"{index}. {proposal.necessity} "
                    f"{proposal.operation} {target}"
                )
                lines.append(f"   {safe_terminal_text(proposal.content)}")
                lines.append(
                    f"   Why: {safe_terminal_text(proposal.reason)}"
                )

    lines.append("")
    if session.state == "AWAITING_REPLY":
        lines.append(
            "Continue with: mem atomize --reply \"CONFIRM, CORRECT, OR EXTEND\""
        )
    elif session.state == "READY_TO_APPLY":
        lines.extend(
            [
                "Apply the exact complete proposal with:",
                "  mem atomize --accept-grounding",
                "Or continue discussing with: mem atomize --reply \"...\"",
            ]
        )
    elif session.state == "KEPT_REVIEW_ONLY":
        lines.append(
            "Kept as review evidence. No Memory changes or checkpoint."
        )
    else:
        assert session.application is not None
        lines.append(
            "Applied in one checkpoint "
            f"[{session.application.checkpoint_uid[:8]}]."
        )
    if session.state in {"AWAITING_REPLY", "READY_TO_APPLY"}:
        lines.append(
            "Keep without changing Memories: "
            "mem atomize --keep-review-only"
        )
        lines.append(
            "No Memory changes have been applied and no checkpoint has been "
            "created by this dialogue."
        )
    return "\n".join(lines)
