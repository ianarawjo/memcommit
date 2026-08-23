"""CLI boundary for grant-authorized cross-Profile sharing."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.command_attempts import annotate_command_outcome
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.share import (
    ShareError,
    deliver_context,
    deliver_prepared_share,
)
from memcommit.store import ConcurrentContextUpdateError


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(
            help="Ordinary Context to send; omit to enter interactive Share setup"
        ),
    ] = None,
    recipient: Annotated[
        str,
        typer.Option(
            "--to",
            help="Exact grant-backed receiver endpoint",
        ),
    ] = "",
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Send only the exact Source Context",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Send the Source Context and all lexical descendants",
        ),
    ] = False,
) -> None:
    """Copy one ordinary Context scope into its grant-backed receiver Profile."""

    try:
        if direct and recursive:
            raise ShareError("Choose either --direct or --recursive, not both.")
        include_descendants = recursive
        if source is not None and recipient:
            # Complete explicit operands retain the compact automation path,
            # even in a TTY. The bare/incomplete form owns interactive setup.
            delivery = deliver_context(
                source,
                recipient,
                include_descendants=include_descendants,
            )
        elif _interactive_terminal():
            from memcommit.commands.share_flow import (
                ShareFlowUnavailable,
                choose_share_preview,
            )
            from memcommit.commands.share_viewer import (
                run_share_unavailable_viewer,
                run_share_viewer,
            )

            try:
                preview = choose_share_preview(
                    source,
                    recipient or None,
                    include_descendants=include_descendants,
                )
            except ShareFlowUnavailable as unavailable:
                run_share_unavailable_viewer(str(unavailable))
                annotate_command_outcome("CANCELLED")
                typer.echo("Share closed; nothing was sent.")
                return
            if preview is None:
                annotate_command_outcome("CANCELLED")
                typer.echo("Share closed; nothing was sent.")
                return
            receipt = run_share_viewer(preview)
            if receipt.action == "close":
                annotate_command_outcome("CANCELLED")
                typer.echo("Share closed; nothing was sent.")
                return
            delivery = deliver_prepared_share(preview)
        else:
            missing = []
            if source is None:
                missing.append("SOURCE")
            if not recipient:
                missing.append("--to ENDPOINT")
            raise ShareError(
                "Non-interactive Share requires " + " and ".join(missing) + "."
            )
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

    if delivery.created and delivery.include_descendants:
        typer.secho("Shared Context bundle.", fg=typer.colors.GREEN, bold=True)
    elif delivery.created:
        typer.secho("Shared Context.", fg=typer.colors.GREEN, bold=True)
    elif delivery.include_descendants:
        annotate_command_outcome("NO_CHANGE")
        typer.echo("Context bundle was already shared; no duplicate was created.")
    else:
        annotate_command_outcome("NO_CHANGE")
        typer.echo("Context was already shared; no duplicate was created.")
    typer.echo(f"Share: {delivery.uid}")
    typer.echo("To: " + display_escape_text(delivery.endpoint))
    if delivery.include_descendants:
        typer.echo("Contexts: " + str(delivery.context_count))
    typer.echo("Memories: " + str(delivery.memory_count))
    typer.echo("Consent digest: " + delivery.consent_digest)
    typer.echo(
        "Receiver: "
        + display_escape_text(delivery.receiver_profile)
        + ":"
        + display_escape_text(delivery.receiver_context)
    )
