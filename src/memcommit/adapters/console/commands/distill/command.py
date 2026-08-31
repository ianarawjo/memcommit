"""Distill evidence-bound Rules and publish an execution receipt."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_operand,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.application.operations.distill.model import DistillError
from memcommit.application.operations.distill.application import (
    DistillApplyRequest,
    DistillRequest,
    DistillResult,
)
from memcommit.application.operations.distill.runtime import (
    apply_prepared_distill_add,
    execute_distill,
    execute_distill_apply,
    prepare_distill_add,
)
from memcommit.application.operations.ground.distill import (
    FrozenGroundDistill,
    GroundDistillResult,
    apply_ground_distill_result,
    execute_ground_distill,
    freeze_ground_distill,
)
from memcommit.adapters.console.commands.distill.proposal import distill_result_text
from memcommit.adapters.console.commands.distill.receipt import render_distill_receipt
from memcommit.adapters.console.terminal.components.applied_memory_preview import (
    render_applied_memory_preview,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    resolve_semantic_result_endpoints,
)
from memcommit.persistence.store import MemoryStore


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
            ),
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
            help=(
                "Optional relevance focus as a Context, CONTEXT:UID/UID "
                "Memory, or inline text; omit it to skip Goal Fit"
            ),
        ),
    ] = None,
    ground: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help="Use the exact Goal and working-candidate frame of a bound Ground",
        ),
    ] = None,
    adopt: Annotated[
        bool,
        typer.Option(
            "--adopt",
            help=(
                "Explicitly add the complete physical-Ground proposal to its "
                "/rules lane"
            ),
        ),
    ] = False,
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
) -> None:
    """Distill reusable Rules and add them to an existing Context."""

    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)
        if adopt and ground is None:
            raise DistillError("--adopt requires --ground.")
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
            endpoints = resolve_semantic_result_endpoints(
                source_locator=(
                    source_name if source_name is not None else context_name
                ),
                target_locator=target_name,
                current=_snapshot.current_name,
            )
            goal_focus = (
                freeze_goal_focus_operand(
                    store,
                    goal,
                    current_name=_snapshot.current_name,
                )
                if goal is not None
                else None
            )
            request = DistillRequest(
                context_locator=endpoints.source_name,
                goal_focus=goal_focus,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
            )
            with CommandProgress(
                "DISTILL",
                "preparing source and target",
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
        frozen_ground: FrozenGroundDistill | None = (
            freeze_ground_distill(store, ground_name=ground)
            if ground is not None
            else None
        )
        ground_result: GroundDistillResult | None = None
        if save_as is not None:
            validate_portable_context_name(save_as)
            if store.context_exists(save_as):
                raise DistillError(
                    f"Distill Result Context already exists: '{save_as}'."
                )

        def execute(request: DistillRequest) -> DistillResult:
            nonlocal ground_result
            active_store, _snapshot = command_resources()
            if frozen_ground is not None and request != frozen_ground.request:
                # Ground supplies an exact frozen frame. A presentation adapter
                # must never broaden or retarget it before provider disclosure.
                raise DistillError(
                    "Ground Distill cannot change its frozen Source or reach."
                )
            with CommandProgress(
                "DISTILL",
                "preparing source",
                total=2,
            ) as progress:

                def connect_provider():
                    progress.update("distilling Rules", step=2)
                    return connect_semantic_provider()

                if frozen_ground is None:
                    return execute_distill(
                        request=request,
                        store=active_store,
                        provider_factory=connect_provider,
                    )
                ground_result = execute_ground_distill(
                    frozen_ground,
                    store=active_store,
                    provider_factory=connect_provider,
                )
                return ground_result.distill

        execution_request = (
            frozen_ground.request
            if frozen_ground is not None
            else DistillRequest(
                context_locator=context_name,
                goal_focus=(
                    freeze_goal_focus_operand(
                        store,
                        goal,
                        current_name=_snapshot.current_name,
                    )
                    if goal is not None
                    else None
                ),
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
            )
        )
        # The hidden compatibility Apply form is still execution-first: its
        # proposal is internal staging and must not become a pre-Apply report.
        result = execute(execution_request)
        if not (save_as is not None and apply):
            render_distill_receipt(result)

        if adopt:
            if ground_result is None:
                raise DistillError("Distill produced no Ground proposal.")
            receipt = apply_ground_distill_result(ground_result, store=store)
            typer.secho(
                f"DISTILL ADOPTED · {display_escape_text(receipt.workspace_name)}"
                f"/{receipt.lane}",
                fg=typer.colors.GREEN,
                bold=True,
            )
            typer.echo(
                f"EFFECTS · ADD {len(receipt.memory_uids)} RULES · "
                f"GROUND REVISION {receipt.revision}"
            )
            typer.echo(f"UNDO · mem ground {receipt.workspace_name} --undo")
            return

        # Terminal interactivity must not broaden compatibility --save-as
        # into publication; only the explicit --apply operand crosses it.
        if apply:
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
