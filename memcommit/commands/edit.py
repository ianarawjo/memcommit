from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.command_attempts import annotate_command_outcome
from memcommit.commands.batch_input import parse_edit_lines, read_text_input
from memcommit.authority.access import (
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint, Memory
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def _render_content(prefix: str, content: str, color: str) -> None:
    lines = content.splitlines() or [""]
    for line in lines:
        typer.secho(f"  {prefix} {line}", fg=color)


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help="UID (or unambiguous prefix) of the direct Memory to edit"
        ),
    ] = None,
    content: Annotated[
        Optional[str],
        typer.Argument(help="Replacement content for the Memory"),
    ] = None,
    input_source: Annotated[
        Optional[str],
        typer.Option(
            "--input",
            "-i",
            help=(
                "Edit one Memory per UTF-8 UID<TAB>content line; "
                "use '-' for stdin"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Local Context or granted view containing the Memory",
        ),
    ] = None,
) -> None:
    if input_source is None:
        if selector is None or content is None:
            typer.secho(
                "Error: provide SELECTOR and CONTENT, or use --input.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
    elif selector is not None or content is not None:
        typer.secho(
            "Error: --input cannot be combined with SELECTOR or CONTENT.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    active_store = MemoryStore()
    try:
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=active_store.current_context_name(),
            required_permission="UPDATE",
        )
        store = access.store
        ctx = store.load_direct(access.context_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if input_source is not None:
        try:
            edits = parse_edit_lines(read_text_input(input_source))
            changes = ops.edit_many(ctx, edits)
        except (KeyError, TypeError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        if not changes:
            annotate_command_outcome("NO_CHANGE")
            typer.secho(
                f"All {len(edits)} memories are unchanged.",
                fg=typer.colors.YELLOW,
            )
            return

        try:
            with authorized_context_mutation(access):
                store.save(
                    ctx,
                    AutoCheckpoint(
                        command="edit",
                        args={
                            "input": input_source,
                            "mode": "uid-tab-content",
                            "count": len(changes),
                            "uids": [edited.uid for _, edited in changes],
                            "edits": [
                                {"uid": edited.uid, "content": edited.content}
                                for _, edited in changes
                            ],
                            **grant_checkpoint_args(access),
                        },
                        description=(
                            f"Edited {len(changes)} memories from "
                            f"{'stdin' if input_source == '-' else repr(input_source)}"
                        ),
                    ),
                )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        typer.secho(
            f"Edited {len(changes)} memories in '{ctx.name}':",
            fg=typer.colors.GREEN,
            bold=True,
        )
        for original, edited in changes:
            typer.secho(f"  [{edited.uid[:8]}]", bold=True)
            _render_content("-", original.content, typer.colors.RED)
            _render_content("+", edited.content, typer.colors.GREEN)

        unchanged = len(edits) - len(changes)
        if unchanged:
            typer.secho(
                f"{unchanged} unchanged "
                f"{'memory was' if unchanged == 1 else 'memories were'} skipped.",
                fg=typer.colors.YELLOW,
            )
        return

    assert selector is not None
    assert content is not None
    try:
        original = ops.edit(ctx, selector, content)
    except (KeyError, TypeError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if original.content == content:
        annotate_command_outcome("NO_CHANGE")
        typer.secho(
            f"Memory [{original.uid[:8]}] is unchanged.",
            fg=typer.colors.YELLOW,
        )
        return

    edited = ctx.memories[original.uid]
    assert isinstance(edited, Memory)
    try:
        with authorized_context_mutation(access):
            store.save(
                ctx,
                AutoCheckpoint(
                    command="edit",
                    args={
                        "uid": edited.uid,
                        "content": content,
                        **grant_checkpoint_args(access),
                    },
                    description=f"Edited memory [{edited.uid[:8]}]",
                ),
            )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.secho(
        f"Edited [{edited.uid[:8]}] in '{ctx.name}':",
        fg=typer.colors.GREEN,
        bold=True,
    )
    _render_content("-", original.content, typer.colors.RED)
    _render_content("+", edited.content, typer.colors.GREEN)
