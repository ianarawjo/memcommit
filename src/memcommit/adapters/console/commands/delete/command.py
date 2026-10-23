"""Delete current-Context Memories, or explicitly delete the current Context."""

from typing import Annotated

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.adapters.console.terminal.components.context_picker import (
    ContextPickerActionReceipt,
)
from memcommit.adapters.console.commands.delete.picker import choose_delete_target
from memcommit.adapters.console.commands.delete.receipt import (
    render_context_delete_result,
    render_removed_item,
    removed_item_description,
)
from memcommit.adapters.console.commands.delete.review import context_delete_warning
from memcommit.adapters.console.terminal.components.errors import render_cli_error
from memcommit.application.operations.delete.application import (
    ContextDeleteRequest,
    DirectItemDeleteRequest,
    apply_context_delete,
    run_direct_item_delete,
)
from memcommit.application.operations.delete.runtime import MemoryStoreDeletePort
from memcommit.persistence.store import MemoryStore


def cmd(
    selectors: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="[UID]...",
            help="Memory UID prefixes in the current Context; omit to select interactively.",
        ),
    ] = None,
    context: Annotated[
        bool,
        typer.Option(
            "--context",
            "-c",
            help="Delete the current Context itself instead of Memories.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Skip confirmation when deleting the current Context."
        ),
    ] = False,
) -> None:
    if context and selectors:
        raise typer.BadParameter(
            "--context takes no name and cannot be combined with Memory UIDs."
        )
    store = MemoryStore()
    port = MemoryStoreDeletePort.capture(store)
    try:
        if port.current_name is None:
            raise ValueError(
                "No current Context. Run 'mem switch' or 'mem init' first."
            )
        if context:
            plan = port.freeze_context(ContextDeleteRequest(port.current_name))
            if not force:
                typer.echo(context_delete_warning(plan))
                typer.confirm("Continue?", abort=True)
            result = apply_context_delete(plan, port=port)
            render_context_delete_result(result)
            if result.status == "APPLIED_WITH_CLEANUP_WARNING":
                raise typer.Exit(1)
            return
        if selectors:
            # Bind the complete batch before removing anything, including ambiguity.
            targets = tuple(
                port.freeze_item(DirectItemDeleteRequest(value)) for value in selectors
            )
            if len({target.item.uid for target in targets}) != len(targets):
                raise ValueError("Delete selectors repeat the same Memory.")
            for target in targets:
                result = run_direct_item_delete(
                    DirectItemDeleteRequest(target.item.uid),
                    port=port,
                    frozen_target=target,
                )
                render_removed_item(result)
            return

        completed = 0

        def delete_memory(
            context_name: str, memory_uid: str
        ) -> ContextPickerActionReceipt:
            nonlocal completed
            try:
                target = port.freeze_item(
                    DirectItemDeleteRequest(memory_uid, context_locator=context_name)
                )
                result = run_direct_item_delete(
                    DirectItemDeleteRequest(memory_uid), port=port, frozen_target=target
                )
            except (OSError, RuntimeError, ValueError, KeyError) as error:
                return ContextPickerActionReceipt(
                    label="DELETE FAILED",
                    detail=str(error),
                    label_style="class:memcommit.error",
                )
            completed += 1
            return ContextPickerActionReceipt(
                label="DELETED",
                detail=removed_item_description(result.item),
                label_style="class:impact.remove",
            )

        chosen = choose_delete_target(
            store, current_name=port.current_name, item_handler=delete_memory
        )
        if isinstance(chosen, tuple):
            delete_memory(*chosen)
        if not completed:
            annotate_command_outcome("CANCELLED")
            typer.echo("Delete cancelled; no Memory was changed.")
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        render_cli_error(error)
        raise typer.Exit(1) from error
