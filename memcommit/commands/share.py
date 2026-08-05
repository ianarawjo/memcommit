"""CLI boundary for grant-authorized cross-Profile sharing."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.share import ShareError, deliver_context
from memcommit.store import ConcurrentContextUpdateError


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(
            help="Applied Sever output Context; defaults to the current Context"
        ),
    ] = None,
    recipient: Annotated[
        str,
        typer.Option(
            "--to",
            help="Exact grant-backed receiver endpoint",
        ),
    ] = "",
) -> None:
    """Copy one reviewed consent unit into its grant-backed receiver Profile."""

    if not recipient:
        typer.secho("Error: --to is required.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        delivery = deliver_context(source, recipient)
    except (
        ConcurrentContextUpdateError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        ShareError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if delivery.created:
        typer.secho("Shared consent unit.", fg=typer.colors.GREEN, bold=True)
    else:
        typer.echo("Consent unit was already shared; no duplicate was created.")
    typer.echo(f"Share: {delivery.uid}")
    typer.echo("To: " + display_escape_text(delivery.endpoint))
    typer.echo("Memories: " + str(delivery.memory_count))
    typer.echo("Consent digest: " + delivery.consent_digest)
    typer.echo(
        "Receiver: "
        + display_escape_text(delivery.receiver_profile)
        + ":"
        + display_escape_text(delivery.receiver_context)
    )
