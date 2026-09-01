import sys
from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.coordination.context_operand import ContextOperandSnapshot
from memcommit.application.context_access.access import (
    context_access_display_facts,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.adapters.console.commands.forget.receipt import render_forget_change_lines
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.core.context import Context
from memcommit.application.operations.forget.application import (
    ForgetAnalysisRequest,
    ForgetApplyRequest,
    ForgetSessionSnapshot,
    ForgetSourcePort,
    FrozenForgetSource,
    prepare_forget_snapshot,
    run_forget_analysis,
    run_forget_apply,
)
from memcommit.application.operations.forget.runtime import (
    MemoryStoreForgetSourcePort,
    connect_forget_provider,
)
from memcommit.adapters.console.commands.forget.setup import choose_forget_setup
from memcommit.adapters.console.commands.forget.workbench import (
    run_forget_review_workbench,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.types import SemanticProvider
from memcommit.providers.subscription import QueryProviderError
from memcommit.application.capabilities.semantic.changes import ProposedChange
from memcommit.persistence.store import MemoryStore


def connect_codex_chatgpt_provider() -> SemanticProvider:
    """Compatibility name for Forget's infrastructure-owned provider factory."""

    return connect_forget_provider()


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _forget_analysis_stage(ctx: Context) -> str:
    """Describe the one honest blocking boundary without implying percent progress."""

    return f"analyzing {len(ctx.memories)} source memories x 1 instruction"


class _FrozenContextForgetSourcePort:
    """Compatibility port for historical in-memory controller tests."""

    def __init__(self, context: Context) -> None:
        self.source = FrozenForgetSource(
            context=context,
            display_name=context.name,
            granted=False,
            _runtime_token=self,
        )

    def freeze(self, _request: ForgetAnalysisRequest) -> FrozenForgetSource:
        return self.source

    def apply(self, *_args, **_kwargs):
        raise RuntimeError("The in-memory Forget compatibility port cannot Apply.")


def _run_resolution_forget_snapshot(
    source_port: ForgetSourcePort,
    request: ForgetAnalysisRequest,
    provider_factory,
    *,
    mutates_granted_authority: bool = False,
) -> ForgetSessionSnapshot | None:
    # Forget remains one whole-frame provider turn. Only its host execution is
    # moved off the foreground so Help can be explored without partitioning or
    # changing the semantic request.
    source = source_port.freeze(request)
    ctx = source.context
    result = run_command_wait(
        "FORGET",
        _forget_analysis_stage(ctx),
        total=1,
        work=lambda _progress: run_forget_analysis(
            request,
            source_port=source_port,
            provider_factory=provider_factory,
        ),
    )
    return run_forget_review_workbench(
        result.snapshot,
        mutates_granted_authority=mutates_granted_authority,
    )


def _run_resolution_forget(
    source_port: MemoryStoreForgetSourcePort | Context,
    request: ForgetAnalysisRequest | str,
    provider_factory,
    *,
    mutates_granted_authority: bool = False,
) -> ForgetSessionSnapshot | list[ProposedChange] | None:
    """Run the current typed controller or adapt the historical test signature."""

    if isinstance(source_port, Context):
        if not isinstance(request, str):
            raise TypeError("Legacy Forget controller requires an instruction.")
        context = source_port
        port = _FrozenContextForgetSourcePort(context)
        typed_request = ForgetAnalysisRequest(context.name, request)
        provider = provider_factory

        def legacy_provider_factory():
            return provider

        snapshot = _run_resolution_forget_snapshot(
            port,
            typed_request,
            legacy_provider_factory,
            mutates_granted_authority=mutates_granted_authority,
        )
        return None if snapshot is None else snapshot.review.changes()
    if not isinstance(request, ForgetAnalysisRequest):
        raise TypeError("Forget controller requires a typed analysis request.")
    return _run_resolution_forget_snapshot(
        source_port,
        request,
        provider_factory,
        mutates_granted_authority=mutates_granted_authority,
    )


def _run_interactive_forget_snapshot(
    source_port: ForgetSourcePort,
    request: ForgetAnalysisRequest,
    provider_factory,
    *,
    mutates_granted_authority: bool = False,
) -> ForgetSessionSnapshot | list[ProposedChange] | None:
    if _interactive_terminal():
        return _run_resolution_forget(
            source_port,
            request,
            provider_factory,
            mutates_granted_authority=mutates_granted_authority,
        )
    source = source_port.freeze(request)
    ctx = source.context
    typer.secho("Consulting the configured Forget provider...", dim=True)
    # The shared wait is intentionally silent outside a TTY, preserving the
    # stable redirected output while keeping one orchestration path.
    result = run_command_wait(
        "FORGET",
        _forget_analysis_stage(ctx),
        total=1,
        work=lambda _progress: run_forget_analysis(
            request,
            source_port=source_port,
            provider_factory=provider_factory,
        ),
    )
    # An explicit non-interactive invocation already expresses Apply intent.
    # Provider decisions remain internal staging and flow directly into the
    # atomic mutation; detailed evidence is available from the receipt Review.
    return result.snapshot


def _run_interactive_forget(
    source_port: MemoryStoreForgetSourcePort | Context,
    request: ForgetAnalysisRequest | str,
    provider_factory,
    *,
    mutates_granted_authority: bool = False,
) -> ForgetSessionSnapshot | list[ProposedChange] | None:
    """Preserve the historical command hook while entering typed use cases."""

    if isinstance(source_port, Context):
        if not isinstance(request, str):
            raise TypeError("Legacy Forget execution requires an instruction.")
        context = source_port
        port = _FrozenContextForgetSourcePort(context)
        typed_request = ForgetAnalysisRequest(context.name, request)
        provider = provider_factory

        def legacy_provider_factory():
            return provider

        return _run_interactive_forget_snapshot(
            port,
            typed_request,
            legacy_provider_factory,
            mutates_granted_authority=mutates_granted_authority,
        )
    if not isinstance(request, ForgetAnalysisRequest):
        raise TypeError("Forget execution requires a typed analysis request.")
    return _run_interactive_forget_snapshot(
        source_port,
        request,
        provider_factory,
        mutates_granted_authority=mutates_granted_authority,
    )


def cmd(
    info: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Description of Memories to forget; omit in a terminal to "
                "enter an instruction and select one direct Source"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            "--context",
            "-c",
            help="Direct Source Context (defaults to current)",
        ),
    ] = None,
) -> None:
    if info is None and not _interactive_terminal():
        typer.secho(
            "Forget error: INSTRUCTION is required outside a terminal. In a "
            "terminal, run 'mem forget' to open the interactive Forget setup.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    active_store = MemoryStore()
    source_locator: str | None = context_name
    try:
        context_snapshot = ContextOperandSnapshot.capture(active_store)
        if info is None:
            access = resolve_existing_context_access(
                active_store,
                context_name,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            ).value
            catalog = freeze_profile_readable_context_catalog(
                active_store,
                access,
                include_query_routes=False,
            )
            names = tuple(catalog.list_context_names())
            annotations = {
                name: context_access_display_facts(catalog.access_for(name))
                for name in names
                if catalog.access_for(name).is_granted
            }
            setup_receipt = choose_forget_setup(
                names,
                current=access.display_name,
                annotations=annotations,
            )
            if setup_receipt is None:
                annotate_command_outcome("CANCELLED")
                typer.echo("Forget cancelled.")
                return
            # The receipt is already canonical in the frozen public catalog.
            # The runtime revalidates its exact local/Grant binding before any
            # provider construction instead of trusting selection visibility.
            source_locator = setup_receipt.context_name
            info = setup_receipt.instruction
        assert info is not None
        request = ForgetAnalysisRequest(
            source_locator=source_locator,
            instruction=info,
        )
        source_port = MemoryStoreForgetSourcePort(
            active_store,
            current_name=context_snapshot.current_name,
        )
        source = source_port.freeze(request)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        provider = connect_codex_chatgpt_provider()
        reviewed = _run_interactive_forget(
            source.context,
            info,
            provider,
            mutates_granted_authority=source.granted,
        )
    except (OSError, QueryProviderError, RuntimeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if reviewed is None:
        annotate_command_outcome("CANCELLED")
        if _interactive_terminal():
            typer.echo(
                "Forget cancelled · SOURCE "
                f"{safe_terminal_text(source.display_name)} · Context unchanged"
            )
        return

    try:
        reviewed_changes = (
            reviewed
            if isinstance(reviewed, list)
            else reviewed.review.changes()
        )
        snapshot = prepare_forget_snapshot(source, info, reviewed_changes)
        result = run_forget_apply(
            ForgetApplyRequest(snapshot=snapshot),
            source_port=source_port,
        )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    apply_receipt = result.receipt
    if not result.applied:
        annotate_command_outcome("NO_CHANGE")
        typer.echo(
            "FORGET · NO CHANGE · SOURCE "
            f"{safe_terminal_text(apply_receipt.source_name)}"
        )
        typer.echo("OUTCOME · NO CHANGE · Context unchanged · no checkpoint")
        return

    typer.secho(
        "FORGET APPLIED · SOURCE "
        f"{safe_terminal_text(apply_receipt.source_name)}",
        bold=True,
    )
    typer.echo(f"FORGET · {display_escape_text(info)}")
    change_count = len(reviewed_changes)
    change_label = "CHANGE" if change_count == 1 else "CHANGES"
    typer.echo(f"DIFF · {change_count} {change_label}")
    render_forget_change_lines(reviewed_changes)
    if apply_receipt.checkpoint_uid is not None:
        typer.echo(f"RECEIPT · {apply_receipt.checkpoint_uid}")
        typer.echo(f"CHECKPOINT · {apply_receipt.checkpoint_uid}")
        if not apply_receipt.granted:
            typer.echo(
                "REVIEW · mem review forget --receipt "
                f"{apply_receipt.checkpoint_uid}"
            )
    if apply_receipt.undo_available:
        typer.echo("RECOVERY · mem undo")
    else:
        typer.echo("RECOVERY · governed by the granted authority owner")
