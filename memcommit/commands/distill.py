"""Distill evidence-bound Rules from one Context into a reviewed proposal."""

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
from memcommit.distill import DistillError
from memcommit.distill_application import (
    DistillApplyRequest,
    DistillRequest,
    DistillResult,
)
from memcommit.distill_runtime import execute_distill, execute_distill_apply
from memcommit.ground_distill import (
    FrozenGroundDistill,
    execute_ground_distill,
    freeze_ground_distill,
)
from memcommit.interfaces.cli.distill import distill_result_text
from memcommit.interfaces.console import (
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.distill import DistillTuiSetup
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.store import MemoryStore, validate_context_name


def render_distill(result: DistillResult) -> str:
    """Compatibility projection for former command-local renderer callers."""

    return distill_result_text(result)


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing local Context to distill by canonical name or explicit "
                "relative locator (defaults to current)"
            )
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
            help="Fresh local Context name for the reviewed Rules",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Create --save-as from this exact proposal without a TTY prompt",
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print the reviewed proposal instead of opening the Viewer",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option(
            "--tui",
            help="Require the interactive Distill setup and Viewer",
        ),
    ] = False,
) -> None:
    """Distill reusable Rules; Source is unchanged and Apply requires a new Result."""

    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)
        mode = resolve_console_mode(plain=plain, tui=tui)
        if ground is not None and (
            context_name is not None
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
        resources: tuple[MemoryStore, ContextOperandSnapshot] | None = None

        def command_resources() -> tuple[MemoryStore, ContextOperandSnapshot]:
            nonlocal resources
            if resources is None:
                store = MemoryStore(create=False)
                resources = (store, ContextOperandSnapshot.capture(store))
            return resources

        store, _snapshot = command_resources()
        frozen_ground: FrozenGroundDistill | None = (
            freeze_ground_distill(store, ground_name=ground)
            if ground is not None
            else None
        )
        if save_as is not None:
            validate_context_name(save_as)
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
                return DistillTuiSetup(
                    names=(name,),
                    selected_context=name,
                    initial_range_mode="EXACT",
                    current_context=(
                        name if active_snapshot.current_name == name else None
                    ),
                    source_locked=True,
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
            )

        runner = build_distill_console_runner(
            execute=execute,
            prepare_tui=prepare_tui,
            clipboard_writer=write_system_clipboard,
            terminal=SystemTerminalCapabilities(),
        )
        result = runner.run(
            (
                frozen_ground.request
                if frozen_ground is not None
                else DistillRequest(
                    context_locator=context_name,
                    goal=goal,
                    include_descendants=traversal.include_descendants,
                    follow_embeds=traversal.follow_embeds,
                )
            ),
            mode=mode,
        )
        if result is None:
            typer.echo("Distill cancelled; Source unchanged.")
            return

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
                f"Created Distill Result '{receipt.output_name}' with "
                f"{len(receipt.result_memory_uids)} Rules; Source unchanged.",
                fg=typer.colors.GREEN,
            )
            typer.echo(f"CHECKPOINT · {receipt.checkpoint_uid[:8]} · RECOVERY · mem undo")
        elif save_as is not None:
            typer.echo(
                f"RESULT · {display_escape_text(save_as)} · NOT CREATED · "
                "rerun with --apply only after reviewing this proposal"
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
