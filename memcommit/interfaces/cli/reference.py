"""CLI adapter for immutable Memory snapshot References."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.reference_application import ReferenceRequest, ReferenceResult
from memcommit.reference_runtime import execute_reference
from memcommit.store import MemoryStore


def render_reference_plain(result: ReferenceResult) -> None:
    typer.secho(
        f"Referenced snapshot [{result.memory_uid[:8]}] from "
        f"'{display_escape_text(result.source_name)}' as "
        f"[{result.reference_uid[:8]}] in "
        f"'{display_escape_text(result.into_name)}'.",
        fg=typer.colors.GREEN,
    )


def cmd(
    selector: Annotated[
        str,
        typer.Argument(help="UID (or unambiguous prefix) of the Source Memory"),
    ],
    source_name: Annotated[
        str,
        typer.Option("--from", help="Context that directly owns the Source Memory"),
    ],
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help="Local Context to retain the snapshot (defaults to current)",
        ),
    ] = None,
) -> None:
    try:
        result = execute_reference(
            ReferenceRequest(
                memory_selector=selector,
                source_locator=source_name,
                into_locator=into,
            ),
            store=MemoryStore(),
        )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    render_reference_plain(result)


__all__ = ["cmd", "render_reference_plain"]
