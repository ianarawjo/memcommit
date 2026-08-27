"""Console projection for saved Atomize Grounding dialogue state."""

from __future__ import annotations

from memcommit.application.operations.atomize.domain import AtomizeAnalysisSession
from memcommit.application.operations.atomize.grounding import AtomizeGroundingSession
from memcommit.application.operations.atomize.workbench import project_atomize_workbench_findings
from memcommit.adapters.console.text import safe_terminal_text


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
                proposal_heading = "REVIEW PROPOSALS"
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
                "Apply the reviewed proposal with:",
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
        lines.append("This dialogue has not changed the Memories.")
    return "\n".join(lines)


__all__ = ["render_grounding_session"]
