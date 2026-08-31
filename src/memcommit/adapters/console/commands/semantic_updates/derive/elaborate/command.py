"""Apply one provider-supported continuation to an existing Memory."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.semantic_updates.derive.elaborate.application import (
    ElaborateError,
    ElaborateRequest,
)
from memcommit.application.operations.semantic_updates.derive.elaborate.runtime import execute_elaborate
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)


def cmd(
    memory_selector: Annotated[
        str,
        typer.Argument(
            help=(
                "UID/prefix or CONTEXT:UID of one directly owned Memory whose "
                "original text must remain unchanged"
            ),
        ),
    ],
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            metavar="CONTEXT",
            help="Existing READ+UPDATE Context that owns the Memory",
        ),
    ] = None,
) -> None:
    """Append supported detail after one Memory without rewriting its original."""

    try:
        store = MemoryStore(create=False)
        with CommandProgress(
            "ELABORATE",
            "preparing exact Memory context",
            total=2,
        ) as progress:
            receipt = execute_elaborate(
                ElaborateRequest(
                    memory_selector=memory_selector,
                    context_locator=context_name,
                ),
                store=store,
                provider_factory=lambda: (
                    progress.update("writing supported continuation", step=2)
                    or connect_semantic_provider()
                ),
            )
    except (
        ElaborateError,
        FileNotFoundError,
        KeyError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Elaborate error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not receipt.changed:
        annotate_command_outcome("NO_CHANGE")
        typer.echo(
            f"ELABORATE KEPT · {display_escape_text(receipt.context_name)} "
            f"[{receipt.memory_uid[:8]}]"
        )
        typer.echo("WHY · " + display_escape_text(receipt.reason))
        return

    typer.echo(
        f"ELABORATE APPLIED · {display_escape_text(receipt.context_name)} "
        f"[{receipt.memory_uid[:8]}]"
    )
    typer.echo(
        f"EFFECT · APPEND {len(receipt.continuation)} CHARACTERS · "
        "SAME UID · SAME POSITION"
    )
    typer.echo("WHY · " + display_escape_text(receipt.reason))
    typer.echo("UNDO · mem undo")


__all__ = ["cmd"]
