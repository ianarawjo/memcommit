"""CLI and wait-screen presentation for Merge sessions and receipts."""

from __future__ import annotations

import shlex

import typer
from memcommit.application.operations.merge.semantic.model import (
    INLINE_MELD_CONTEXT_NAME,
    MeldSession,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.adapters.console.commands.merge.semantic.sessions import (
    MeldSessionCatalogEntry,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionPickerEntry,
)

from memcommit.adapters.console.commands.merge.semantic.errors import MeldCommandError


def _session_command(session: MeldSession) -> str:
    """Return one explicit, portable command prefix for this saved meld."""
    left, right = session.frames
    if session.frames[0].context_name == INLINE_MELD_CONTEXT_NAME:
        parts = [
            "mem",
            "merge",
            "--memory",
            left.memories[0].content,
            "--into",
            right.context_name,
        ]
    else:
        parts = ["mem", "merge", left.context_name, right.context_name]
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
            if session.frames[0].context_name == INLINE_MELD_CONTEXT_NAME
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
        f"MEM MERGE · {session.mode}",
        _session_route(session),
        _session_scope(session),
    ]
    review = session.candidate_review
    if review is None:
        raise MeldCommandError("Merge candidate review is unavailable.")
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


def render_meld_receipt(
    session: MeldSession,
    *,
    recovered: bool = False,
) -> str:
    """Render terminal Merge success without reopening its analysis Viewer."""

    if session.state != "APPLIED" or session.application is None:
        raise MeldCommandError("Merge receipt requires an applied session.")
    review = session.candidate_review
    if review is None:
        raise MeldCommandError("Applied Merge candidate review is unavailable.")
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
        uid in after and after[uid] != content for uid, content in before.items()
    )
    lines = [
        f"MERGE APPLIED · {session.mode} · {session.target.context_name}",
        f"EFFECTS · ADD {additions} · EDIT {edits} · REMOVE {removals}",
        f"RESULT MEMORIES · {len(session.application.result_memory_uids)}",
        f"RECEIPT · {session.uid}",
        f"CHECKPOINT · {session.application.checkpoint_uid}",
        f"REVIEW · mem review merge --session {session.uid}",
    ]
    assert session.candidate_review is not None
    lines.insert(
        3,
        f"UNRESOLVED · {len(session.candidate_review.forced_audit_keys)}",
    )
    if recovered:
        lines.append(
            "RECOVERY STATUS · prior application recovered; no duplicate write"
        )
    else:
        lines.append("RECOVERY · mem undo")
    return "\n".join(lines)


def render_meld_incomplete_receipt(session: MeldSession) -> str:
    """Return saved execution state without echoing the retained report."""

    review = session.candidate_review
    if review is None:
        raise MeldCommandError("Merge candidate review is unavailable.")
    required = len(review.issues)
    optional = 0
    state_label = {
        "AWAITING_REPLY": "NEEDS INPUT",
        "UNDONE": "UNDONE",
        "PENDING_ANALYSIS": "PENDING",
    }.get(session.state, session.state.replace("_", " "))
    route = _session_route(session)
    return "\n".join(
        [
            f"MERGE {state_label} · {session.mode} · {session.target.context_name}",
            f"ROUTE · {route}",
            f"JUDGMENTS · REQUIRED {required} · OPTIONAL {optional}",
            f"SESSION · {session.uid}",
            "SOURCE · UNCHANGED",
            f"IMPACT · mem impact merge --session {session.uid}",
            "RESUME · mem merge --sessions",
        ]
    )


def _meld_picker_entry(
    entry: MeldSessionCatalogEntry,
) -> SessionPickerEntry:
    """Adapt one target-bound Merge snapshot to the shared session picker."""
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
        typer.echo(f"MERGE DEFERRED · {session.target.context_name}")
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
        typer.echo(f"MERGE DEFERRED · {session.target.context_name}")
        typer.echo(f"SESSION · {session.uid}")
        typer.echo("SOURCE · UNCHANGED")
        typer.echo("RESUME · mem merge --sessions")
    else:
        _present_terminal_outcome(session)
    if interactive_ran:
        if not terminal_session:
            typer.secho(
                "Interactive Merge view closed; any approved turns remain saved.",
                fg=typer.colors.CYAN,
            )
    else:
        typer.secho(
            "Resumed without calling the semantic provider.",
            fg=typer.colors.CYAN,
        )


def present_started_meld(
    session: MeldSession,
) -> None:
    """Present a newly created Merge."""
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
            "Merge completed without an opinion-submission turn."
            if interactive_ran and session.state == "APPLIED"
            else (
                "Merge ended without opening a response turn."
                if interactive_ran
                else "Resumed without calling the semantic provider."
            )
        ),
        fg=typer.colors.CYAN,
    )
