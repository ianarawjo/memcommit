"""Create or resume the shared terminal shell for semantic review."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.atomize.domain import AtomizeImpactError
from memcommit.application.operations.atomize.records import AtomizeRecordError
from memcommit.adapters.console.commands.atomize.review import (
    open_atomize_review as _run_atomize_workbench,
)
from memcommit.adapters.console.commands.audit.review import (
    open_audit_review as _run_audit_review,
)
from memcommit.adapters.console.commands.compare.review import (
    open_compare_review as _run_compare_report,
)
from memcommit.adapters.console.commands.meld.review import (
    open_meld_review as _run_meld_report,
)
from memcommit.adapters.console.commands.sever.review import (
    open_sever_review as _run_sever_report,
)
from memcommit.adapters.console.commands.update.review import (
    open_update_review as _run_update_report,
)
from memcommit.application.operations.review.applied_checkpoint import (
    CHECKPOINT_REVIEW_OPERATIONS,
    list_applied_checkpoint_reviews,
    select_applied_checkpoint_review,
)
from memcommit.adapters.console.commands.review.applied_checkpoint_report import (
    applied_checkpoint_review_controller,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.adapters.console.commands.review.snapshot import (
    render_review_snapshot,
    visible_ordinal_index,
)
from memcommit.adapters.console.coordination.review import ReviewCancelled
from memcommit.adapters.console.commands.review.resolution_shell import (
    run_review_resolution_shell as run_review_shell,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionPickerEntry,
)
from memcommit.adapters.console.commands.review.report import (
    show_operation_review as _show_operation_review,
)
from memcommit.adapters.console.commands.review.sessions import (
    SAVED_REVIEW_KIND,
    choose_review_session,
    select_report_session as _select_report_session,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsError,
)
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.application.operations.audit.model import QualityAuditError
from memcommit.application.operations.review.model import (
    ReviewError,
    atomize_review_matches_analysis,
    create_ambiguity_review,
    review_matches_context,
)
from memcommit.persistence.store import MemoryStore
from memcommit.core.context_targeting.uid_locator import (
    UidLocatorError,
    resolve_exact_or_unique_uid,
)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


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


def cmd(
    kind: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Open a review report (audit, compare, meld, sever, update, "
                "atomize, dedun, distill, makemore, forget, resolve, or "
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
            None
            if context_name is None
            else resolve_existing_context_operand(
                freeze_local_context_operand_candidates(store),
                context_name,
                current=context_snapshot.current_name,
            ).name
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
            if replace_review or respond_to is not None or response is not None:
                raise ReviewError(
                    "Atomize Review is read-only and does not accept --new, "
                    "--respond-to, or --response."
                )
            _run_atomize_workbench(
                store=store,
                context_name=canonical_context_name,
                current_name=context_snapshot.current_name,
                snapshot=snapshot,
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
                if respond_to is not None or response is not None:
                    raise ReviewError(
                        "No active response-capable Review exists; Atomize "
                        "Review is read-only."
                    )
                _run_atomize_workbench(
                    store=store,
                    context_name=canonical_context_name,
                    current_name=context_snapshot.current_name,
                    snapshot=snapshot,
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
                    "'audit', 'compare', 'dedun', 'distill', 'makemore', "
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
        AtomizeRecordError,
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
