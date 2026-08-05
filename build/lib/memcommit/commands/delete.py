from typing import Annotated

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.store import (
    ContextDeletionCommittedError,
    MemoryStore,
    context_record_digest,
)


def cmd(
    context_name: Annotated[str, typer.Argument(help="Context to delete")],
    force: Annotated[bool, typer.Option("-f", "--force", help="Skip confirmation prompt")] = False,
) -> None:
    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    try:
        context_name = snapshot.resolve(context_name)
        target = store.load_direct(context_name)
    except (FileNotFoundError, OSError, ValueError) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    target_digest = context_record_digest(target)
    display_name = display_escape_text(context_name)

    if not force:
        typer.echo(
            f"This will permanently delete context '{display_name}' and its "
            "checkpoint history, plus its matching atomize analysis and "
            "semantic review artifacts, including peer Compare analyses. "
            "Descendant contexts will be preserved. A Profile-scoped lifecycle "
            "event will retain the deleted Context identity and digests, but no "
            "Memory content or restorable snapshot."
        )
        typer.confirm("Continue?", abort=True)

    try:
        deletion_event = store.delete_context_if(
            context_name,
            expected_context_uid=target.uid,
            expected_context_digest=target_digest,
        )
    except ContextDeletionCommittedError as error:
        typer.secho(
            f"Deleted context '{display_name}' · ledger "
            f"[{error.event.event_uid[:8]}], but post-delete cleanup was "
            f"incomplete: {display_escape_text(str(error))}",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(1)
    except (OSError, RuntimeError, ValueError) as e:
        typer.secho(
            f"Error: {display_escape_text(str(e))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.secho(
        f"Deleted context '{display_name}' · ledger "
        f"[{deletion_event.event_uid[:8]}].",
        fg=typer.colors.GREEN,
    )
