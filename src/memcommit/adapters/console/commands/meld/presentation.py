"""CLI and wait-screen presentation for Meld sessions and receipts."""

from __future__ import annotations

import shlex

import typer
from memcommit.adapters.console.terminal.components.command_wait import (
    CommandWaitView,
)
from memcommit.application.operations.meld.model import (
    MELD_CANDIDATE_SCHEMA_VERSION,
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MeldSession,
    meld_accounting,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.adapters.console.commands.meld.sessions import (
    MeldSessionCatalogEntry,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionPickerEntry,
)

from memcommit.adapters.console.commands.meld.errors import MeldCommandError


def _session_command(session: MeldSession) -> str:
    """Return one explicit, portable command prefix for this saved meld."""
    left, right = session.frames
    if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION:
        parts = [
            "mem",
            "meld",
            "--memory",
            left.memories[0].content,
            "--into",
            right.context_name,
        ]
    else:
        parts = ["mem", "meld", left.context_name, right.context_name]
    if left.include_descendants:
        parts.append("--left-descendants")
    if session.mode == "DIRECTIONAL":
        if right.include_descendants:
            parts.append("--right-descendants")
    else:
        if right.include_descendants:
            parts.append("--right-descendants")
        parts.extend(("--to", session.target.context_name))
    return shlex.join(parts)


def _session_route(session: MeldSession) -> str:
    if session.mode == "DIRECTIONAL":
        incoming_label = (
            "INLINE MEMORY"
            if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION
            else session.frames[0].context_name
        )
        return (
            f"INCOMING {incoming_label} → "
            f"BASELINE / TARGET {session.frames[1].context_name}"
        )
    return (
        f"{session.frames[0].context_name} + "
        f"{session.frames[1].context_name} → "
        f"{session.target.context_name}"
    )


def _session_scope(session: MeldSession) -> str:
    left, right = session.frames
    left_label = (
        "SELECTED + ALL DESCENDANTS"
        if left.include_descendants
        else "SELECTED GRAPH ONLY"
    )
    right_label = (
        "SELECTED + ALL DESCENDANTS"
        if right.include_descendants
        else "SELECTED GRAPH ONLY"
    )
    return f"SCOPE · A {left_label} · B {right_label}"


def _single_line(value: str, *, limit: int = 90) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def render_meld_session(
    session: MeldSession,
    *,
    expanded_issue_uid: str | None = None,
) -> str:
    """Render one provider-free snapshot over a saved meld session."""
    lines = [
        f"MEM MELD · {session.mode}",
        _session_route(session),
        _session_scope(session),
    ]
    if session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
        review = session.candidate_review
        if review is None:
            raise MeldCommandError("Meld candidate review is unavailable.")
        lines.extend(
            [
                f"State: {session.state} · Resolve round: {review.round + 1}",
                "",
                "AUDIT-BACKED RESOLUTION",
                f"SOURCE CLAIMS · {len(review.source_claims)}",
                f"AUDIT ITEMS · {len(review.issues)}",
                "UPDATE · one complete candidate post-image per finalized round",
            ]
        )
        return "\n".join(lines)
    if session.relation_analysis_seed is not None:
        lines.append(f"Compare: {session.relation_analysis_seed.analysis.uid[:8]} · IMPORTED")
    lines.append(f"State: {session.state} · Round: {len(session.turns)}")
    assessment = session.current_assessment
    if assessment is None:
        lines.extend(["", "Analysis is pending."])
        return "\n".join(lines)
    accounting = meld_accounting(session)
    lines.extend(
        [
            "",
            "WHAT MEM UNDERSTOOD",
            safe_terminal_text(assessment.overview),
            "",
            (
                f"RELATIONS · {len(assessment.relations)}  "
                f"ISSUES · {len(assessment.issues)}  "
                f"RESULTS · {len(assessment.proposals)}"
            ),
            "",
            "ACCOUNTING",
            (
                f"  Source coverage: {accounting.represented_sources}/"
                f"{accounting.source_memories}"
            ),
            (
                f"  Relation coverage: {accounting.represented_relations}/"
                f"{accounting.primary_relations}"
            ),
            (
                f"  Final Memories: {accounting.final_memories} · "
                f"PRESERVE {accounting.preserve_results} · "
                f"COALESCE {accounting.coalesce_results} · "
                f"SYNTHESIZE {accounting.synthesize_results} · "
                f"USER_ADD {accounting.user_add_results}"
            ),
            (
                f"  Open issues: REQUIRED {accounting.required_issues} · "
                f"HELPFUL {accounting.helpful_issues}"
            ),
            f"  Cross-relation results: {accounting.cross_relation_results}",
        ]
    )
    for index, relation in enumerate(assessment.relations, start=1):
        marker = "?" if relation.status == "UNRESOLVED" else "✓"
        lines.append(
            f"  {marker} R{index}. {relation.kind} · {_single_line(relation.summary)}"
        )
    lines.extend(["", "ISSUES"])
    relation_number = {
        relation.uid: index
        for index, relation in enumerate(assessment.relations, start=1)
    }
    relation_by_uid = {relation.uid: relation for relation in assessment.relations}
    frame_by_uid = {frame.uid: frame for frame in session.frames}
    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in session.frames
        for memory in frame.memories
    }
    if not assessment.issues:
        lines.append("  (none)")
    ordered_issues = sorted(
        assessment.issues,
        key=lambda item: 0 if item.priority == "REQUIRED" else 1,
    )
    for index, issue in enumerate(ordered_issues, start=1):
        expanded = issue.uid == expanded_issue_uid
        pointer = "▾" if expanded else "›"
        issue_title = issue.title
        if issue.priority == "HELPFUL" and len(issue.relation_uids) == 1:
            relation = relation_by_uid[issue.relation_uids[0]]
            issue_title = f"{relation.kind.title()} · {relation.summary}"
        lines.append(
            f"{pointer} {index:>2}. [{issue.priority}] {_single_line(issue_title)}"
        )
        lines.append(f"      WHY · {_single_line(issue.why_it_matters)}")
        for option_index, option in enumerate(issue.options, start=1):
            lines.append(f"      ↳ {option_index}. {_single_line(option.label)}")
            if expanded:
                lines.append(f"         {safe_terminal_text(option.text)}")
        if expanded:
            lines.extend(
                [
                    f"      QUESTION · {safe_terminal_text(issue.question)}",
                    f"      ISSUE UID · {issue.uid}",
                    "      SOURCE MEMORIES",
                ]
            )
            seen_members: set[tuple[str, str]] = set()
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                for member in relation.members:
                    key = (member.frame_uid, member.memory_uid)
                    if key in seen_members:
                        continue
                    seen_members.add(key)
                    frame = frame_by_uid[member.frame_uid]
                    memory = memory_by_key[key]
                    lines.append(
                        "        - "
                        f"[{frame.role}] "
                        f"{safe_terminal_text(frame.context_name)} "
                        f"#{memory.position + 1} [{memory.uid[:8]}] · "
                        f"{safe_terminal_text(memory.content)}"
                    )
            lines.append("      RELATED RELATIONS")
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                lines.append(
                    f"        - R{relation_number[relation_uid]} "
                    f"{relation.kind} · "
                    f"{safe_terminal_text(relation.reason)}"
                )
            affected = [
                proposal
                for proposal in assessment.proposals
                if set(proposal.relation_uids) & set(issue.relation_uids)
            ]
            lines.append("      AFFECTED RESULTS")
            if not affected:
                lines.append("        - unresolved; no target Memory is proposed yet")
            for proposal in affected:
                lines.append(
                    f"        - [{proposal.disposition}] "
                    f"{safe_terminal_text(proposal.content)}"
                )
    lines.extend(
        [
            "",
            (
                "PROPOSED BASELINE CHANGES"
                if session.mode == "DIRECTIONAL"
                else "PROPOSED TARGET MEMORIES"
            ),
        ]
    )
    if not assessment.proposals:
        lines.append(
            (
                "  (no material baseline changes; acceptance records the "
                "resolved zero-change meld)"
                if session.mode == "DIRECTIONAL" and assessment.ready_to_apply
                else "  (none until required issues are grounded)"
            )
        )
    for index, proposal in enumerate(assessment.proposals, start=1):
        marker = "~" if proposal.operation == "EDIT" else "+"
        label = (
            f"{proposal.operation} · {proposal.disposition}"
            if session.mode == "DIRECTIONAL"
            else proposal.disposition
        )
        lines.append(
            f"  {marker} {index:>2}. [{label}] {safe_terminal_text(proposal.content)}"
        )
        if (
            session.mode == "DIRECTIONAL"
            and len(session.frames[1].contexts or ()) > 1
            and proposal.owner_context_name is not None
        ):
            lines.append(
                "       OWNER · " + safe_terminal_text(proposal.owner_context_name)
            )
        lines.append(f"       WHY · {safe_terminal_text(proposal.reason)}")
    if session.state == "AWAITING_REPLY":
        command = _session_command(session)
        lines.extend(
            [
                "",
                f"Resolve one: {command} --issue N --comment TEXT",
                f"Guide all:  {command} --comment TEXT",
                f"Preserve:   {command} --preserve-all",
                f"Defer:      {command} --defer-all",
            ]
        )
    elif session.state == "READY_TO_APPLY":
        lines.extend(
            [
                "",
                (f"Apply exactly this proposal: {_session_command(session)} --accept"),
            ]
        )
    elif session.state == "APPLIED" and session.granted_target is None:
        lines.extend(["", "RECOVERY · mem undo"])
    return "\n".join(lines)


def render_meld_receipt(
    session: MeldSession,
    *,
    recovered: bool = False,
) -> str:
    """Render terminal Meld success without reopening its analysis Viewer."""

    if session.state != "APPLIED" or session.application is None:
        raise MeldCommandError("Meld receipt requires an applied session.")
    assessment = session.current_assessment
    proposals = assessment.proposals if assessment is not None else ()
    additions = sum(item.operation == "ADD" for item in proposals)
    edits = sum(item.operation == "EDIT" for item in proposals)
    removals = sum(item.operation == "REMOVE" for item in proposals)
    if session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
        review = session.candidate_review
        if review is None:
            raise MeldCommandError("Applied Meld candidate review is unavailable.")
        after = {
            item.uid: item.content
            for item in review.candidate.iter_items()
            if hasattr(item, "content")
        }
        before = (
            {}
            if session.mode == "SYMMETRIC"
            else {memory.uid: memory.content for memory in session.frames[1].memories}
        )
        additions = len(set(after) - set(before))
        removals = len(set(before) - set(after))
        edits = sum(
            uid in after and after[uid] != content
            for uid, content in before.items()
        )
    lines = [
        f"MELD APPLIED · {session.mode} · {session.target.context_name}",
        f"EFFECTS · ADD {additions} · EDIT {edits} · REMOVE {removals}",
        f"RESULT MEMORIES · {len(session.application.result_memory_uids)}",
        f"RECEIPT · {session.uid}",
        f"CHECKPOINT · {session.application.checkpoint_uid}",
        f"REVIEW · mem review meld --session {session.uid}",
    ]
    if session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
        assert session.candidate_review is not None
        lines.insert(
            3,
            f"UNRESOLVED · {len(session.candidate_review.forced_audit_keys)}",
        )
    if recovered:
        lines.append(
            "RECOVERY STATUS · prior application recovered; no duplicate write"
        )
    elif session.granted_target is None:
        lines.append("RECOVERY · mem undo")
    else:
        lines.append("RECOVERY · governed by the granted authority owner")
    return "\n".join(lines)


def render_meld_incomplete_receipt(session: MeldSession) -> str:
    """Return saved execution state without echoing the retained report."""

    assessment = session.current_assessment
    issues = assessment.issues if assessment is not None else ()
    required = sum(issue.priority == "REQUIRED" for issue in issues)
    optional = len(issues) - required
    if session.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
        review = session.candidate_review
        if review is None:
            raise MeldCommandError("Meld candidate review is unavailable.")
        required = len(review.issues)
        optional = 0
    state_label = {
        "AWAITING_REPLY": "NEEDS INPUT",
        "READY_TO_APPLY": "READY",
        "KEPT_REVIEW_ONLY": "DEFERRED",
        "PENDING_ANALYSIS": "PENDING",
    }.get(session.state, session.state.replace("_", " "))
    route = _session_route(session)
    return "\n".join(
        [
            f"MELD {state_label} · {session.mode} · {session.target.context_name}",
            f"ROUTE · {route}",
            f"JUDGMENTS · REQUIRED {required} · OPTIONAL {optional}",
            f"SESSION · {session.uid}",
            "SOURCE · UNCHANGED",
            f"IMPACT · mem impact meld --session {session.uid}",
            "RESUME · mem meld --sessions",
        ]
    )


def _meld_wait_view(session: MeldSession) -> CommandWaitView:
    """Restore the last complete Meld report beneath one pending turn.

    A newly started turn intentionally has no assessment, so rendering the
    live object would replace the participant's report with only "pending".
    Reconstruct the immediately preceding durable view for display only and
    keep the submitted turn visibly separate. Initial analysis has no prior
    report and remains on the shared one-line progress contract.
    """

    current = session.current_turn
    if current is None or current.assessment is not None or len(session.turns) <= 1:
        raise ValueError(
            "A Meld wait report requires a submitted turn after a completed assessment."
        )

    prior_turn = session.turns[-2]
    assert prior_turn.assessment is not None
    prior_payload = session.to_dict()
    prior_payload["turns"] = [turn.to_dict() for turn in session.turns[:-1]]
    prior_payload["state"] = (
        "READY_TO_APPLY" if prior_turn.assessment.ready_to_apply else "AWAITING_REPLY"
    )
    prior_session = MeldSession.from_dict(prior_payload)
    pending_lines = [
        render_meld_session(prior_session),
        "",
        "PENDING TURN · SUBMITTED",
        f"SCOPE · {current.scope}",
    ]
    if current.issue_uids:
        pending_lines.append(
            "ISSUES · " + ", ".join(uid[:8] for uid in current.issue_uids)
        )
    if current.comment:
        pending_lines.extend(["", "COMMENT", safe_terminal_text(current.comment)])
    return CommandWaitView(
        title="PREVIOUS MELD REPORT",
        text=_meld_wait_fragments("\n".join(pending_lines)),
    )


def _meld_wait_context_view(session: MeldSession) -> CommandWaitView:
    """Show the exact route, scopes, and submitted turn frozen for analysis."""

    lines = [
        f"MEM MELD · {session.mode} · INPUTS CONFIRMED",
        _session_route(session),
        _session_scope(session),
        "",
        "SOURCE FRAMES",
    ]
    for frame in session.frames:
        scope = (
            "INCLUDE DESCENDANTS" if frame.include_descendants else "THIS CONTEXT ONLY"
        )
        lines.extend(
            [
                f"  {frame.role} · {safe_terminal_text(frame.context_name)}",
                f"    SCOPE · {scope}",
                f"    MEMORIES · {len(frame.memories)}",
            ]
        )
    lines.extend(
        [
            "",
            f"TARGET · {safe_terminal_text(session.target.context_name)}",
            "TARGET · CHANGES APPLY HERE AFTER REVIEW",
        ]
    )
    current = session.current_turn
    if current is not None:
        lines.extend(
            [
                "",
                "SUBMITTED TURN",
                f"  SCOPE · {current.scope}",
            ]
        )
        if current.issue_uids:
            lines.append(
                "  ISSUES · " + ", ".join(uid[:8] for uid in current.issue_uids)
            )
        if current.comment:
            lines.extend(["", "COMMENT", safe_terminal_text(current.comment)])
    return CommandWaitView(
        title="MELD INPUTS",
        text="\n".join(lines),
    )


def _meld_wait_fragments(text: str) -> list[tuple[str, str]]:
    """Retain Meld report semantics on the shared read-only return pane."""

    section_headings = {
        "WHAT MEM UNDERSTOOD",
        "ACCOUNTING",
        "ISSUES",
        "PROPOSED BASELINE CHANGES",
        "PROPOSED TARGET MEMORIES",
        "PENDING TURN · SUBMITTED · NOT YET INCORPORATED",
        "COMMENT",
    }
    lines = text.splitlines()
    fragments: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        style = ""
        if line in section_headings:
            style = "class:section"
        elif line.startswith(("  + ", "  ~ ")):
            # A proposed target/baseline Memory is the only object text on the
            # compact report. Explanations and surrounding chrome stay white.
            style = "class:memory-object"
        fragments.append((style, line + ("\n" if index < len(lines) - 1 else "")))
    return fragments


def _meld_picker_entry(
    entry: MeldSessionCatalogEntry,
) -> SessionPickerEntry:
    """Adapt one target-bound Meld snapshot to the shared session picker."""
    return SessionPickerEntry(
        kind="meld",
        key=entry.key,
        title=entry.title,
        status=entry.status,
        subtitle=entry.subtitle,
        group=entry.group,
        sort_timestamp=entry.modified_timestamp,
        detail=entry.detail,
        reopen_argv=entry.reopen_argv,
    )


def _present_terminal_outcome(
    session: MeldSession,
    *,
    expanded_issue_uid: str | None = None,
) -> None:
    typer.echo(
        render_meld_receipt(session)
        if session.state == "APPLIED"
        else (
            render_meld_session(session, expanded_issue_uid=expanded_issue_uid)
            if expanded_issue_uid is not None
            else render_meld_incomplete_receipt(session)
        )
    )


def present_archived_meld(session: MeldSession) -> None:
    """Present retained terminal history without implying a live resume."""
    if session.state == "APPLIED":
        typer.echo(render_meld_receipt(session))
    else:
        typer.echo(f"MELD DEFERRED · {session.target.context_name}")
        typer.echo(f"SESSION · {session.uid}")
        typer.echo("SOURCE · UNCHANGED")
    typer.secho(
        "Opened retained terminal history; no live work was resumed.",
        fg=typer.colors.CYAN,
    )


def present_resumed_meld(
    session: MeldSession,
    *,
    interactive_ran: bool,
    terminal_session: bool,
    show_deferred_resume: bool,
) -> None:
    """Present a picker resume after its workflow has finished."""
    if show_deferred_resume:
        typer.echo(f"MELD DEFERRED · {session.target.context_name}")
        typer.echo(f"SESSION · {session.uid}")
        typer.echo("SOURCE · UNCHANGED")
        typer.echo("RESUME · mem meld --sessions")
    else:
        _present_terminal_outcome(session)
    if interactive_ran:
        if not terminal_session:
            typer.secho(
                "Interactive Meld view closed; any approved turns remain saved.",
                fg=typer.colors.CYAN,
            )
    else:
        typer.secho(
            "Resumed without calling the semantic provider.",
            fg=typer.colors.CYAN,
        )


def present_started_meld(
    session: MeldSession,
    *,
    directional_prewarm_origin: str | None,
) -> None:
    """Present a newly created Meld and any provider-free analysis origin."""
    if directional_prewarm_origin:
        label = (
            "EXACT PREWARM"
            if directional_prewarm_origin == "EXACT_PREWARM"
            else (
                "EQUIVALENT SCOPE PREWARM"
                if directional_prewarm_origin == "EQUIVALENT_SCOPE_PREWARM"
                else "PROJECTED PREWARM"
            )
        )
        phase = "INITIAL ANALYSIS" if len(session.turns) > 1 else "ANALYSIS"
        typer.echo(f"{phase} · {label} · PROVIDER NOT CALLED")
    _present_terminal_outcome(session)


def present_restarted_meld(
    session: MeldSession,
    *,
    prior_session_uid: str | None,
) -> None:
    """Present a replacement session and retained terminal-history identity."""
    _present_terminal_outcome(session)
    if prior_session_uid is not None:
        typer.echo(f"PRIOR SESSION · {prior_session_uid} · RETAINED TERMINAL HISTORY")


def present_accepted_meld(session: MeldSession, *, recovered: bool) -> None:
    typer.echo(render_meld_receipt(session, recovered=recovered))


def present_deferred_meld(session: MeldSession) -> None:
    typer.echo(render_meld_incomplete_receipt(session))
    typer.secho(
        "Deferred this meld without changing the target.",
        fg=typer.colors.YELLOW,
    )


def present_incomplete_meld(session: MeldSession) -> None:
    typer.echo(render_meld_incomplete_receipt(session))


def present_existing_meld(
    session: MeldSession,
    *,
    expanded_issue_uid: str | None,
    interactive_ran: bool,
) -> None:
    """Present a normal saved-session route after optional TUI execution."""
    _present_terminal_outcome(session, expanded_issue_uid=expanded_issue_uid)
    typer.secho(
        (
            "Meld completed without an opinion-submission turn."
            if interactive_ran and session.state == "APPLIED"
            else (
                "Meld ended without opening a response turn."
                if interactive_ran
                else "Resumed without calling the semantic provider."
            )
        ),
        fg=typer.colors.CYAN,
    )
