from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.branch_dialog import choose_branch_creation
from memcommit.context_naming import validate_portable_context_name
from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.context_targeting.tui.name_editor import suggest_fresh_context_name
from memcommit.store import (
    ContextBranchBinding,
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
)


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
    expected_current = store.current_context_name()
    local_names = tuple(store.list_context_names())
    if name is None:
        if direct or recursive or source_descendants is not None:
            typer.secho(
                "Error: scope flags require an explicit branch NAME; "
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
                memory_loader=lambda context_name: context_memory_rows(
                    store.load(context_name)
                ),
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
                "Error: selected Branch Source is outside the frozen local catalog.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        source_name = receipt.source_name
        name = receipt.target_name
        source_descendants = receipt.include_descendants
    else:
        source_name = expected_current
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
            "Error: Branch requires a local Source; the current Context "
            f"'{display_escape_text(source_name)}' is not in the local catalog.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    try:
        validate_portable_context_name(name)
        if store.context_exists(name):
            raise FileExistsError(f"Context '{name}' already exists.")
        source_names = expand_lexical_context_names(
            ContextScope.create(
                (source_name,),
                include_descendants=source_descendants,
            ),
            local_names,
        )
        sources = tuple(store.load_for_update(value) for value in source_names)
        histories = {value: store.list_checkpoints(value) for value in source_names}
        targets = (
            ops.branch_subtree(sources, source_name, name)
            if source_descendants
            else (ops.branch(sources[0], name),)
        )
        bindings = tuple(
            ContextBranchBinding(
                source_name=source.name,
                expected_source_uid=source.uid,
                expected_source_digest=context_record_digest(source),
                expected_history_digest=checkpoint_history_digest(
                    histories[source.name]
                ),
                target=target,
            )
            for source, target in zip(sources, targets, strict=True)
        )
        store.create_branch_contexts(
            bindings,
            source_root=source_name,
            target_root=name,
            include_descendants=source_descendants,
            expected_current=expected_current,
        )
    except (FileExistsError, FileNotFoundError, OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if source_descendants:
        descendant_count = len(source_names) - 1
        typer.secho(
            f"Branched subtree '{display_escape_text(source_name)}' → "
            f"'{display_escape_text(name)}' · {len(source_names)} Context(s), "
            f"{descendant_count} descendant(s); switched to its root.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"Branched '{display_escape_text(source_name)}' → "
            f"'{display_escape_text(name)}' and switched to it.",
            fg=typer.colors.GREEN,
        )
