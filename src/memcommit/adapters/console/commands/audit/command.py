"""Run and persist one durable Memory quality Audit from the console."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.terminal.components.progress import (
    BUSY_INTERVAL_SECONDS,
)
from memcommit.adapters.console.terminal.components.command_wait import (
    CommandWaitProgress,
    run_command_wait,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.application.context_access.access import (
    GrantedReadStore,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.commands.audit.receipt import (
    render_quality_audit_receipt,
)
from memcommit.adapters.console.commands.audit.review import (
    render_quality_audit_review_snapshot,
)
from memcommit.adapters.console.commands.audit.audit_endpoint_setup_screen import (
    run_audit_endpoint_setup_screen,
)
from memcommit.core.context import Context
from memcommit.application.operations.check_conformance.model import ConformanceError
from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsError,
    FindingsProvider,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.audit.application import (
    record_quality_audit,
    run_quality_audit,
)
from memcommit.application.operations.audit.model import (
    QualityAuditError,
    QualityAuditKind,
    QualityAuditSession,
)
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.application.capabilities.memory_issue_analysis.report import (
    quality_find_category_label,
)
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


def _run_quality_audit_checks(
    ctx: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    conformance_rules: Context | None = None,
    interactive: bool | None = None,
    interval: float = BUSY_INTERVAL_SECONDS,
) -> QualityAuditSession:
    """Run the frozen checks behind one shared transient progress line."""

    fit_enabled = len(ctx.memories) >= 2
    total_checks = 3 + int(fit_enabled) + int(conformance_rules is not None)

    def work(progress: CommandWaitProgress) -> QualityAuditSession:
        def update_progress(kind: QualityAuditKind, step: int, _total: int) -> None:
            progress.update(
                f"finding {quality_find_category_label(kind).casefold()}",
                step=step,
            )

        return run_quality_audit(
            ctx,
            provider_factory,
            conformance_rules=conformance_rules,
            on_check=update_progress,
            on_fit=(
                lambda: progress.update("checking whole-Context Fit", step=4)
                if fit_enabled
                else None
            ),
            on_conformance=lambda: progress.update(
                "checking conformance",
                step=4 + int(fit_enabled),
            ),
        )

    return run_command_wait(
        "AUDIT",
        "finding redundancies",
        total=total_checks,
        work=work,
        interactive=interactive,
        interval=interval,
    )


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _interactive_source(store: MemoryStore, *, current_name: str | None):
    access = resolve_context_access(
        store,
        None,
        current_name=current_name,
        required_permission="READ",
    )
    catalog = freeze_profile_readable_context_catalog(
        store,
        access,
        include_query_routes=False,
    )
    names = tuple(catalog.list_context_names())
    annotations = {
        name: context_access_display_facts(catalog.access_for(name))
        for name in names
        if catalog.access_for(name).is_granted
    }
    selected_name = run_audit_endpoint_setup_screen(
        names,
        current=access.access_name,
        annotations=annotations,
    )
    if selected_name is None:
        return None
    selected_access = catalog.access_for(selected_name)
    return selected_access, catalog.load_direct(selected_name)


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT",
            help="Exact readable Context to audit (defaults to current)",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact readable Context to audit (defaults to current)",
        ),
    ] = None,
    against: Annotated[
        Optional[list[str]],
        typer.Option(
            "--against",
            "--rule",
            metavar="RULES_CONTEXT",
            help=(
                "Optional local Rules Context; --against and --rule are "
                "equivalent and add the shared Conformance check"
            ),
        ),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the complete newly saved Audit instead of its receipt",
        ),
    ] = False,
    select_source: Annotated[
        bool,
        typer.Option(
            "--select",
            help="Choose one readable Source Context interactively",
        ),
    ] = False,
) -> None:
    """Run quality checks, whole-Context Fit, and optional Rule Conformance."""

    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
    except ValueError as error:
        typer.secho(
            "Audit error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        if select_source and context_name is not None:
            raise QualityAuditError(
                "--select cannot be combined with an explicit Context."
            )
        if select_source and not _interactive_terminal():
            raise QualityAuditError("--select requires an interactive terminal.")
        rules_ctx: Context | None = None
        rules_operands = tuple(against or ())
        if len(rules_operands) > 1:
            raise QualityAuditError(
                "Use only one of --against or --rule; they are aliases for "
                "the Rules Context."
            )
        if rules_operands:
            rules_name = resolve_existing_context_operand(
                freeze_local_context_operand_candidates(store),
                rules_operands[0],
                current=context_snapshot.current_name,
            ).name
            rules_ctx = store.load_direct(rules_name)
        if select_source:
            selected = _interactive_source(
                store,
                current_name=context_snapshot.current_name,
            )
            if selected is None:
                typer.echo("Audit cancelled.")
                return
            selected_access, ctx = selected
            if rules_ctx is not None and selected_access.is_granted:
                raise ConformanceError(
                    "Audit Conformance currently requires a local Target Context."
                )
        else:
            access = resolve_existing_context_access(
                store,
                context_name,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            ).value
            ctx = (
                GrantedReadStore(access).load_direct(access.access_name)
                if access.is_granted
                else store.load_direct(access.context_name)
            )
            if rules_ctx is not None and access.is_granted:
                raise ConformanceError(
                    "Audit Conformance currently requires a local Target Context."
                )

        session = _run_quality_audit_checks(
            ctx,
            connect_codex_chatgpt_provider,
            conformance_rules=rules_ctx,
        )

        # Publish the complete snapshot before printing its receipt. Review is
        # a separate command, so a terminal disconnect cannot lose the result.
        record_quality_audit(JsonAuditRecordRepository(store), session)
    except (
        ConcurrentContextUpdateError,
        ConformanceError,
        FileNotFoundError,
        FindingsError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QualityAuditError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Audit error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if snapshot:
        typer.echo(render_quality_audit_review_snapshot(session))
        return
    render_quality_audit_receipt(session)
