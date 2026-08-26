from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.infrastructure.command_ledger.attempts import annotate_command_outcome
from memcommit.authority.access import (
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint
from memcommit.operations.edit.application import (
    EditRequest,
    EditResult,
    FrozenEditPlan,
    run_edit,
)
from memcommit.operations.edit.runtime import MemoryStoreEditPort
from memcommit.interfaces.cli.batch_input import parse_edit_lines, read_text_input
from memcommit.interfaces.console.terminal import is_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.operations.edit import choose_edit_setup
from memcommit.operations.profile.config import ProfileConfigError
from memcommit.operations.profile.model import ProfileError
from memcommit.store import MemoryStore


def _render_content(prefix: str, content: str, color: str) -> None:
    lines = content.splitlines() or [""]
    for line in lines:
        typer.secho(f"  {prefix} {line}", fg=color)


def _render_edit_result(result: EditResult) -> None:
    if not result.changed:
        annotate_command_outcome("NO_CHANGE")
        typer.secho(
            f"Memory [{result.memory_uid[:8]}] is unchanged.",
            fg=typer.colors.YELLOW,
        )
        return
    typer.secho(
        f"Edited [{result.memory_uid[:8]}] in '{result.context_name}':",
        fg=typer.colors.GREEN,
        bold=True,
    )
    _render_content("-", result.original_content, typer.colors.RED)
    _render_content("+", result.content, typer.colors.GREEN)


def cmd(
    memory_selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "UID/prefix or CONTEXT:UID of the directly owned Memory; "
                "a bare UID must be unique across all local Contexts; "
                "omit both positional operands in a terminal to choose it interactively"
            ),
        ),
    ] = None,
    content: Annotated[
        Optional[str],
        typer.Argument(
            help="Exact replacement content for one selected Memory",
        ),
    ] = None,
    input_source: Annotated[
        Optional[str],
        typer.Option(
            "--input",
            "-i",
            metavar="BATCH_FILE",
            help=(
                "Batch mode: edit one Memory per UTF-8 UID<TAB>content line; "
                "use '-' for stdin"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            metavar="CONTEXT",
            help="Local Context or granted view containing the Memory",
        ),
    ] = None,
) -> None:
    interactive_plan: FrozenEditPlan | None = None
    if input_source is None:
        if memory_selector is None and content is None and is_interactive_terminal():
            active_store = MemoryStore()
            edit_port = MemoryStoreEditPort.capture(active_store)
            try:
                interactive_plan = choose_edit_setup(
                    edit_port,
                    requested_context=context_name,
                )
            except (
                FileNotFoundError,
                KeyError,
                OSError,
                ProfileConfigError,
                ProfileError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as error:
                typer.secho(
                    f"Error: {safe_terminal_text(str(error))}",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            if interactive_plan is None:
                annotate_command_outcome("CANCELLED")
                typer.echo("Edit cancelled — no Memory was changed.")
                return
            request = interactive_plan.request
            try:
                result = run_edit(
                    request,
                    port=edit_port,
                    frozen_plan=interactive_plan,
                )
            except (
                FileNotFoundError,
                KeyError,
                OSError,
                ProfileConfigError,
                ProfileError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as error:
                typer.secho(
                    f"Error: {safe_terminal_text(str(error))}",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
            _render_edit_result(result)
            return
        if memory_selector is None or content is None:
            typer.secho(
                "Error: provide MEMORY_SELECTOR and CONTENT for one edit, use "
                "--input BATCH_FILE for UID<TAB>CONTENT records, or run bare "
                "'mem edit' in a terminal to choose a Memory.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
    elif memory_selector is not None or content is not None:
        typer.secho(
            "Error: --input is batch-file mode and cannot be combined with "
            "positional MEMORY_SELECTOR or CONTENT. For one Memory, run: "
            'mem edit MEMORY_SELECTOR "CONTENT".',
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    active_store = MemoryStore()
    current_name = active_store.current_context_name()
    if input_source is None:
        assert memory_selector is not None
        assert content is not None
        port = MemoryStoreEditPort(active_store, current_name=current_name)
        try:
            result = run_edit(
                EditRequest(
                    memory_selector=memory_selector,
                    content=content,
                    context_locator=context_name,
                ),
                port=port,
            )
        except (
            FileNotFoundError,
            KeyError,
            OSError,
            ProfileConfigError,
            ProfileError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Error: {safe_terminal_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        _render_edit_result(result)
        return

    try:
        access = resolve_context_access(
            active_store,
            context_name,
            current_name=current_name,
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

    assert input_source is not None
    try:
        edits = parse_edit_lines(read_text_input(input_source))
        changes = ops.edit_many(ctx, edits)
    except (KeyError, TypeError, ValueError) as error:
        typer.secho(
            f"Error: {safe_terminal_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
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
        typer.secho(
            f"Error: {safe_terminal_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
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
