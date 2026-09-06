"""Atomize-owned console adapter for ``mem impact atomize``."""

from __future__ import annotations

import sys

from dataclasses import replace
from typing import TYPE_CHECKING

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

import typer

from memcommit.adapters.console.commands.atomize.records import (
    load_saved_atomize_analysis,
    revalidate_saved_atomize_analysis,
)
from memcommit.adapters.console.coordination.review import ReviewCancelled
from memcommit.adapters.console.terminal.components.progress import (
    progressing_provider_factory,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.application.operations.atomize.analysis_application import (
    AtomizeAnalysisApplicationError,
    AtomizeAnalysisOpenRequest,
)
from memcommit.application.operations.atomize.analysis_runtime import (
    execute_atomize_analysis_open,
)
from memcommit.application.operations.atomize.domain import (
    AtomizeAnalysisSession,
    AtomizeImpactError,
)
from memcommit.application.operations.atomize.resolution_adapter import (
    AtomizeResolutionWorkbenchAdapter,
)
from memcommit.application.operations.atomize.result_adapter import (
    AtomizeResultWorkbenchAdapter,
)
from memcommit.application.operations.atomize.records import (
    AtomizeRecordError,
    AtomizeReviewFinding,
    AtomizeReviewRecord,
    atomize_review_issue_projection,
    project_atomize_review_findings,
)
from memcommit.application.capabilities.review_policy import (
    ownership_aware_application_review,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
)
from memcommit.application.capabilities.reviewing.result_workbench import (
    ResultWorkbenchView,
)
from memcommit.adapters.console.terminal.components.result import (
    render_result_workbench_snapshot,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.persistence.store import MemoryStore

if TYPE_CHECKING:
    from memcommit.adapters.console.terminal.components.resolution import (
        ResolutionDestination,
    )

from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)


_LIST_READING_PREVIEW_LIMIT = 2
_LIST_READING_LABEL_LIMIT = 160
_LIST_REASON_TEXT_LIMIT = 220


def _assert_matches(
    session: AtomizeReviewRecord,
    analysis: AtomizeAnalysisSession,
) -> None:
    if not session.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_review_issue_projection(analysis),
    ):
        raise ValueError("The atomize workbench does not match its saved analysis.")


def _finding_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, AtomizeReviewFinding]:
    return {
        finding.uid: finding for finding in project_atomize_review_findings(analysis)
    }


def _source_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, str]:
    return {item.memory_uid: item.content for item in analysis.items}


def _single_line(value: str, *, limit: int = 72) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _issue_label(finding: AtomizeReviewFinding) -> str:
    return {
        "AMBIGUITY": "AMBIGUITY",
        "CONFLICT": "CONFLICT",
        "ATOMIZE_SPLIT": "SUGGESTED SPLIT",
        "ATOMIZE_UNCERTAINTY": "AMBIGUITY",
    }[finding.kind]


def _reading_preview_lines(
    finding: AtomizeReviewFinding,
) -> list[str]:
    """Expose saved readings as lossy list hints, never new semantics."""
    if not finding.readings:
        return []
    visible = finding.readings[:_LIST_READING_PREVIEW_LIMIT]
    lines = [
        (
            "      WHY · "
            f"{_compact_preview_text(finding.reason, _LIST_REASON_TEXT_LIMIT)}"
        )
    ]
    lines.extend(
        (
            f"      ↳ R{index} · "
            f"{_compact_preview_text(reading.label, _LIST_READING_LABEL_LIMIT)}"
        )
        for index, reading in enumerate(visible, start=1)
    )
    hidden_count = len(finding.readings) - len(visible)
    if hidden_count:
        lines.append(
            f"      ↳ +{hidden_count} more "
            f"{'reading' if hidden_count == 1 else 'readings'} "
            "(open detail)"
        )
    return lines


def _compact_preview_text(value: str, limit: int) -> str:
    """Keep both a preview's opening claim and trailing qualification."""
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(
        normalized,
        limit,
        position="middle",
        marker=" … ",
    )


def _overview_text(
    session: AtomizeReviewRecord,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeReviewFinding],
    *,
    result_view: ResultWorkbenchView | None = None,
) -> str:
    view = result_view or AtomizeResultWorkbenchAdapter(analysis).view()
    result = render_result_workbench_snapshot(view).rstrip()
    return "\n".join(
        [
            result,
            "",
            (
                f"Analysis [{analysis.uid[:8]}] · "
                f"TARGET {analysis.context_name} · "
                f"ORDER: {session.sort_mode} (PROCESS LOCAL) · "
                f"{len(findings)} findings"
            ),
        ]
    )


def _list_text(
    session: AtomizeReviewRecord,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeReviewFinding],
    sources: dict[str, str],
    *,
    expanded_issue_uid: str | None = None,
    cursor_token: str = "",
    result_view: ResultWorkbenchView | None = None,
) -> str:
    current = session.current_issue()
    lines = [
        _overview_text(
            session,
            analysis,
            findings,
            result_view=result_view,
        ),
        "",
        "ATOMIZE FINDINGS",
    ]
    for index, descriptor in enumerate(
        session.ordered_issues(),
        start=1,
    ):
        finding = findings[descriptor.uid]
        is_current = current is not None and current.uid == descriptor.uid
        is_expanded = is_current and expanded_issue_uid == descriptor.uid
        pointer = "▾" if is_expanded else ("›" if is_current else " ")
        marker = (
            cursor_token
            if is_current and (not is_expanded or not finding.readings)
            else ""
        )
        source = sources.get(finding.source_uids[0], "")
        lines.append(
            f"{marker}{pointer} {index:>2}. · "
            f"{_issue_label(finding)} · "
            f"{finding.classification}  “{_single_line(source, limit=48)}”"
        )
        if is_expanded:
            lines.extend(
                f"      {line}" if line else ""
                for line in _detail_text(
                    session,
                    analysis,
                    findings,
                    sources,
                ).splitlines()
            )
        else:
            lines.extend(_reading_preview_lines(finding))
    if not findings:
        lines.append("  (no Atomize findings)")
    return "\n".join(lines)


def _reason_heading(finding: AtomizeReviewFinding) -> str:
    if finding.kind == "ATOMIZE_SPLIT":
        return "WHY THIS MEMORY SPLIT"
    if finding.kind == "CONFLICT":
        return (
            "WHY THE CONFLICT DEPENDS ON SCOPE"
            if finding.classification.endswith("MAY")
            else "WHY THESE MEMORIES CONFLICT"
        )
    return "WHY THIS IS UNCLEAR"


def _detail_text(
    session: AtomizeReviewRecord,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeReviewFinding],
    sources: dict[str, str],
) -> str:
    descriptor = session.current_issue()
    if descriptor is None:
        return (
            "NO ATOMIZE FINDINGS\n\n"
            "The overview and complete atomize analysis remain saved."
        )
    finding = findings[descriptor.uid]
    ordered = session.ordered_issues()
    number = next(
        index
        for index, candidate in enumerate(ordered, start=1)
        if candidate.uid == descriptor.uid
    )
    lines = [
        f"{_issue_label(finding)} {number}/{len(findings)}",
        "",
    ]
    for source_number, source_uid in enumerate(
        finding.source_uids,
        start=1,
    ):
        source_label = (
            "SOURCE" if len(finding.source_uids) == 1 else f"SOURCE {source_number}"
        )
        lines.extend(
            [
                f"{source_label} [{safe_terminal_text(source_uid[:8])}]",
                safe_terminal_text(
                    sources.get(source_uid, "[source Memory unavailable]")
                ),
                "",
            ]
        )
    lines.extend(
        [
            "CLASSIFICATION",
            safe_terminal_text(finding.classification),
            "",
            _reason_heading(finding),
            safe_terminal_text(finding.reason),
        ]
    )
    if finding.question:
        lines.extend(
            [
                "",
                "CLARIFICATION PROMPT",
                safe_terminal_text(finding.question),
            ]
        )
    if finding.readings:
        lines.extend(["", "POSSIBLE READINGS"])
        for index, reading in enumerate(finding.readings, start=1):
            lines.append(
                f"  {index}. "
                f"[{safe_terminal_text(reading.role)}] "
                f"{safe_terminal_text(reading.label)}"
            )
            if reading.label != reading.text:
                lines.append(f"   {safe_terminal_text(reading.text)}")
    if finding.children:
        lines.extend(["", "PROPOSED CHILDREN"])
        for index, child in enumerate(finding.children, start=1):
            lines.append(f"{index}. {safe_terminal_text(child.content)}")
            evidence = [*child.source_spans, *child.frame_spans]
            if evidence:
                lines.append(
                    "   EVIDENCE: "
                    + " | ".join(safe_terminal_text(span) for span in evidence)
                )
    return "\n".join(lines).rstrip()


def render_atomize_impact_snapshot(
    session: AtomizeReviewRecord,
    analysis: AtomizeAnalysisSession,
    *,
    show_all: bool = False,
) -> str:
    """Render the same durable state without ANSI or a live terminal."""
    _assert_matches(session, analysis)
    findings = _finding_map(analysis)
    sources = _source_map(analysis)
    result_view = AtomizeResultWorkbenchAdapter(analysis).view()
    lines = [
        _list_text(
            session,
            analysis,
            findings,
            sources,
            result_view=result_view,
        ),
        "",
        _detail_text(session, analysis, findings, sources),
    ]
    if show_all:
        lines.extend(["", "ALL ATOMIZE RESULTS"])
        for item in analysis.items:
            lines.append(
                f"{item.position + 1:>3}. {item.classification} "
                f"[{item.memory_uid[:8]}] "
                f"{_single_line(item.content)}"
            )
    lines.extend(
        [
            "",
            (
                "SOURCE means canonical Context order; Memory creation "
                "timestamps are not recorded."
            ),
            "No Memory changes have been applied. No checkpoint was created.",
        ]
    )
    return "\n".join(lines)


def run_atomize_impact_shell(
    record: AtomizeReviewRecord,
    analysis: AtomizeAnalysisSession,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    workflow_actions: bool = False,
    application_complete: bool = False,
    destination: ResolutionDestination | None = None,
) -> AtomizeReviewRecord | ResolutionWorkbenchAction:
    """Inspect one analysis with process-local navigation and sorting."""
    from memcommit.adapters.console.terminal.components.resolution import (
        run_resolution_workbench_shell,
    )

    _assert_matches(record, analysis)
    navigation = ResolutionNavigation(
        selected_item_uid=record.cursor_uid,
    )

    def view():
        projected = AtomizeResolutionWorkbenchAdapter(analysis, record).view()
        if workflow_actions:
            return projected
        # A completed Atomize report has no mutation or response capability.
        return replace(
            projected,
            title="MEM IMPACT · ATOMIZE",
            route=f"TARGET {analysis.context_name}",
            status=(
                "APPLIED RECORD · NON-APPLYING"
                if application_complete
                else "ANALYSIS · NON-APPLYING"
            ),
            context_locations=projected.context_locations[:1],
            capabilities=frozenset(),
            accept_enabled=False,
            accept_mode="CHANGES",
            unresolved_at_apply_count=0,
        )

    def toggle_sort() -> None:
        record.toggle_sort()

    first_round = True
    while True:
        action = run_resolution_workbench_shell(
            view,
            navigation=navigation,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty and first_round,
            terminal_label="Interactive Atomize Impact",
            snapshot_hint=(
                "Run 'mem impact atomize' outside a TTY to render the saved snapshot."
            ),
            toggle_sort=toggle_sort,
            split_viewer_items=True,
            review_and_apply=workflow_actions,
            decision_free_behavior=(
                ownership_aware_application_review(
                    mutates_granted_authority=False,
                    local_undo_available=True,
                ).decision_free_behavior
                if workflow_actions
                else "REPORT_FIRST"
            ),
            destination=destination,
            read_only=not workflow_actions,
        )
        first_round = False
        record.cursor_uid = navigation.selected_item_uid
        if action.kind == "CLOSE":
            return record
        if workflow_actions and action.kind in {
            "ACCEPT",
            "CHANGE_DESTINATION",
        }:
            return action
        raise ValueError(f"Unsupported resolution action '{action.kind}' for Atomize.")


def open_saved_atomize_impact(
    store: MemoryStore,
    *,
    session_uid: str | None,
    show_all: bool = False,
) -> None:
    """Open one exact Atomize analysis without a create or refresh fallback."""

    if session_uid is None:
        raise ValueError("Saved Atomize Impact requires an exact session UID.")
    analysis = load_saved_atomize_analysis(store, session_uid)
    revalidate_saved_atomize_analysis(store, analysis)
    record = store.load_atomize_workbench(analysis)
    if record is None:
        raise ValueError(
            "The saved Atomize review record is unavailable. Run "
            "'mem impact atomize CONTEXT' to reopen or explicitly refresh "
            "that Context."
        )
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_atomize_impact_snapshot(
                record,
                analysis,
                show_all=show_all,
            )
        )
    else:
        try:
            run_atomize_impact_shell(
                record,
                analysis,
            )
        except ReviewCancelled:
            typer.echo("Atomize Impact closed. No Memory changes applied.")
    typer.secho(
        f"Resumed saved analysis [{analysis.uid[:8]}]; the provider was not called.",
        fg=typer.colors.CYAN,
    )


def run_atomize_impact(
    *,
    store: MemoryStore,
    context_name: str,
    show_all: bool,
    refresh: bool,
    memory_selector: str | None,
) -> None:
    """Create once or reopen one non-applying atomization analysis."""

    try:
        ctx = store.load_direct(context_name)
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        with progressing_provider_factory(
            "IMPACT ATOMIZE",
            "analyzing memory structure",
            connect_codex_chatgpt_provider,
        ) as provider_factory:
            opened = execute_atomize_analysis_open(
                AtomizeAnalysisOpenRequest(
                    context=ctx,
                    refresh=refresh,
                    memory_selector=memory_selector,
                ),
                store=store,
                provider_factory=provider_factory,
            )
        analysis = opened.analysis
        record = opened.review_record
    except (
        AtomizeAnalysisApplicationError,
        AtomizeImpactError,
        AtomizeRecordError,
        OSError,
        QueryProviderError,
        ValueError,
    ) as error:
        typer.secho(
            f"Impact error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_atomize_impact_snapshot(
                record,
                analysis,
                show_all=show_all,
            )
        )
    else:
        try:
            run_atomize_impact_shell(
                record,
                analysis,
            )
        except ReviewCancelled:
            typer.echo("Atomize Impact closed. No Memory changes applied.")
    if opened.created_analysis:
        typer.secho(
            f"Analysis saved [{analysis.uid[:8]}] for mem trace/rationale.",
            fg=typer.colors.CYAN,
        )
    else:
        typer.secho(
            f"Resumed saved analysis [{analysis.uid[:8]}]; "
            "the provider was not called.",
            fg=typer.colors.CYAN,
        )
    typer.echo(f"REOPEN · mem impact atomize --session {analysis.uid}")
    typer.echo("BROWSE ATOMIZE · mem impact atomize --sessions")
    typer.echo("BROWSE ALL IMPACT · mem impact --sessions")


__all__ = ["open_saved_atomize_impact", "run_atomize_impact"]
