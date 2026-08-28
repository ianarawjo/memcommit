"""Create or resume the shared terminal shell for semantic review."""

from __future__ import annotations

import copy
import sys
from typing import Annotated, Optional

import typer

import memcommit.application.ops as ops
from memcommit.application.operations.atomize.domain import (
    AtomizeImpactError,
)
from memcommit.application.operations.atomize.workbench import (
    AtomizeWorkbenchError,
    atomize_workbench_issue_projection,
    create_atomize_workbench,
    project_atomize_workbench_findings,
)
from memcommit.application.retained_history.applied_review import (
    CHECKPOINT_REVIEW_OPERATIONS,
    applied_checkpoint_review_controller,
    list_applied_checkpoint_reviews,
    select_applied_checkpoint_review,
)
from memcommit.adapters.console.shared.command_progress import CommandProgress
from memcommit.adapters.console.shared.context_operand import ContextOperandSnapshot
from memcommit.adapters.interfaces.cli.review import (
    render_review_snapshot,
    visible_ordinal_index,
)
from memcommit.adapters.interfaces.tui.workbenches.review import ReviewCancelled
from memcommit.adapters.console.commands.review.resolution_shell import (
    run_review_resolution_shell as run_review_shell,
)
from memcommit.adapters.interfaces.tui.components.operation_launcher.session import (
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.adapters.console.commands.review.sessions import (
    SAVED_REVIEW_KIND,
    choose_review_session,
)
from memcommit.adapters.console.text import (
    display_escape_text,
)
from memcommit.application.reviewing.quality.findings import FindingsError
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.application.reviewing.quality.audit import (
    QualityAuditError,
)
from memcommit.application.reviewing.quality.audit_store import QualityAuditStore
from memcommit.application.operations.review.model import (
    ReviewError,
    atomize_review_matches_analysis,
    create_ambiguity_review,
    review_matches_context,
)
from memcommit.persistence.store import MemoryStore
from memcommit.core.context_targeting.uid_locator import UidLocatorError, resolve_exact_or_unique_uid


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _select_report_session(
    entries: tuple[SessionPickerEntry, ...],
    *,
    kind: str,
    title: str,
    session_uid: str | None,
    selector_option: str = "--session",
) -> SessionPickerEntry | None:
    """Resolve one UID/prefix or return one TTY picker selection."""
    if session_uid is not None:
        try:
            return resolve_exact_or_unique_uid(
                entries,
                session_uid,
                uid=lambda entry: entry.key,
                label=f"Saved {kind} review artifact",
            )
        except UidLocatorError as error:
            raise ReviewError(str(error)) from error
    if not entries:
        raise ReviewError(f"No saved {kind} review artifacts are available.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        if len(entries) == 1:
            return entries[0]
        raise ReviewError(
            f"Several saved {kind} artifacts are available; pass "
            f"{selector_option} UID."
        )
    receipt = choose_session(entries, title=title)
    if receipt is None:
        return None
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != kind:
        raise ReviewError("Review session picker returned an invalid receipt.")
    selected = next((entry for entry in entries if entry.key == receipt.key), None)
    if selected is None or selected.reopen_argv != receipt.argv:
        raise ReviewError("Review session picker returned a stale receipt.")
    return selected


def _load_saved_review_by_selector(
    store: MemoryStore,
    selector: str,
):
    """Resolve one active or terminal-history ReviewSession UID/prefix."""

    try:
        return resolve_exact_or_unique_uid(
            store.list_review_sessions(),
            selector,
            uid=lambda session: session.uid,
            label="Saved Review session",
        )
    except UidLocatorError as error:
        raise ReviewError(str(error)) from error


def _show_operation_review(controller, *, snapshot: bool) -> None:
    from memcommit.adapters.console.commands.review.report import (
        echo_review_report_snapshot,
        render_review_report_snapshot,
        run_review_report_shell,
    )

    report = controller.report()
    if snapshot or not sys.stdin.isatty() or not sys.stdout.isatty():
        if report.report_fragments:
            echo_review_report_snapshot(report)
        else:
            typer.echo(render_review_report_snapshot(report))
        return
    run_review_report_shell(controller, interactive_actions=False)


def _checkpoint_report_entries(
    store: MemoryStore,
    operation: str,
) -> tuple[SessionPickerEntry, ...]:
    """Project immutable application checkpoints through the common picker."""

    from datetime import datetime

    return tuple(
        SessionPickerEntry(
            kind=operation,
            key=record.checkpoint_uid,
            title=f"{record.context_name} · {record.checkpoint_uid[:8]}",
            status="APPLIED",
            subtitle=record.description,
            group=record.context_name,
            sort_timestamp=datetime.fromisoformat(record.timestamp).timestamp(),
            detail=(
                f"{operation.upper()} RECEIPT\n"
                f"Context: {record.context_name}\n"
                f"Checkpoint: {record.checkpoint_uid}\n"
                f"Completed: {record.timestamp}\n\n"
                "Enter opens immutable post-application evidence."
            ),
            reopen_argv=(
                "mem",
                "review",
                operation,
                "--receipt",
                record.checkpoint_uid,
            ),
        )
        for record in list_applied_checkpoint_reviews(store, operation)
    )


def _run_checkpoint_report(
    store: MemoryStore,
    *,
    operation: str,
    receipt_uid: str | None,
    snapshot: bool,
) -> None:
    records = list_applied_checkpoint_reviews(store, operation)
    if receipt_uid is not None:
        try:
            record = select_applied_checkpoint_review(records, receipt_uid)
        except ValueError as error:
            raise ReviewError(str(error)) from error
    else:
        selected = _select_report_session(
            _checkpoint_report_entries(store, operation),
            kind=operation,
            title=f"MEM REVIEW · {operation.upper()} RECEIPTS",
            session_uid=None,
            selector_option="--receipt",
        )
        if selected is None:
            return
        record = select_applied_checkpoint_review(records, selected.key)
    _show_operation_review(
        applied_checkpoint_review_controller(record),
        snapshot=snapshot,
    )


def _run_update_report(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    from memcommit.application.operations.review.report_adapters import update_review_report
    from memcommit.application.operations.update.receipt_store import UpdateReceiptStore

    current = store.load_staged_update() or store.load_impact_plan()
    retained = UpdateReceiptStore(store).list()
    if current is None and not retained:
        raise ReviewError(
            "No saved Update or Impact plan exists. Run 'mem impact' first."
        )
    if session_uid is None:
        session = current or retained[0]
    else:
        candidates = retained
        if current is not None and current.uid not in {
            candidate.uid for candidate in retained
        }:
            candidates = (*retained, current)
        try:
            session = resolve_exact_or_unique_uid(
                candidates,
                session_uid,
                uid=lambda candidate: candidate.uid,
                label="Saved Update artifact",
            )
        except UidLocatorError as error:
            raise ReviewError(str(error)) from error
    if session.status not in {"applied", "undone"}:
        raise ReviewError(
            "Update execution is not complete. Resume it with 'mem update'; "
            "Review opens only terminal application evidence."
        )
    _show_operation_review(update_review_report(session), snapshot=snapshot)


def _run_audit_review(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    """Open one exact saved Audit without rerunning any finder."""

    from memcommit.adapters.console.commands.audit.review import (
        render_quality_audit_review_snapshot,
        run_quality_audit_review,
    )
    from memcommit.adapters.console.commands.audit.sessions import audit_session_entries

    sessions = QualityAuditStore(store)
    selected = _select_report_session(
        audit_session_entries(sessions),
        kind="audit",
        title="MEM REVIEW · AUDIT REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    session = sessions.load(selected.key)
    if snapshot or not _interactive_terminal():
        typer.echo(render_quality_audit_review_snapshot(session))
        return
    run_quality_audit_review(store, session)


def _run_compare_report(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    from memcommit.adapters.console.commands.compare.sessions import (
        comparison_session_entries,
        load_saved_comparison,
        revalidate_saved_comparison,
    )
    from memcommit.application.operations.review.report_adapters import compare_review_report

    selected = _select_report_session(
        comparison_session_entries(store),
        kind="compare",
        title="MEM REVIEW · COMPARE REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    analysis = load_saved_comparison(selected.key, store=store)
    revalidate_saved_comparison(store, analysis)
    _show_operation_review(compare_review_report(analysis), snapshot=snapshot)


def _run_meld_report(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    from memcommit.adapters.console.commands.meld.sessions import (
        list_meld_session_catalog,
        reload_selected_meld_session,
    )
    from memcommit.application.operations.review.report_adapters import meld_review_report

    catalog = list_meld_session_catalog(store)
    by_key = {entry.session_uid: entry for entry in catalog}
    entries = tuple(
        SessionPickerEntry(
            kind="meld",
            key=entry.session_uid,
            title=entry.title,
            status=entry.status,
            subtitle=entry.subtitle,
            group=entry.group,
            sort_timestamp=entry.modified_timestamp,
            detail=entry.detail,
            reopen_argv=entry.reopen_argv,
        )
        for entry in catalog
    )
    selected = _select_report_session(
        entries,
        kind="meld",
        title="MEM REVIEW · MELD REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    session = reload_selected_meld_session(store, by_key[selected.key])
    if session.state != "APPLIED":
        raise ReviewError(
            "Meld execution is not complete. Resume it with 'mem meld'; "
            "Review opens only terminal application evidence."
        )
    _show_operation_review(meld_review_report(session), snapshot=snapshot)


def _run_sever_report(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    from memcommit.adapters.console.commands.sever.sessions import (
        list_sever_session_catalog,
        reload_selected_sever_session,
    )
    from memcommit.application.operations.review.report_adapters import sever_review_report
    from memcommit.application.operations.sever.session_store import SeverSessionStore

    sessions = SeverSessionStore(store)
    catalog = list_sever_session_catalog(sessions)
    by_key = {entry.picker_entry.key: entry for entry in catalog}
    selected = _select_report_session(
        tuple(entry.picker_entry for entry in catalog),
        kind="sever",
        title="MEM REVIEW · SEVER REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    session = reload_selected_sever_session(sessions, by_key[selected.key])
    if session.state != "APPLIED":
        raise ReviewError(
            "Sever execution is not complete. Resume it with 'mem sever'; "
            "Review opens only terminal application evidence."
        )
    _show_operation_review(sever_review_report(session), snapshot=snapshot)


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


def _run_atomize_workbench(
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
    """Resume the Context-bound atomize workbench compatibility adapter."""
    from memcommit.adapters.console.commands.atomize.sessions import (
        atomize_application_checkpoint_uid,
        revalidate_saved_atomize_analysis,
    )

    if expected_analysis_uid is not None:
        from memcommit.adapters.console.commands.atomize.sessions import (
            load_saved_atomize_analysis,
        )

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
        # read-only receipt so Review says APPLIED without creating a second
        # session owner or repairing persistence as a side effect of reading.
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
        from memcommit.application.operations.review.report_adapters import atomize_review_report

        _show_operation_review(
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
        from memcommit.adapters.console.commands.review.report import render_review_report_snapshot
        from memcommit.application.operations.review.report_adapters import atomize_review_report

        typer.echo(
            render_review_report_snapshot(
                atomize_review_report(analysis, workbench).report()
            )
        )
        return
    if snapshot or not sys.stdin.isatty() or not sys.stdout.isatty():
        from memcommit.adapters.console.commands.review.report import render_review_report_snapshot
        from memcommit.application.operations.review.report_adapters import atomize_review_report

        typer.echo(
            render_review_report_snapshot(
                atomize_review_report(analysis, workbench).report()
            )
        )
        return
    from memcommit.adapters.console.commands.review.report import run_review_report_shell
    from memcommit.application.resolution.workbench import ResolutionNavigation
    from memcommit.application.operations.review.report_adapters import atomize_review_report

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


def cmd(
    kind: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Open a review report (audit, compare, meld, sever, update, "
                "atomize, dedun, distill, elaborate, forget, resolve, or "
                "ambiguities); "
                "omit to enter the interactive Review session"
            )
        ),
    ] = None,
    session_uid: Annotated[
        Optional[str],
        typer.Option(
            "--session",
            help="Saved operation artifact uid or unambiguous prefix",
        ),
    ] = None,
    receipt_uid: Annotated[
        Optional[str],
        typer.Option(
            "--receipt",
            help="Exact or unambiguous applied checkpoint uid",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to review (defaults to current)",
        ),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the current review frame without opening the TUI",
        ),
    ] = False,
    replace_review: Annotated[
        bool,
        typer.Option(
            "--new",
            "--replace-review",
            help=(
                "Start a new adapter review; --replace-review remains a "
                "compatibility alias"
            ),
        ),
    ] = False,
    respond_to: Annotated[
        Optional[str],
        typer.Option(
            "--respond-to",
            help=(
                "Visible issue number or unique issue/source uid prefix to "
                "annotate without opening the TUI"
            ),
        ),
    ] = None,
    response: Annotated[
        Optional[str],
        typer.Option(
            "--response",
            help="Context/comment saved for --respond-to; an empty value clears",
        ),
    ] = None,
) -> None:
    """Inspect terminal evidence or saved reports without applying Memories."""
    store = MemoryStore()
    retained_review_source = False
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        canonical_context_name = (
            None if context_name is None else context_snapshot.resolve(context_name)
        )
        normalized_kind = kind.casefold() if kind is not None else None
        if session_uid is not None and receipt_uid is not None:
            raise ReviewError("Use either --session or --receipt, not both.")
        selected_session_uid = session_uid
        launcher_receipt = None
        if (
            kind is None
            and session_uid is None
            and receipt_uid is None
            and context_name is None
            and not snapshot
            and not replace_review
            and respond_to is None
            and response is None
            and _interactive_terminal()
        ):
            launcher_receipt = choose_review_session(store)
            if launcher_receipt is None:
                typer.echo("Review selection cancelled.")
                return
            normalized_kind = launcher_receipt.kind
            selected_session_uid = launcher_receipt.key
        if normalized_kind in CHECKPOINT_REVIEW_OPERATIONS:
            if launcher_receipt is None and session_uid is not None:
                raise ReviewError(
                    "Applied checkpoint Review uses --receipt, not --session."
                )
            if (
                replace_review
                or context_name is not None
                or respond_to is not None
                or response is not None
            ):
                raise ReviewError(
                    "Applied checkpoint Review uses --receipt and --snapshot only."
                )
            _run_checkpoint_report(
                store,
                operation=normalized_kind,
                receipt_uid=(
                    selected_session_uid
                    if launcher_receipt is not None
                    else receipt_uid
                ),
                snapshot=snapshot,
            )
            return
        if normalized_kind == "audit":
            if (
                replace_review
                or context_name is not None
                or respond_to is not None
                or response is not None
            ):
                raise ReviewError(
                    "Saved Audit Review uses --session and --snapshot only."
                )
            _run_audit_review(
                store,
                session_uid=selected_session_uid,
                snapshot=snapshot,
            )
            return
        if normalized_kind in {"compare", "meld", "sever", "update"}:
            if replace_review or respond_to is not None or response is not None:
                raise ReviewError(
                    "Adaptive operation reports do not use --replace-review or "
                    "--respond-to. Review actions remain operation-owned."
                )
            runners = {
                "compare": _run_compare_report,
                "meld": _run_meld_report,
                "sever": _run_sever_report,
                "update": _run_update_report,
            }
            runners[normalized_kind](
                store,
                session_uid=selected_session_uid,
                snapshot=snapshot,
            )
            return
        if normalized_kind == "atomize":
            if launcher_receipt is None and session_uid is not None:
                raise ReviewError(
                    "Atomize Review is Context-bound; use --context instead of "
                    "--session."
                )
            _run_atomize_workbench(
                store=store,
                context_name=canonical_context_name,
                current_name=context_snapshot.current_name,
                snapshot=snapshot,
                replace=replace_review,
                respond_to=respond_to,
                response=response,
                expected_analysis_uid=(
                    selected_session_uid if launcher_receipt is not None else None
                ),
            )
            return
        if normalized_kind == SAVED_REVIEW_KIND:
            if launcher_receipt is None:
                raise ReviewError("Unsupported review adapter.")
            assert selected_session_uid is not None
            session = _load_saved_review_by_selector(
                store,
                selected_session_uid,
            )
            active_review = store.load_review_session()
            retained_review_source = (
                active_review is None or active_review.uid != session.uid
            )
            ctx = (
                store.load_review_session_source(session.uid)
                if retained_review_source
                else store.load_direct(session.context_name)
            )
        elif normalized_kind is None:
            if session_uid is not None or receipt_uid is not None:
                raise ReviewError(
                    "--session or --receipt requires an explicit review kind."
                )
            if replace_review:
                raise ReviewError(
                    "--replace-review is valid only when starting an adapter."
                )
            session = store.load_review_session()
            if session is None:
                _run_atomize_workbench(
                    store=store,
                    context_name=canonical_context_name,
                    current_name=context_snapshot.current_name,
                    snapshot=snapshot,
                    replace=False,
                    respond_to=respond_to,
                    response=response,
                )
                return
            if (
                canonical_context_name is not None
                and canonical_context_name != session.context_name
            ):
                raise ReviewError("The saved review belongs to a different Context.")
            ctx = store.load_direct(session.context_name)
        else:
            if normalized_kind not in {
                "ambiguity",
                "ambiguities",
            }:
                raise ReviewError(
                    "Unsupported review adapter. "
                    "Implemented adapters are 'ambiguities', 'atomize', "
                    "'audit', 'compare', 'dedun', 'distill', 'elaborate', "
                    "'forget', 'meld', 'resolve', 'sever', and 'update'."
                )
            if session_uid is not None:
                if replace_review:
                    raise ReviewError("--new cannot be combined with --session.")
                session = _load_saved_review_by_selector(store, session_uid)
                if session.kind != "ambiguities":
                    raise ReviewError(
                        "The selected Review session is not an ambiguity review."
                    )
                active_review = store.load_review_session()
                retained_review_source = (
                    active_review is None or active_review.uid != session.uid
                )
                ctx = (
                    store.load_review_session_source(session.uid)
                    if retained_review_source
                    else store.load_direct(session.context_name)
                )
            else:
                ctx = _load_direct_context(
                    store,
                    canonical_context_name,
                    current_name=context_snapshot.current_name,
                )
                # --new is also the recovery path for malformed legacy state,
                # so it deliberately avoids parsing the prior singleton.
                existing = None if replace_review else store.load_review_session()
                exact_resume = (
                    existing is not None
                    and existing.kind == "ambiguities"
                    and review_matches_context(existing, ctx)
                )
                if exact_resume:
                    session = existing
                else:
                    if (
                        existing is not None
                        and not existing.terminal
                        and not replace_review
                    ):
                        raise ReviewError(
                            "An unfinished saved review already exists. Resume it "
                            "with 'mem review', or explicitly start new work with "
                            f"'mem review {normalized_kind} --new'."
                        )
                    with CommandProgress(
                        "REVIEW AMBIGUITIES",
                        "analyzing direct memories",
                        total=1,
                    ):
                        report = ops.find_ambiguities(
                            ctx,
                            connect_codex_chatgpt_provider,
                        )
                    session = create_ambiguity_review(ctx, report)
                    # The semantic report and its source snapshot are durable
                    # before terminal control begins. Saving a distinct review
                    # archives terminal predecessor evidence by UID.
                    store.save_review_session(session)
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        FindingsError,
        AtomizeImpactError,
        AtomizeWorkbenchError,
        QueryProviderError,
        QualityAuditError,
        ReviewError,
    ) as error:
        typer.secho(
            f"Review error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        analysis = (
            store.load_atomize_analysis(ctx.uid) if session.kind == "atomize" else None
        )
    except (OSError, RuntimeError, ValueError) as error:
        typer.secho(
            f"Review error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    matches_source = retained_review_source or (
        atomize_review_matches_analysis(session, ctx, analysis)
        if session.kind == "atomize" and analysis is not None
        else (
            review_matches_context(session, ctx)
            if session.kind == "ambiguities"
            else False
        )
    )
    if not matches_source:
        restart = (
            "mem review atomize --replace-review"
            if session.kind == "atomize"
            else "mem review ambiguities --replace-review"
        )
        typer.secho(
            "Review error: the saved review is stale because its Context "
            "or source analysis changed. Start a new review with "
            f"'{restart}'.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if (respond_to is None) != (response is None):
        typer.secho(
            "Review error: --respond-to and --response must be used together.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if retained_review_source and respond_to is not None:
        typer.secho(
            "Review error: retained terminal Review history is read-only.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if respond_to is not None:
        selector = respond_to.strip()
        ordered = session.ordered_items()
        selected_index = visible_ordinal_index(selector, len(ordered))
        if selected_index is not None:
            matches = [ordered[selected_index]]
        else:
            matches = [item for item in session.items if item.uid.startswith(selector)]
        if not selector or len(matches) != 1:
            typer.secho(
                "Review error: the response target is missing or ambiguous. "
                "Use its visible 1-based issue number or a unique uid prefix.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        session.cursor_uid = matches[0].uid
        session.response_for(matches[0].uid).text = response or ""
        try:
            store.save_review_session(session)
        except (OSError, ValueError) as error:
            typer.secho(
                f"Review error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(render_review_snapshot(session, ctx))
        return

    if snapshot or not session.items:
        typer.echo(render_review_snapshot(session, ctx))
        return

    try:
        run_review_shell(
            session,
            ctx,
            save=store.save_review_session,
            read_only=retained_review_source,
        )
    except ReviewCancelled:
        typer.echo("Review saved. No Memory changes applied.")
        return
    except (OSError, ValueError) as error:
        typer.secho(
            f"Review error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Review saved: {session.answered_count}/{len(session.items)} items answered.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo("No Memory changes applied. No checkpoint created.")
