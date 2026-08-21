"""Run and review one durable three-finder Memory quality Audit."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Annotated, Optional

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
import typer

from memcommit.commands.command_progress import BUSY_INTERVAL_SECONDS
from memcommit.commands.command_wait import (
    CommandWaitProgress,
    run_command_wait,
)
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    GrantedReadStore,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.help_inventory import CommandEntry
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.commands.resolution_workbench_shell import (
    render_resolution_workbench_snapshot,
    run_resolution_workbench_shell,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.tui.operations.audit import choose_audit_setup
from memcommit.context import Context
from memcommit.conformance import ConformanceError, check_context_conformance
from memcommit.conformance_runtime import freeze_context_conformance
from memcommit.derived_policy import authorize_analysis_save
from memcommit.findings import FindingsError, FindingsProvider
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.quality_audit import (
    QualityAuditError,
    QualityAuditKind,
    QualityAuditSession,
    quality_audit_record_digest,
    quality_audit_resolution_view,
    create_quality_audit,
    run_quality_audit,
)
from memcommit.quality_audit_store import QualityAuditStore
from memcommit.quality_find_workbench import validate_quality_find_response
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


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
            progress.update(f"finding {kind}", step=step)

        session = run_quality_audit(
            ctx,
            provider_factory,
            on_check=update_progress,
        )
        if conformance_rules is not None:
            progress.update("checking conformance", step=4)
            frozen = freeze_context_conformance(ctx, conformance_rules)
            report = check_context_conformance(
                source_label=frozen.target_name,
                rules_label=frozen.rules_name,
                rules=frozen.rules,
                subjects=frozen.subjects,
                provider=provider_factory(),
            )
            session = create_quality_audit(
                ctx,
                session.checks,
                conformance=report,
                uid=session.uid,
                created_at=session.created_at,
            )
        return session

    return run_command_wait(
        "AUDIT",
        "finding duplicates",
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


def run_quality_audit_review(
    store: MemoryStore,
    session: QualityAuditSession,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> QualityAuditSession:
    """Resume one saved Audit response ledger without rerunning a finder."""

    sessions = QualityAuditStore(store)
    expected_digest = quality_audit_record_digest(session)
    navigation = ResolutionNavigation()
    workbench_navigation = SessionWorkbenchNavigation()

    def load_draft(item_uid: str) -> tuple[str | None, str]:
        response = session.responses.get(item_uid)
        if response is None:
            return None, ""
        return response.selected_option_uid, response.text

    def save_draft(item_uid: str, option_uid: str | None, text: str) -> None:
        nonlocal expected_digest
        validate_quality_find_response(text)
        item = quality_audit_resolution_view(session).item(item_uid)
        if option_uid is not None:
            item.option(option_uid)
        response = session.response_for(item_uid)
        response.selected_option_uid = option_uid
        response.text = text
        sessions.save(session, expected_digest=expected_digest)
        expected_digest = quality_audit_record_digest(session)

    while True:
        action = run_resolution_workbench_shell(
            lambda: quality_audit_resolution_view(session),
            navigation=navigation,
            workbench_navigation=workbench_navigation,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
            terminal_label="Interactive Memory quality Audit",
            snapshot_hint=(
                "Use 'mem review audit --session UID --snapshot' to inspect "
                "the saved Audit."
            ),
            draft_loader=load_draft,
            draft_saver=save_draft,
            response_validator=validate_quality_find_response,
            save_draft_on_close=True,
            split_viewer_items=True,
            # Audit has no whole-set provider turn or Apply route. Ask the
            # common shell to derive COMPLETE from the real capabilities
            # instead of rendering its generic empty RESOLVE ALL placeholder.
            review_and_apply=True,
        )
        if action.kind == "CLOSE":
            return session
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise QualityAuditError(f"Unsupported Audit review action '{action.kind}'.")
        save_draft(action.item_uid, action.option_uid, action.comment)


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
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact readable Context to audit (flagless TTY opens setup)",
        ),
    ] = None,
    against: Annotated[
        Optional[str],
        typer.Option(
            "--against",
            help=(
                "Optional local Rules Context; adds the shared Conformance "
                "check to this Audit"
            ),
        ),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the newly saved Audit instead of opening its review",
        ),
    ] = False,
) -> None:
    """Run quality checks and optional Rule Conformance, then save one Audit."""

    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        rules_ctx: Context | None = None
        if against is not None:
            rules_name = context_snapshot.resolve(against)
            if not store.context_exists(rules_name):
                raise ConformanceError(
                    "Audit Conformance currently requires a local Rules Context."
                )
            rules_ctx = store.load_direct(rules_name)
        if context_name is None and _interactive_terminal() and not snapshot:
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

        if rules_ctx is not None:
            # Fail structural Conformance setup before opening any of the four
            # provider turns; a bad Rules frame must not waste a partial Audit.
            freeze_context_conformance(ctx, rules_ctx)
        session = _run_quality_audit_checks(
            ctx,
            connect_codex_chatgpt_provider,
            conformance_rules=rules_ctx,
        )

        # Publish the complete three- or four-check snapshot before terminal control.
        # A PTY disconnect can lose only an unsaved composer draft, never the
        # provider result the person is about to review.
        QualityAuditStore(store).save(session, expected_digest=None)
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

    if snapshot or not _interactive_terminal():
        typer.echo(
            render_resolution_workbench_snapshot(quality_audit_resolution_view(session))
        )
        return

    try:
        run_quality_audit_review(store, session)
    except (
        ConcurrentContextUpdateError,
        OSError,
        QualityAuditError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Audit review error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.secho(
        f"Audit saved: {session.answered_count}/{session.finding_count} findings answered.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo("No Context or Memory changes applied. No checkpoint created.")
