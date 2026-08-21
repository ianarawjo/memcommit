"""Common snapshot and terminal host for operation-adaptive Review reports."""

from __future__ import annotations

from collections.abc import Callable

import click
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.resolution_workbench_shell import (
    resolution_report_fragments,
    run_resolution_workbench_shell,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.interfaces.console.theme import SemanticColorRole, semantic_color_rgb
from memcommit.interfaces.tui.core.theme import semantic_role_style
from memcommit.resolution_workbench import (
    ResolutionNavigation,
    ResolutionOverviewSection,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.responses.resolution import (
    response_draft_from_item,
    response_target_from_item,
)
from memcommit.responses.tui import response_snapshot_lines
from memcommit.review_report import (
    ReviewReport,
    ReviewReportController,
    ReviewTextFragment,
)


def render_review_report_snapshot(report: ReviewReport) -> str:
    """Render the existing operation report without adding an Apply action."""
    parts = [] if report.view is not None else [f"{report.title}\n{report.summary}"]
    if report.report_text.strip():
        parts.append(report.report_text.rstrip())
    if report.view is not None:
        parts.append(
            "".join(
                text
                for style, text in resolution_report_fragments(
                    report.view,
                    read_only=True,
                )
                if style != "[SetCursorPosition]"
            ).rstrip()
        )
        detail_lines: list[str] = []
        for item in report.view.items:
            if not item.blocks and item.issue_presentation is None:
                continue
            detail_lines.append(safe_terminal_text(item.title))
            if item.issue_presentation is not None:
                for evidence in item.issue_presentation.evidence:
                    if evidence.group_heading:
                        detail_lines.append(
                            f"  {safe_terminal_text(evidence.group_heading)}"
                        )
                    detail_indent = "    " if evidence.group_heading else "  "
                    detail_lines.append(f"{detail_indent}CLASSIFICATION")
                    detail_lines.extend(
                        f"{detail_indent}  {line}"
                        for line in safe_terminal_text(
                            evidence.classification
                        ).splitlines()
                    )
                    detail_lines.append(
                        f"{detail_indent}{safe_terminal_text(evidence.sources_heading)}"
                    )
                    for claim in evidence.source_groups:
                        detail_lines.append(
                            f"{detail_indent}  "
                            f"{safe_terminal_text(claim.label)} · FROM "
                            f"{safe_terminal_text(claim.context_name)}"
                        )
                        for source in claim.sources:
                            detail_lines.append(
                                f"{detail_indent}    "
                                f"[{safe_terminal_text(source.memory_uid[:8])}] "
                                f"{safe_terminal_text(source.content)}"
                            )
                    detail_lines.append(
                        f"{detail_indent}{safe_terminal_text(evidence.reason_heading)}"
                    )
                    detail_lines.extend(
                        f"{detail_indent}  {line}"
                        for line in safe_terminal_text(evidence.reason).splitlines()
                    )
                response_target = response_target_from_item(
                    report.view,
                    item,
                    read_only=True,
                )
                if response_target is not None:
                    detail_lines.extend(
                        response_snapshot_lines(
                            response_target,
                            response_draft_from_item(item),
                            indent="  ",
                        )
                    )
            for block in item.blocks:
                detail_lines.append(f"  {safe_terminal_text(block.heading)}")
                detail_lines.extend(
                    f"    {line}"
                    for line in safe_terminal_text(block.text).splitlines()
                )
        if detail_lines:
            parts.append("\n".join(detail_lines))
    return "\n\n".join(parts).rstrip()


def echo_review_report_snapshot(report: ReviewReport) -> None:
    """Emit a snapshot while retaining typed semantic tokens when available."""

    if not report.report_fragments:
        click.echo(render_review_report_snapshot(report))
        return
    fragments = (
        ReviewTextFragment(f"{report.title}\n{report.summary}\n\n"),
        *report.report_fragments,
    )
    for fragment in fragments:
        if fragment.role is None:
            click.echo(fragment.text, nl=False)
        else:
            click.secho(
                fragment.text,
                fg=semantic_color_rgb(fragment.role),
                bold=fragment.bold,
                nl=False,
            )
    click.echo()


def _review_report_tui_fragments(
    report: ReviewReport,
) -> tuple[tuple[str, str], ...] | None:
    if not report.report_fragments:
        return None
    return tuple(
        (
            (
                "class:impact.add"
                if fragment.role is SemanticColorRole.ADD
                else "class:impact.remove"
                if fragment.role is SemanticColorRole.REMOVE
                else semantic_role_style(fragment.role)
                if fragment.role is not None
                else ""
            ),
            fragment.text,
        )
        for fragment in report.report_fragments
    )


def _text_only_view(report: ReviewReport) -> ResolutionWorkbenchView:
    overview_sections = (
        ResolutionOverviewSection("summary", "SUMMARY", report.summary),
    )
    return ResolutionWorkbenchView(
        operation=report.operation,
        artifact_uid=report.artifact_uid,
        revision=report.revision,
        title=report.title,
        route=report.kind,
        status="REVIEW REPORT · READ ONLY",
        metrics=(),
        overview=report.summary,
        overview_sections=overview_sections,
        list_label="REPORT",
        items=(),
        empty_message="This report has no interactive review items.",
        results_label="REVIEW RESPONSES",
        results=(),
        capabilities=frozenset(),
        accept_enabled=False,
        input_locked=True,
    )


def run_review_report_shell(
    controller: ReviewReportController,
    *,
    interactive_actions: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    navigation: ResolutionNavigation | None = None,
    draft_loader: Callable[[str], tuple[str | None, str]] | None = None,
    draft_saver: Callable[[str, str | None, str], None] | None = None,
    save_draft_on_close: bool = False,
    toggle_sort: Callable[[], None] | None = None,
) -> ResolutionWorkbenchAction:
    """Show one report and return a review action; never return Accept."""
    report = controller.report()
    view = report.view or _text_only_view(report)
    action = run_resolution_workbench_shell(
        view,
        navigation=navigation,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
        terminal_label=f"Interactive {report.operation.title()} review",
        snapshot_hint="Run the same 'mem review' command outside a TTY for a snapshot.",
        split_viewer_items=True,
        split_report_text=report.report_text or None,
        split_report_fragments=_review_report_tui_fragments(report),
        read_only=not interactive_actions,
        draft_loader=draft_loader,
        draft_saver=draft_saver,
        save_draft_on_close=save_draft_on_close,
        toggle_sort=toggle_sort,
    )
    if action.kind == "ACCEPT":
        raise ValueError("Review cannot return an Apply action.")
    return action
