from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.application.operations.edit.application import (
    EditBatchRequest,
    EditBatchResult,
    EditRequest,
    EditResult,
    FrozenEditPlan,
    run_edit,
)
from memcommit.application.operations.edit.runtime import MemoryStoreEditPort
from memcommit.adapters.console.commands.edit.input_records import parse_input_records
from memcommit.adapters.console.coordination.batch_input_source import (
    read_batch_input_text,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    is_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.commands.edit.workbench import choose_edit_setup
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


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


def _render_edit_batch_result(result: EditBatchResult) -> None:
    changes = result.changed_edits
    if not changes:
        annotate_command_outcome("NO_CHANGE")
        typer.secho(
            f"All {len(result.edits)} memories are unchanged.",
            fg=typer.colors.YELLOW,
        )
        return
    typer.secho(
        f"Edited {len(changes)} memories in '{result.context_name}':",
        fg=typer.colors.GREEN,
        bold=True,
    )
    for edit in changes:
        typer.secho(f"  [{edit.memory_uid[:8]}]", bold=True)
        _render_content("-", edit.original_content, typer.colors.RED)
        _render_content("+", edit.content, typer.colors.GREEN)
    unchanged = len(result.edits) - len(changes)
    if unchanged:
        typer.secho(
            f"{unchanged} unchanged "
            f"{'memory was' if unchanged == 1 else 'memories were'} skipped.",
            fg=typer.colors.YELLOW,
        )


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
    port = MemoryStoreEditPort.capture(active_store)
    try:
        if input_source is None:
            assert memory_selector is not None
            assert content is not None
            request = EditRequest(memory_selector, content, context_name)
        else:
            request = EditBatchRequest(
                edits=tuple(parse_input_records(read_batch_input_text(input_source))),
                context_locator=context_name,
                input_source=input_source,
            )
        result = run_edit(request, port=port)
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
    if isinstance(result, EditBatchResult):
        _render_edit_batch_result(result)
    else:
        _render_edit_result(result)
