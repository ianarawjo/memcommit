"""Interactive and snapshot views over one saved atomize workbench."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.atomize import AtomizeAnalysisSession
from memcommit.atomize_resolution_adapter import (
    AtomizeResolutionWorkbenchAdapter,
)
from memcommit.atomize_result_adapter import AtomizeResultWorkbenchAdapter
from memcommit.atomize_workbench import (
    ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT,
    AtomizeWorkbenchFinding,
    AtomizeWorkbenchSession,
    atomize_workbench_issue_projection,
    project_atomize_workbench_findings,
)
from memcommit.interfaces.tui.workbenches.review import (
    RESPONSE_LABEL,
)
from memcommit.application_review_policy import (
    ownership_aware_application_review,
)
from memcommit.interfaces.tui.workbenches.result import (
    render_result_workbench_snapshot,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.resolution_workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
)
from memcommit.result_workbench import (
    ResultWorkbenchView,
)
from memcommit.selection.tui import choice_marker

if TYPE_CHECKING:
    from memcommit.interfaces.tui.workbenches.resolution import ResolutionDestination

_LIST_READING_PREVIEW_LIMIT = 2
_LIST_READING_LABEL_LIMIT = 160
_LIST_REASON_TEXT_LIMIT = 220
def _assert_matches(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
) -> None:
    if not session.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_workbench_issue_projection(analysis),
    ):
        raise ValueError("The atomize workbench does not match its saved analysis.")


def _finding_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, AtomizeWorkbenchFinding]:
    return {
        finding.uid: finding for finding in project_atomize_workbench_findings(analysis)
    }


def _source_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, str]:
    return {item.memory_uid: item.content for item in analysis.items}


def _single_line(value: str, *, limit: int = 72) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _issue_label(finding: AtomizeWorkbenchFinding) -> str:
    return {
        "AMBIGUITY": "AMBIGUITY",
        "CONFLICT": "CONFLICT",
        "ATOMIZE_SPLIT": "SUGGESTED SPLIT",
        "ATOMIZE_UNCERTAINTY": "ATOMIZE UNCERTAINTY",
    }[finding.kind]


def _reading_preview_lines(
    finding: AtomizeWorkbenchFinding,
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
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
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
                f"INPUT {analysis.context_name} → OUTPUT "
                f"{session.output_context_name or analysis.context_name} · "
                f"ORDER: {session.sort_mode} · "
                f"{session.answered_count}/{len(findings)} answered"
            ),
        ]
    )


def _list_text(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    sources: dict[str, str],
    *,
    expanded_issue_uid: str | None = None,
    reading_index: int = 0,
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
        "ACTIONABLE ISSUES",
    ]
    for index, descriptor in enumerate(
        session.ordered_issues(),
        start=1,
    ):
        finding = findings[descriptor.uid]
        response = session.responses.get(descriptor.uid)
        is_current = current is not None and current.uid == descriptor.uid
        is_expanded = is_current and expanded_issue_uid == descriptor.uid
        pointer = "▾" if is_expanded else ("›" if is_current else " ")
        marker = (
            cursor_token
            if is_current and (not is_expanded or not finding.readings)
            else ""
        )
        status = "✓" if response is not None and response.answered else "·"
        source = sources.get(finding.source_uids[0], "")
        lines.append(
            f"{marker}{pointer} {index:>2}. {status} "
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
                    reading_cursor_index=(reading_index if finding.readings else None),
                    reading_cursor_token=cursor_token,
                ).splitlines()
            )
        else:
            lines.extend(_reading_preview_lines(finding))
    if not findings:
        lines.append("  (no actionable atomize, ambiguity, or conflict issues)")
    return "\n".join(lines)


def _reason_heading(finding: AtomizeWorkbenchFinding) -> str:
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
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    sources: dict[str, str],
    *,
    reading_cursor_index: int | None = None,
    reading_cursor_token: str = "",
) -> str:
    descriptor = session.current_issue()
    if descriptor is None:
        return (
            "NO ACTIONABLE ISSUES\n\n"
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
        selected = session.selected_choice_index(descriptor)
        lines.extend(["", "READING OPTIONS"])
        for index, reading in enumerate(finding.readings, start=1):
            if reading_cursor_index is None:
                pointer = "›" if selected == index - 1 else " "
                marker = ""
            else:
                pointer = "›" if reading_cursor_index == index - 1 else " "
                marker = f"{choice_marker(selected=selected == index - 1)} "
            cursor_marker = (
                reading_cursor_token if reading_cursor_index == index - 1 else ""
            )
            lines.append(
                f"{cursor_marker}{pointer} {marker}{index}. "
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


def render_atomize_workbench_snapshot(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    *,
    show_all: bool = False,
) -> str:
    """Render the same durable state without ANSI or a live terminal."""
    _assert_matches(session, analysis)
    findings = _finding_map(analysis)
    sources = _source_map(analysis)
    result_view = AtomizeResultWorkbenchAdapter(analysis).view()
    current = session.current_issue()
    response_text = ""
    if current is not None:
        response = session.responses.get(current.uid)
        if response is not None:
            response_text = safe_terminal_text(response.text)
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
        "",
        RESPONSE_LABEL,
        f"> {response_text}",
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


def run_atomize_workbench_shell(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    *,
    save: Callable[[AtomizeWorkbenchSession], None],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    workflow_actions: bool = False,
    application_complete: bool = False,
    destination: ResolutionDestination | None = None,
) -> AtomizeWorkbenchSession | ResolutionWorkbenchAction:
    """Review Atomize findings through the shared resolution workbench."""
    from memcommit.interfaces.tui.workbenches.resolution import (
        ResolutionGlobalStrategy,
        run_resolution_workbench_shell,
    )

    _assert_matches(session, analysis)
    navigation = ResolutionNavigation(
        selected_item_uid=session.cursor_uid,
    )

    def view():
        projected = AtomizeResolutionWorkbenchAdapter(analysis, session).view()
        if workflow_actions:
            return projected
        # Review-only and terminal sessions may still edit saved comments, but
        # they must not leak the adapter's Apply or whole-set materialization
        # capabilities through keyboard shortcuts in the common shell.
        return replace(
            projected,
            status="APPLIED" if application_complete else projected.status,
            capabilities=frozenset({"SUBMIT_ITEM"}),
            accept_enabled=False,
            accept_mode="CHANGES",
            unresolved_at_apply_count=0,
        )

    def load_draft(issue_uid: str) -> tuple[str | None, str]:
        response = session.responses.get(issue_uid)
        if response is None:
            return None, ""
        return response.selected_choice_uid, response.text

    saved_in_round = {"value": False}

    def validate_response(comment: str) -> None:
        if len(comment) > ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT:
            raise ValueError(
                "Response is too long to save "
                f"({len(comment):,}/"
                f"{ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT:,} characters)."
            )

    def save_draft(
        issue_uid: str,
        option_uid: str | None,
        comment: str,
    ) -> None:
        validate_response(comment)
        response = session.response_for(issue_uid)
        response.selected_choice_uid = option_uid
        response.text = comment
        session.cursor_uid = issue_uid
        save(session)
        saved_in_round["value"] = True

    def toggle_sort() -> None:
        session.toggle_sort()
        save(session)
        saved_in_round["value"] = True

    first_round = True
    while True:
        saved_in_round["value"] = False
        action = run_resolution_workbench_shell(
            view,
            navigation=navigation,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty and first_round,
            terminal_label="Interactive atomize workbench",
            snapshot_hint=(
                "Run 'mem impact atomize' outside a TTY to render the saved snapshot."
            ),
            draft_loader=load_draft,
            draft_saver=save_draft,
            response_validator=validate_response,
            save_draft_on_close=True,
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
            global_strategies=(
                ResolutionGlobalStrategy(
                    label="Keep unanswered optional findings as analyzed",
                    action_kind="SUBMIT_ALL",
                    comment=(
                        "Keep unanswered optional findings as analyzed while "
                        "incorporating every saved Atomize response into the "
                        "revised proposal."
                    ),
                ),
            )
            if workflow_actions
            else (),
            compact_decisions=workflow_actions,
        )
        first_round = False
        session.cursor_uid = navigation.selected_item_uid
        if action.kind == "CLOSE":
            if not saved_in_round["value"]:
                save(session)
            return session
        if workflow_actions and action.kind in {
            "SUBMIT_ALL",
            "INCORPORATE_AND_APPLY",
            "ACCEPT",
            "CHANGE_DESTINATION",
        }:
            return action
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise ValueError(
                f"Unsupported resolution action '{action.kind}' for Atomize."
            )
        save_draft(
            action.item_uid,
            action.option_uid,
            action.comment,
        )
        session.move(1)
        navigation.selected_item_uid = session.cursor_uid
        navigation.close_detail()
