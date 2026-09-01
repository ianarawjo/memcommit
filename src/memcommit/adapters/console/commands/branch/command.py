from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.branch.endpoint_setup import (
    choose_branch_creation,
)
from memcommit.application.capabilities.operand_resolution import (
    freeze_local_context_operand_candidates,
    resolve_existing_context_operand,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import (
    suggest_fresh_context_name,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.branch.application import BranchRequest
from memcommit.application.operations.branch.runtime import (
    execute_branch,
    prepare_branch,
)
from memcommit.persistence.store import MemoryStore


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Name for a new branch Context; omit in a terminal to choose "
                "a local Source, parent location, and exact fresh name"
            )
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Existing local Source Context; defaults to the current Context",
        ),
    ] = None,
    source_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--source-descendants/--source-root-only",
            legacy_root_only_option_alias("source"),
            help="Branch the Source root and every local lexical descendant",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Branch only the selected Source root"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Branch the Source root and all lexical descendants",
        ),
    ] = False,
) -> None:
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        (resolved_source_descendants,) = resolve_descendant_scopes(
            preset=preset,
            explicit=(source_descendants,),
        )
    except (TypeError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore()
    setup = prepare_branch(store)
    expected_current = setup.expected_current
    local_names = setup.local_context_names
    if name is None:
        if direct or recursive or source_descendants is not None or from_ is not None:
            typer.secho(
                "Error: --from and scope flags require an explicit branch NAME; "
                "interactive setup owns its visible Source range.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        if not local_names:
            typer.secho(
                "No local Contexts exist. Run 'mem init <name>' first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            receipt = choose_branch_creation(
                local_names,
                current=expected_current,
                suggest_name=lambda source: suggest_fresh_context_name(
                    f"{source}/branch",
                    local_names,
                ),
                validate_name=store.assert_context_creatable,
            )
        except (OSError, TypeError, ValueError) as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        if receipt is None:
            typer.echo("Branch cancelled — no Context was changed.")
            return
        if receipt.source_name not in local_names:
            typer.secho(
                "Error: the selected Branch Source is no longer available. "
                "Reopen Branch and select it again.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        source_name = receipt.source_name
        name = receipt.target_name
        source_descendants = receipt.include_descendants
    else:
        try:
            source_name = (
                resolve_existing_context_operand(
                    freeze_local_context_operand_candidates(store),
                    from_,
                    current=expected_current,
                ).name
                if from_ is not None
                else expected_current
            )
        except ValueError as error:
            typer.secho(
                f"Error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        source_descendants = resolved_source_descendants
    if not source_name:
        typer.secho(
            "No current context. Run 'mem init <name>' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if source_name not in local_names:
        typer.secho(
            "Error: Branch requires a local Source; "
            f"'{display_escape_text(source_name)}' is not in the local catalog.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        result = execute_branch(
            BranchRequest(
                source_name=source_name,
                target_name=name,
                include_descendants=source_descendants,
                expected_current=expected_current,
                local_context_names=local_names,
            ),
            store=store,
        )
    except (FileExistsError, FileNotFoundError, OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if source_descendants:
        typer.secho(
            f"Branched subtree '{display_escape_text(source_name)}' → "
            f"'{display_escape_text(name)}' · {result.context_count} Context(s), "
            f"{result.descendant_count} descendant(s); switched to its root.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"Branched '{display_escape_text(source_name)}' → "
            f"'{display_escape_text(name)}' and switched to it.",
            fg=typer.colors.GREEN,
        )
