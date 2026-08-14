from typing import Annotated, Optional

import typer

import memcommit.commands.init_study as init_study_command
from memcommit.context_init_application import (
    ContextInitError,
    ContextInitRequest,
)
from memcommit.context_init_runtime import (
    execute_context_init,
    prepare_context_init,
)
from memcommit.context_targeting.tui.name_editor import choose_context_name
from memcommit.interfaces.cli.context_init import render_context_init
from memcommit.interfaces.tui.operations.context_init import (
    ContextInitTuiSetup,
    run_context_init_tui,
)
from memcommit.profiles import STUDY_BASELINE_PROFILE_NAME
from memcommit.store import MemoryStore, validate_context_name


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Unique name for the new Context, or for the new Study Profile "
                "with --study; omit to use the corresponding interactive or "
                "generated default"
            )
        ),
    ] = None,
    parents: Annotated[
        bool,
        typer.Option(
            "--parents",
            "-p",
            help=(
                "Create missing lexical parent Contexts and reuse existing "
                "prefixes; does not embed children"
            ),
        ),
    ] = False,
    study: Annotated[
        bool,
        typer.Option(
            "--study",
            help=(
                "Initialize an isolated Study Profile pair instead of an "
                "ordinary Context"
            ),
        ),
    ] = False,
    baseline_profile: Annotated[
        Optional[str],
        typer.Option(
            "--from-profile",
            help=(
                "Editable Study baseline to copy; valid only together with "
                "--study"
            ),
        ),
    ] = None,
) -> None:
    if study:
        if parents:
            typer.secho(
                "Error: --study cannot be combined with --parents.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        # Keep Study initialization as a separate use case.  The compatibility
        # command and the new option must share its Profile-pair, hidden-cache,
        # and action-ledger path instead of reimplementing those rules here.
        init_study_command.cmd(
            name=name,
            baseline_profile=(
                baseline_profile
                if baseline_profile is not None
                else STUDY_BASELINE_PROFILE_NAME
            ),
        )
        return
    if baseline_profile is not None:
        typer.secho(
            "Error: --from-profile requires --study.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore()
    snapshot = prepare_context_init(store)
    try:
        if name is None:
            request = run_context_init_tui(
                setup=ContextInitTuiSetup(
                    expected_current=snapshot.expected_current,
                    context_names=snapshot.context_names,
                    validate_name=(
                        validate_context_name
                        if parents
                        else store.assert_context_creatable
                    ),
                ),
                create_parents=parents,
                # Preserve the historical command-level injection seam while
                # the concrete TUI implementation lives with its adapter.
                chooser=choose_context_name,
            )
            if request is None:
                typer.echo("Initialization cancelled — no Context was created.")
                return
        else:
            request = ContextInitRequest(
                name=name,
                create_parents=parents,
                expected_current=snapshot.expected_current,
            )
        result = execute_context_init(request, store=store)
    except (ContextInitError, OSError, RuntimeError, TypeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    render_context_init(result)
