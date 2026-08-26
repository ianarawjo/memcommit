"""Typer adapter for structural Context Merge."""

from typing import Annotated, Optional

import typer

from memcommit.application.review_policy import (
    ownership_aware_application_review,
)
from memcommit.context_targeting.operands import choose_endpoint_operand
from memcommit.interfaces.cli.merge import (
    parse_merge_resolutions,
    render_merge_conflicts_plain,
    render_merge_plain,
)
from memcommit.interfaces.console.terminal import is_interactive_terminal
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.merge import (
    build_merge_tui_setup,
    choose_merge_setup,
    run_merge_conflict_review,
    run_merge_plan_review,
)
from memcommit.operations.merge.application import (
    MergeDecision,
    MergeError,
    MergeReach,
    MergeRequest,
    prepare_merge,
    run_merge,
)
from memcommit.operations.merge.runtime import MemoryStoreMergePort
from memcommit.operations.profile.config import ProfileConfigError
from memcommit.operations.profile.model import ProfileError
from memcommit.store import MemoryStore


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Readable Source Context to structurally merge into the selected "
                "Target; omit in a TTY to choose both endpoints interactively"
            )
        ),
    ] = None,
    target: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing CREATE-authorized Target Context; equivalent to "
                "--into and defaults to the command-start current Context"
            )
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Explicit Source Context; compatibility alias for the first "
                "positional endpoint"
            ),
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help=(
                "Existing CREATE-authorized Target Context; defaults to the "
                "command-start current Context"
            ),
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Compatibility alias for --into Target Context",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Merge direct items from the exact Source root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Merge matching descendants by the same relative path, "
                "creating Source-only Target paths"
            ),
        ),
    ] = False,
    resolution: Annotated[
        Optional[list[str]],
        typer.Option(
            "--resolve",
            help=(
                "Resolve one conflict as ID=keep-target or "
                "ID=take-source; repeat for every conflict"
            ),
        ),
    ] = None,
    keep_target_all: Annotated[
        bool,
        typer.Option(
            "--keep-target-all",
            help="Resolve every deterministic conflict by keeping Target",
        ),
    ] = False,
    take_source_all: Annotated[
        bool,
        typer.Option(
            "--take-source-all",
            help="Resolve every deterministic conflict by taking Source",
        ),
    ] = False,
) -> None:
    try:
        requested_source = choose_endpoint_operand(
            source,
            role="Source",
            options=(("--from", from_),),
        )
        requested_target = choose_endpoint_operand(
            target,
            role="Target",
            options=(("--into", into), ("--to", to)),
        )
    except ValueError as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if direct and recursive:
        typer.secho(
            "Error: choose either --direct or --recursive, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if keep_target_all and take_source_all:
        typer.secho(
            "Error: choose either --keep-target-all or --take-source-all.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if resolution and (keep_target_all or take_source_all):
        typer.secho(
            "Error: use either repeatable --resolve or one bulk strategy.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    current = store.current_context_name()
    if not current and requested_target is None:
        typer.secho(
            "No current Target. Pass TARGET/--into/--to or run "
            "'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    port = MemoryStoreMergePort(store, current_name=current)
    try:
        if requested_source is None:
            if not is_interactive_terminal():
                raise MergeError(
                    "Merge requires SOURCE outside a TTY; pass SOURCE with "
                    "--direct or --recursive."
                )
            setup = build_merge_tui_setup(
                port,
                initial_recursive=recursive,
                requested_target=requested_target,
            )
            request = choose_merge_setup(setup)
            if request is None:
                typer.echo("Merge cancelled — no changes made.")
                return
            plan = prepare_merge(request, port=port)
            if plan.conflicts:
                result = run_merge_conflict_review(
                    plan,
                    apply_plan=lambda frozen, resolutions: run_merge(
                        request,
                        port=port,
                        frozen_plan=frozen,
                        resolutions=resolutions,
                    ),
                )
            elif (
                ownership_aware_application_review(
                    mutates_granted_authority=plan.mutates_granted_authority,
                    local_undo_available=True,
                ).decision_free_behavior
                == "AUTO_ACCEPT"
            ):
                # A decision-free local plan needs no duplicate approval. It
                # still crosses the normal application boundary so its exact
                # no-op or mutation remains a checkpointed Undo/Redo unit.
                result = run_merge(
                    request,
                    port=port,
                    frozen_plan=plan,
                )
            else:
                result = run_merge_plan_review(
                    plan,
                    apply_plan=lambda frozen: run_merge(
                        request,
                        port=port,
                        frozen_plan=frozen,
                    ),
                )
            if result is None:
                typer.echo("Merge cancelled — no changes made.")
                return
        else:
            request = MergeRequest(
                source_locator=requested_source,
                target_locator=requested_target,
                reach=(MergeReach.DESCENDANTS if recursive else MergeReach.DIRECT),
            )
            plan = prepare_merge(request, port=port)
            bulk = (
                MergeDecision.KEEP_TARGET
                if keep_target_all
                else MergeDecision.TAKE_SOURCE
                if take_source_all
                else None
            )
            parsed = parse_merge_resolutions(plan, tuple(resolution or ()))
            if plan.conflicts and not parsed and bulk is None:
                render_merge_conflicts_plain(plan)
                raise MergeError(
                    "Merge has required conflicts; review the conflict IDs above "
                    "and choose one resolution for each."
                )
            result = run_merge(
                request,
                port=port,
                frozen_plan=plan,
                resolutions=parsed,
                bulk=bulk,
            )
    except (
        FileNotFoundError,
        MergeError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_merge_plain(result)
