"""Distill evidence-bound Rules and publish an execution receipt."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.bootstrap import build_distill_console_runner
from memcommit.clipboard import write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.context_targeting.tui.picker import (
    ContextMemoryRow,
    context_memory_rows,
)
from memcommit.context_naming import validate_portable_context_name
from memcommit.distill import DistillError
from memcommit.distill_application import (
    DistillApplyRequest,
    DistillRequest,
    DistillResult,
)
from memcommit.distill_runtime import (
    apply_prepared_distill_add,
    execute_distill,
    execute_distill_apply,
    prepare_distill_add,
)
from memcommit.ground_distill import (
    FrozenGroundDistill,
    FrozenGroundWorkspaceDistill,
    execute_ground_distill,
    freeze_ground_distill,
)
from memcommit.interfaces.cli.distill import (
    distill_result_text,
    render_distill_receipt,
)
from memcommit.interfaces.cli.semantic_add import render_applied_memory_preview
from memcommit.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.distill import DistillTuiSetup
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.semantic_add_runtime import resolve_semantic_add_endpoints
from memcommit.store import MemoryStore
from memcommit.summarize import SummaryFrame


def _summary_frame_memory_rows(frame: SummaryFrame) -> tuple[ContextMemoryRow, ...]:
    """Project the exact frozen Ground evidence consumed by Distill."""

    return tuple(
        ContextMemoryRow(
            label=f"{source.context_name} · {source.memory_uid[:8]}",
            content=source.content,
            selector=source.memory_uid,
        )
        for source in frame.sources
    )


def render_distill(result: DistillResult) -> str:
    """Compatibility projection for former command-local renderer callers."""

    return distill_result_text(result)


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            hidden=True,
            help=(
                "Existing local Context to distill by canonical name or explicit "
                "relative locator (defaults to current)"
            )
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Existing Source Context (defaults to current)",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Existing Context that receives distilled Rules (defaults to current)",
        ),
    ] = None,
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            "-g",
            help="Optional Goal that focuses which supported Rules are relevant",
        ),
    ] = None,
    ground: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help="Use the exact Goal and working-candidate frame of a bound Ground",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only directly owned Memories in the selected Context",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include readable lexical descendants and embedded Contexts",
        ),
    ] = False,
    save_as: Annotated[
        Optional[str],
        typer.Option(
            "--save-as",
            hidden=True,
            help="Fresh local Context name for the reviewed Rules",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            hidden=True,
            help="Create --save-as from the operation-owned Distill decision",
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print a read-only legacy or Ground result without a Viewer",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option(
            "--tui",
            help="Require the read-only legacy or Ground result Viewer",
        ),
    ] = False,
) -> None:
    """Distill reusable Rules and add them to an existing Context."""

    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)
        automatic_result = not plain and not tui
        mode = resolve_console_mode(plain=plain, tui=tui)
        # Standalone results return through the compact/plain adapter. The
        # Context Summary Viewer is an explicit --tui inspection surface.
        if mode is ConsoleMode.AUTO:
            mode = ConsoleMode.PLAIN
        if ground is not None and (
            context_name is not None
            or source_name is not None
            or target_name is not None
            or goal is not None
            or direct
            or recursive
            or save_as is not None
            or apply
        ):
            raise DistillError(
                "--ground uses its frozen Goal and candidate frame and cannot be "
                "combined with Context, range, Goal, --save-as, or --apply options."
            )
        if apply and save_as is None:
            raise DistillError("--apply requires --save-as RESULT_CONTEXT.")
        if context_name is not None and source_name is not None:
            raise DistillError("Use either positional Context or --from, not both.")
        if save_as is not None and (source_name is not None or target_name is not None):
            raise DistillError(
                "Legacy --save-as cannot be combined with --from or --to."
            )
        resources: tuple[MemoryStore, ContextOperandSnapshot] | None = None

        def command_resources() -> tuple[MemoryStore, ContextOperandSnapshot]:
            nonlocal resources
            if resources is None:
                store = MemoryStore(create=False)
                resources = (store, ContextOperandSnapshot.capture(store))
            return resources

        store, _snapshot = command_resources()
        if ground is None and save_as is None:
            if tui:
                raise DistillError(
                    "Direct Distill Add is non-interactive; use "
                    "'mem impact distill' to inspect without saving."
                )
            endpoints = resolve_semantic_add_endpoints(
                source_locator=(
                    source_name if source_name is not None else context_name
                ),
                target_locator=target_name,
                current=_snapshot.current_name,
            )
            request = DistillRequest(
                context_locator=endpoints.source_name,
                goal=goal,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
            )
            with CommandProgress(
                "DISTILL",
                "freezing source and target",
                total=2,
            ) as progress:
                prepared = prepare_distill_add(
                    request,
                    store=store,
                    target_name=endpoints.target_name,
                    provider_factory=lambda: (
                        progress.update("distilling Rules", step=2)
                        or connect_semantic_provider()
                    ),
                )
            receipt = apply_prepared_distill_add(prepared, store=store)
            typer.secho(
                f"DISTILL APPLIED · {display_escape_text(endpoints.source_name)} "
                f"→ {display_escape_text(receipt.target_name)}",
                fg=typer.colors.GREEN,
                bold=True,
            )
            typer.echo(f"EFFECTS · ADD {receipt.count} RULES")
            render_applied_memory_preview(
                receipt.memory_uids,
                tuple(rule.content for rule in prepared.result.analysis.rules),
            )
            typer.echo(
                f"REVIEW · mem review distill --receipt {receipt.checkpoint_uid}"
            )
            typer.echo("UNDO · mem undo")
            return
        frozen_ground: FrozenGroundDistill | FrozenGroundWorkspaceDistill | None = (
            freeze_ground_distill(store, ground_name=ground)
            if ground is not None
            else None
        )
        if save_as is not None:
            validate_portable_context_name(save_as)
            if store.context_exists(save_as):
                raise DistillError(
                    f"Distill Result Context already exists: '{save_as}'."
                )

        def execute(request: DistillRequest) -> DistillResult:
            active_store, _snapshot = command_resources()
            if frozen_ground is not None and request != frozen_ground.request:
                # Ground supplies an exact frozen frame. A presentation adapter
                # must never broaden or retarget it before provider disclosure.
                raise DistillError(
                    "Ground Distill cannot change its frozen Source or reach."
                )
            with CommandProgress(
                "DISTILL",
                "freezing source",
                total=2,
            ) as progress:
                def connect_provider():
                    progress.update("distilling Rules", step=2)
                    return connect_semantic_provider()

                return (
                    execute_distill(
                        request=request,
                        store=active_store,
                        provider_factory=connect_provider,
                    )
                    if frozen_ground is None
                    else execute_ground_distill(
                        frozen_ground,
                        store=active_store,
                        provider_factory=connect_provider,
                    ).distill
                )

        def prepare_tui(request: DistillRequest) -> DistillTuiSetup:
            active_store, active_snapshot = command_resources()
            if frozen_ground is not None:
                name = frozen_ground.candidate_frame.context_name
                if request != frozen_ground.request:
                    raise DistillError(
                        "Ground Distill cannot change its frozen Source or reach."
                    )
                ground_preview_frame = (
                    frozen_ground.candidate_frame
                    if isinstance(frozen_ground, FrozenGroundWorkspaceDistill)
                    else frozen_ground.example_frame
                )
                if ground_preview_frame is not None:
                    def memory_loader(_name: str) -> tuple[ContextMemoryRow, ...]:
                        return _summary_frame_memory_rows(ground_preview_frame)

                else:
                    def memory_loader(
                        context_name: str,
                    ) -> tuple[ContextMemoryRow, ...]:
                        return context_memory_rows(
                            active_store.load_direct(context_name)
                        )

                return DistillTuiSetup(
                    names=(name,),
                    selected_context=name,
                    initial_range_mode="EXACT",
                    current_context=(
                        name if active_snapshot.current_name == name else None
                    ),
                    source_locked=True,
                    memory_loader=memory_loader,
                )
            selected_access = resolve_context_access(
                active_store,
                request.context_locator,
                current_name=active_snapshot.current_name,
                required_permission="READ",
            )
            catalog = freeze_profile_readable_context_catalog(
                active_store,
                selected_access,
                include_query_routes=False,
            )
            names = tuple(catalog.list_context_names())
            annotations = tuple(
                (name, context_access_display_facts(access))
                for name in names
                if (access := catalog.access_for(name)).is_granted
            )
            current = active_snapshot.current_name
            return DistillTuiSetup(
                names=names,
                selected_context=selected_access.display_name,
                initial_range_mode=(
                    "SUBTREE" if request.include_descendants else "EXACT"
                ),
                current_context=current if current in names else None,
                annotations=annotations,
                memory_loader=lambda name: context_memory_rows(
                    catalog.load_direct(name)
                ),
            )

        runner = build_distill_console_runner(
            execute=execute,
            prepare_tui=prepare_tui,
            clipboard_writer=write_system_clipboard,
            terminal=SystemTerminalCapabilities(),
        )
        execution_request = (
            frozen_ground.request
            if frozen_ground is not None
            else DistillRequest(
                context_locator=context_name,
                goal=goal,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
            )
        )
        # The hidden compatibility Apply form is still execution-first: its
        # proposal is internal staging and must not become a pre-Apply report.
        result = (
            execute(execution_request)
            if save_as is not None and apply
            else execute(execution_request)
            if automatic_result
            else runner.run(execution_request, mode=mode)
        )
        if result is None:
            typer.echo("Distill cancelled; Source unchanged.")
            return
        if automatic_result and not (save_as is not None and apply):
            render_distill_receipt(result)

        should_apply = apply
        if save_as is not None and not apply and sys.stdin.isatty() and sys.stdout.isatty():
            should_apply = typer.confirm(
                f"Create '{save_as}' from these exact {len(result.analysis.rules)} Rules?",
                default=False,
            )
        if should_apply:
            assert save_as is not None
            receipt = execute_distill_apply(
                DistillApplyRequest(result=result, output_name=save_as),
                store=store,
            )
            typer.echo("")
            typer.secho(
                f"DISTILL APPLIED · RESULT {receipt.output_name}",
                fg=typer.colors.GREEN,
                bold=True,
            )
            typer.echo(f"EFFECTS · ADD {len(receipt.result_memory_uids)} RULES")
            typer.echo("SOURCE · UNCHANGED")
            render_applied_memory_preview(
                receipt.result_memory_uids,
                tuple(rule.content for rule in result.analysis.rules),
            )
            typer.echo(
                f"REVIEW · mem review distill --receipt {receipt.checkpoint_uid}"
            )
            typer.echo("UNDO · mem undo")
        elif save_as is not None:
            typer.echo(
                f"RESULT · {display_escape_text(save_as)} · READY TO CREATE · "
                "rerun with --apply after reviewing this proposal"
            )
    except (
        DistillError,
        ConsoleModeError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Distill error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
