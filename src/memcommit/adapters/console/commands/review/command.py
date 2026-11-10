"""Open operation-owned Review reports and completed evidence."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.application.operations.atomize.domain import AtomizeImpactError
from memcommit.application.operations.atomize.records import AtomizeRecordError
from memcommit.adapters.console.commands.atomize.review import (
    open_atomize_review as _run_atomize_workbench,
)
from memcommit.adapters.console.commands.compare.review import (
    open_compare_review as _run_compare_report,
)
from memcommit.adapters.console.commands.sever.review import (
    open_sever_review as _run_sever_report,
)
from memcommit.application.operations.review.applied_checkpoint import (
    CHECKPOINT_REVIEW_OPERATIONS,
    list_applied_checkpoint_reviews,
    select_applied_checkpoint_review,
)
from memcommit.adapters.console.commands.review.applied_checkpoint_report import (
    applied_checkpoint_review_controller,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionPickerEntry,
)
from memcommit.adapters.console.commands.review.report import (
    show_operation_review as _show_operation_review,
)
from memcommit.adapters.console.commands.review.sessions import (
    choose_review_session,
    select_report_session as _select_report_session,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.review.model import ReviewError
from memcommit.persistence.store import ProfileStore


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _checkpoint_report_entries(
    store: ProfileStore,
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
    store: ProfileStore,
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


def _show_audit_review_scope() -> None:
    # TODO(audit-review): Load a saved Audit record and reuse
    # audit.receipt.render_quality_audit_receipt. Review owns reopening;
    # Audit owns receipt formatting. Never rerun checks or connect a provider.
    typer.echo(
        "REVIEW AUDIT · NOT IMPLEMENTED\n"
        "Planned: saved Audit record → the same completion receipt as mem audit.\n"
        "Show Source, completed checks, and findings.\n"
        "Read-only receipt; no new Audit, decisions, or Apply."
    )


def _show_merge_review_scope() -> None:
    """Describe deferred Merge receipt Review without opening a saved record."""
    # TODO(merge-review): Validate a saved Merge checkpoint and reconstruct its
    # completion receipt using Merge's receipt renderer. Keep this adapter here;
    # do not rerun analysis, resume a session, or apply the recorded work again.
    typer.echo(
        "REVIEW MERGE · NOT IMPLEMENTED\n"
        "Planned: saved Merge checkpoint → completion receipt.\n"
        "Show method, Source/Target note counts, applied decisions, "
        "and unresolved issues.\n"
        "Read-only receipt; no analysis, session resume, or Apply."
    )


def cmd(
    kind: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Open a saved report or completed evidence (compare, sever, atomize, "
                "distill, makemore, or conflict); audit and merge show their "
                "planned receipt-review scope; omit to browse Review records"
            )
        ),
    ] = None,
    session_uid: Annotated[
        Optional[str],
        typer.Option(
            "--session", help="Saved operation artifact uid or unambiguous prefix"
        ),
    ] = None,
    receipt_uid: Annotated[
        Optional[str],
        typer.Option("--receipt", help="Exact or unambiguous applied checkpoint uid"),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option("--context", "-c", help="Context to review (defaults to current)"),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot", help="Print the current review frame without opening the TUI"
        ),
    ] = False,
) -> None:
    """Inspect terminal evidence or saved reports without applying Memories."""
    normalized_kind = kind.casefold() if kind is not None else None
    supported = {
        "atomize",
        "compare",
        "sever",
        "audit",
        "merge",
        *CHECKPOINT_REVIEW_OPERATIONS,
    }
    if normalized_kind is not None and normalized_kind not in supported:
        raise typer.BadParameter(
            "Unsupported review adapter. Choose atomize, compare, sever, audit, "
            "merge, distill, makemore, or conflict."
        )
    if normalized_kind in {"audit", "merge"}:
        if (
            session_uid is not None
            or receipt_uid is not None
            or context_name is not None
            or snapshot
        ):
            raise typer.BadParameter(
                f"{normalized_kind.title()} Review is not implemented; "
                f"run 'mem review {normalized_kind}' without options to see the planned scope."
            )
        if normalized_kind == "audit":
            _show_audit_review_scope()
        else:
            _show_merge_review_scope()
        return
    store = ProfileStore()
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
            and _interactive_terminal()
        ):
            launcher_receipt = choose_review_session(store)
            if launcher_receipt is None:
                annotate_command_outcome("CANCELLED")
                typer.echo("Review selection cancelled.")
                return
            normalized_kind = launcher_receipt.kind
            selected_session_uid = launcher_receipt.key
        if normalized_kind in CHECKPOINT_REVIEW_OPERATIONS:
            if launcher_receipt is None and session_uid is not None:
                raise ReviewError(
                    "Applied checkpoint Review uses --receipt, not --session."
                )
            if context_name is not None:
                raise ReviewError(
                    "Applied checkpoint Review uses --receipt and --snapshot only."
                )
            _run_checkpoint_report(
                store,
                operation=normalized_kind,
                receipt_uid=selected_session_uid
                if launcher_receipt is not None
                else receipt_uid,
                snapshot=snapshot,
            )
            return
        if normalized_kind in {"compare", "sever"}:
            runners = {"compare": _run_compare_report, "sever": _run_sever_report}
            runners[normalized_kind](
                store, session_uid=selected_session_uid, snapshot=snapshot
            )
            return
        if normalized_kind is None:
            if session_uid is not None or receipt_uid is not None:
                raise ReviewError(
                    "--session or --receipt requires an explicit review kind."
                )
        elif normalized_kind != "atomize":
            raise ReviewError("Unsupported review adapter.")
        if selected_session_uid is not None and context_name is not None:
            raise ReviewError(
                "Atomize Review accepts either --session or --context, not both."
            )
        if receipt_uid is not None:
            raise ReviewError(
                "Atomize Review selects an analysis with --session, not --receipt."
            )
        _run_atomize_workbench(
            store=store,
            context_name=canonical_context_name,
            current_name=context_snapshot.current_name,
            snapshot=snapshot,
            expected_analysis_uid=selected_session_uid,
        )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        AtomizeImpactError,
        AtomizeRecordError,
    ) as error:
        typer.secho(
            f"Review error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
