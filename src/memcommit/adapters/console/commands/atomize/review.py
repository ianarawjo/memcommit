"""Atomize-owned projection and loader for ``mem review atomize``."""

from __future__ import annotations

import copy
from dataclasses import replace
import sys

import typer

from memcommit.adapters.console.commands.atomize.sessions import (
    atomize_application_checkpoint_uid,
    load_saved_atomize_analysis,
    revalidate_saved_atomize_analysis,
)
from memcommit.adapters.console.commands.review.report import (
    render_review_report_snapshot,
    run_review_report_shell,
    show_operation_review,
)
from memcommit.adapters.console.commands.review.snapshot import visible_ordinal_index
from memcommit.adapters.console.terminal.components.result import (
    render_result_workbench_snapshot,
)
from memcommit.application.capabilities.resolution.workbench import ResolutionNavigation
from memcommit.application.capabilities.reviewing.report import ReviewReportController
from memcommit.application.operations.atomize.domain import AtomizeAnalysisSession
from memcommit.application.operations.atomize.resolution_adapter import (
    AtomizeResolutionWorkbenchAdapter,
)
from memcommit.application.operations.atomize.result_adapter import (
    AtomizeResultWorkbenchAdapter,
)
from memcommit.application.operations.atomize.workbench import (
    AtomizeWorkbenchSession,
    atomize_workbench_issue_projection,
    create_atomize_workbench,
    project_atomize_workbench_findings,
)
from memcommit.application.operations.review.model import ReviewError
from memcommit.persistence.store import MemoryStore


def atomize_review_report(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> ReviewReportController:
    """Expose Atomize findings and saved clarification responses."""

    result_view = AtomizeResultWorkbenchAdapter(analysis).view()
    if workbench.application is not None:
        result_view = replace(result_view, status="APPLIED ANALYSIS")

    return ReviewReportController.from_resolution(
        AtomizeResolutionWorkbenchAdapter(analysis, workbench).view,
        kind="CLARIFICATION",
        title="MEM REVIEW · ATOMIZE",
        summary=(
            "Review uncertain findings and their saved clarifications. "
            "Context application remains outside Review."
        ),
        # Atomize's immutable result account and its actionable clarification
        # queue are different layers. Preserve the former verbatim while the
        # common Review host supplies navigation and response controls.
        report_text=render_result_workbench_snapshot(result_view),
    )


def _load_direct_context(
    store: MemoryStore,
    context_name: str | None,
    *,
    current_name: str | None,
):
    selected_name = context_name if context_name is not None else current_name
    if not selected_name:
        raise RuntimeError(
            "No current context. Pass --context or run 'mem init <name>' first."
        )
    return store.load_direct(selected_name)


def open_atomize_review(
    *,
    store: MemoryStore,
    context_name: str | None,
    current_name: str | None,
    snapshot: bool,
    replace: bool,
    respond_to: str | None,
    response: str | None,
    expected_analysis_uid: str | None = None,
) -> None:
    """Resume the Context-bound Atomize workbench through the Review host."""

    if expected_analysis_uid is not None:
        selected_analysis = load_saved_atomize_analysis(
            store,
            expected_analysis_uid,
        )
        expected_analysis_uid = selected_analysis.uid
        context_name = selected_analysis.context_name
    ctx = _load_direct_context(
        store,
        context_name,
        current_name=current_name,
    )
    analysis = store.load_atomize_analysis(ctx.uid)
    if analysis is None:
        raise ReviewError(
            "No saved atomize analysis exists for this Context. Run "
            "'mem impact atomize' or 'mem atomize' first."
        )
    if expected_analysis_uid is not None and analysis.uid != expected_analysis_uid:
        raise ReviewError(
            "The selected atomize analysis changed while the Review launcher "
            "was open. Reopen the launcher."
        )
    try:
        ctx, applied = revalidate_saved_atomize_analysis(store, analysis)
    except ValueError as error:
        raise ReviewError(str(error)) from error
    if not applied:
        raise ReviewError(
            "Atomize execution is not complete. Resume it with 'mem atomize'; "
            "Review opens only terminal application evidence."
        )
    if replace and applied:
        raise ReviewError(
            "An applied Atomize analysis is read-only and cannot replace its "
            "saved review state."
        )
    workbench = None if replace else store.load_atomize_workbench(analysis)
    if workbench is None:
        workbench = create_atomize_workbench(analysis)
        if not applied:
            store.save_atomize_workbench(workbench)
    if applied and workbench.application is None:
        checkpoint_uid = atomize_application_checkpoint_uid(
            store,
            ctx,
            analysis.uid,
        )
        if checkpoint_uid is None:
            raise ReviewError(
                "The applied Atomize analysis has no recognized checkpoint."
            )
        # Analysis-only and applied-Output copies deliberately have no durable
        # workbench owner. Project the exact terminal checkpoint into a local
        # read-only receipt without repairing persistence during a read.
        workbench = copy.deepcopy(workbench)
        workbench.record_application(
            output_context_name=analysis.context_name,
            checkpoint_uid=checkpoint_uid,
        )
    if not workbench.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_workbench_issue_projection(analysis),
    ):
        raise ReviewError("The saved atomize workbench does not match its analysis.")
    if (respond_to is None) != (response is None):
        raise ReviewError("--respond-to and --response must be used together.")
    if applied:
        if respond_to is not None:
            raise ReviewError(
                "An applied Atomize analysis is read-only; its saved findings "
                "and responses cannot be changed."
            )
        show_operation_review(
            atomize_review_report(analysis, workbench),
            snapshot=snapshot,
        )
        return
    if respond_to is not None:
        selector = respond_to.strip()
        findings = project_atomize_workbench_findings(analysis)
        finding_by_uid = {finding.uid: finding for finding in findings}
        ordered = workbench.ordered_issues()
        selected_index = visible_ordinal_index(selector, len(ordered))
        if selected_index is not None:
            matches = [finding_by_uid[ordered[selected_index].uid]]
        else:
            matches = [
                finding
                for finding in findings
                if finding.uid.startswith(selector)
                or any(
                    source_uid.startswith(selector)
                    for source_uid in finding.source_uids
                )
            ]
        if not selector or len(matches) != 1:
            raise ReviewError(
                "The response target is missing or ambiguous. Use its visible "
                "1-based issue number or a unique issue/source uid prefix."
            )
        workbench.cursor_uid = matches[0].uid
        workbench.response_for(matches[0].uid).text = response or ""
        store.save_atomize_workbench(workbench)
        typer.echo(
            render_review_report_snapshot(
                atomize_review_report(analysis, workbench).report()
            )
        )
        return
    if snapshot or not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo(
            render_review_report_snapshot(
                atomize_review_report(analysis, workbench).report()
            )
        )
        return

    navigation = ResolutionNavigation(selected_item_uid=workbench.cursor_uid)

    def load_draft(item_uid: str) -> tuple[str | None, str]:
        response = workbench.responses.get(item_uid)
        if response is None:
            return None, ""
        return response.selected_choice_uid, response.text

    def save_draft(
        item_uid: str,
        option_uid: str | None,
        comment: str,
    ) -> None:
        issue = next(
            (candidate for candidate in workbench.issues if candidate.uid == item_uid),
            None,
        )
        if issue is None or (
            option_uid is not None and option_uid not in issue.choice_uids
        ):
            raise ReviewError("Atomize Review returned an invalid item response.")
        workbench.cursor_uid = item_uid
        response = workbench.response_for(item_uid)
        response.selected_choice_uid = option_uid
        response.text = comment
        store.save_atomize_workbench(workbench)

    def toggle_sort() -> None:
        workbench.toggle_sort()
        store.save_atomize_workbench(workbench)

    while True:
        action = run_review_report_shell(
            atomize_review_report(analysis, workbench),
            interactive_actions=True,
            navigation=navigation,
            draft_loader=load_draft,
            draft_saver=save_draft,
            save_draft_on_close=True,
            toggle_sort=toggle_sort,
        )
        if action.kind == "CLOSE":
            typer.echo("Atomize workbench saved. No Memory changes applied.")
            return
        if action.kind != "SUBMIT_ITEM":
            raise ReviewError(f"Unsupported Atomize Review action '{action.kind}'.")


__all__ = ["atomize_review_report", "open_atomize_review"]
