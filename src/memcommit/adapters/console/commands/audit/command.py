"""Run and persist one durable Memory quality Audit from the console."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Annotated, Optional

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
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
from memcommit.application.capabilities.authority.access import (
    GrantedReadStore,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.adapters.console.commands.help.inventory import CommandEntry
from memcommit.core.context_targeting.readable_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.commands.audit.receipt import (
    render_quality_audit_receipt,
)
from memcommit.adapters.console.commands.audit.review import (
    render_quality_audit_review_snapshot,
)
from memcommit.adapters.console.commands.audit.setup import choose_audit_setup
from memcommit.core.context import Context
from memcommit.application.operations.conformance.model import ConformanceError
from memcommit.application.capabilities.authority.derived_policy import (
    authorize_analysis_save,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.findings import (
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
from memcommit.application.capabilities.reviewing.memory_issue_finding.report import (
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
    app_input: Input | None = None,
    app_output: Output | None = None,
    interactive: bool | None = None,
    interval: float = BUSY_INTERVAL_SECONDS,
    help_entries: Sequence[CommandEntry] | None = None,
    on_help_action: Callable[[str, str | None], None] | None = None,
) -> QualityAuditSession:
    """Run the frozen checks behind one shared transient progress line."""

    total_checks = 4 if conformance_rules is not None else 3

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
            on_conformance=lambda: progress.update(
                "checking conformance",
                step=4,
            ),
        )

    return run_command_wait(
        "AUDIT",
        "finding redundancies",
        total=total_checks,
        work=work,
        app_input=app_input,
        app_output=app_output,
        interactive=interactive,
        interval=interval,
        help_entries=help_entries,
        on_help_action=on_help_action,
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
    selected_name = choose_audit_setup(
        names,
        current=access.display_name,
        annotations=annotations,
    )
    if selected_name is None:
        return None
    selected_access = catalog.access_for(selected_name)
    # Audit retains source-derived content and provider judgments. READ alone
    # is sufficient for one-shot Find, but not for this durable artifact.
    authorize_analysis_save((selected_access,), retention="RETAINED")
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
    """Run quality checks and optional Rule Conformance, then save one Audit."""

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
            rules_name = context_snapshot.resolve(rules_operands[0])
            if not store.context_exists(rules_name):
                raise ConformanceError(
                    "Audit Conformance currently requires a local Rules Context."
                )
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
            canonical_name = (
                None if context_name is None else context_snapshot.resolve(context_name)
            )
            access = resolve_context_access(
                store,
                canonical_name,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            )
            authorize_analysis_save((access,), retention="RETAINED")
            ctx = (
                GrantedReadStore(access).load_direct(access.display_name)
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
