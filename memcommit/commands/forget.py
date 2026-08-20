import sys
from typing import Annotated, Optional

import typer

from memcommit.command_attempts import annotate_command_outcome
from memcommit.commands.command_wait import (
    CommandWaitView,
    build_report_loading_view,
    run_command_wait,
)
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.context import Context
from memcommit.forget_application import (
    ForgetAnalysisRequest,
    ForgetApplyRequest,
    ForgetRevisionRequest,
    ForgetSessionSnapshot,
    ForgetSourcePort,
    FrozenForgetSource,
    prepare_forget_snapshot,
    run_forget_analysis,
    run_forget_apply,
    run_forget_revision,
)
from memcommit.forget_runtime import (
    MemoryStoreForgetSourcePort,
    connect_forget_provider,
)
from memcommit.interfaces.tui.operations.forget import (
    choose_forget_setup,
    run_forget_review_workbench,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import CodexChatGPTProvider, QueryProviderError
from memcommit.semantic.changes import EditChange, RemoveChange, ProposedChange
from memcommit.store import MemoryStore


def connect_codex_chatgpt_provider() -> CodexChatGPTProvider:
    """Compatibility name for Forget's infrastructure-owned provider factory."""

    return connect_forget_provider()


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _forget_analysis_stage(ctx: Context) -> str:
    """Describe the one honest blocking boundary without implying percent progress."""

    return f"analyzing {len(ctx.memories)} source memories x 1 instruction"


def _forget_wait_view(ctx: Context, info: str) -> CommandWaitView:
    """Show the reviewed input because no Forget report exists pre-analysis."""

    text = "\n".join(
        [
            "MEM FORGET · FROZEN INPUT · RESULT PENDING",
            "",
            f"SOURCE · {safe_terminal_text(ctx.name)} · THIS CONTEXT ONLY",
            f"FROZEN MEMORIES · {len(ctx.memories)}",
            "SOURCE STATE · UNCHANGED",
            "",
            "INSTRUCTION",
            safe_terminal_text(info),
            "",
            "The review report will replace this setup after the provider returns.",
        ]
    )
    return CommandWaitView(title="FORGET CONFIRMED INPUTS · READ-ONLY", text=text)


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
    info = request.instruction
    result = run_command_wait(
        "FORGET",
        _forget_analysis_stage(ctx),
        total=1,
        work=lambda _progress: run_forget_analysis(
            request,
            source_port=source_port,
            provider_factory=provider_factory,
        ),
        return_view=build_report_loading_view(
            "FORGET",
            sections=("What mem understood", "Review decisions", "To do"),
        ),
        context_view=_forget_wait_view(ctx, info),
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


def _print_proposals(proposals: list[ProposedChange], query: str) -> None:
    typer.echo()
    typer.secho(f'Proposed changes for "{query}"', bold=True)
    typer.echo("-" * 56)
    if not proposals:
        typer.secho("  (no changes proposed - nothing matched)", dim=True)
        typer.echo("-" * 56)
        return

    for i, change in enumerate(proposals, 1):
        if isinstance(change, RemoveChange):
            typer.secho(f'  {i}  REMOVE  [{change.uid[:8]}]  "{change.content}"', fg=typer.colors.RED, bold=True)
            typer.secho(f"       Reason: {change.reason}", dim=True)
        elif isinstance(change, EditChange):
            typer.secho(f'  {i}  EDIT    [{change.uid[:8]}]  "{change.old_content}"', fg=typer.colors.YELLOW, bold=True)
            typer.secho(f'         -> "{change.new_content}"', fg=typer.colors.GREEN)
            typer.secho(f"       Reason: {change.reason}", dim=True)
        typer.echo()

    typer.echo("-" * 56)


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
    info = request.instruction
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
    snapshot = result.snapshot

    while True:
        proposals = snapshot.review.changes()
        _print_proposals(proposals, info)

        if not proposals:
            typer.echo("Nothing to apply.")
            return snapshot

        n = len(proposals)
        label = "change" if n == 1 else "changes"
        typer.echo(f"Apply {'this' if n == 1 else 'these'} {n} {label}?")
        typer.secho("  y = apply    n = abort    r = revise with feedback", dim=True)
        decision = typer.prompt(">", default="", show_default=False).strip()

        if decision.lower() in ("y", "yes"):
            return snapshot

        if decision.lower() in ("n", "no"):
            typer.echo("Aborted - no changes made.")
            return None

        feedback = decision if not decision.lower().startswith("r") else ""
        if not feedback:
            feedback = typer.prompt("Describe what to change", default="", show_default=False).strip()
        if not feedback:
            continue

        typer.secho("Revising with the configured Forget provider...", dim=True)
        snapshot = run_forget_revision(
            ForgetRevisionRequest(snapshot=snapshot, feedback=feedback),
            provider_factory=provider_factory,
        )


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
    source_locator: str | None = None
    try:
        context_snapshot = ContextOperandSnapshot.capture(active_store)
        if info is None:
            access = resolve_context_access(
                active_store,
                None,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            )
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
        if _interactive_terminal():
            typer.echo(
                "Forget complete · SOURCE "
                f"{safe_terminal_text(apply_receipt.source_name)} · "
                "no changes needed · Context unchanged · no checkpoint"
            )
        return

    effects: list[str] = []
    if apply_receipt.removed_count:
        effects.append(f"{apply_receipt.removed_count} removed")
    if apply_receipt.edited_count:
        effects.append(f"{apply_receipt.edited_count} edited")
    if _interactive_terminal():
        checkpoint_label = (
            f" · checkpoint [{apply_receipt.checkpoint_uid[:8]}]"
            if apply_receipt.checkpoint_uid is not None
            else ""
        )
        recovery_label = (
            " · recovery mem undo" if apply_receipt.undo_available else ""
        )
        typer.secho(
            "Forget applied · SOURCE "
            f"{safe_terminal_text(apply_receipt.source_name)} · "
            f"{', '.join(effects)}{checkpoint_label}{recovery_label}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(f"Done: {', '.join(effects)}.", fg=typer.colors.GREEN)
