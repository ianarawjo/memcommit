"""Git-style console grammar composed from Branch and Switch."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands import branch, switch


def cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Context to switch to; omit to enter the switch picker, or "
                "with -b omit to choose a branch Source and name"
            )
        ),
    ] = None,
    b: Annotated[
        bool,
        typer.Option(
            "-b",
            "--branch",
            help="Create a branch; without NAME choose its local Source and name",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="With -b, branch only the selected Source root",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="With -b, branch the Source root and lexical descendants",
        ),
    ] = False,
) -> None:
    """Route Git-style checkout syntax to Switch or, with ``-b``, Branch."""

    if b:
        branch.cmd(
            name,
            source_descendants=None,
            direct=direct,
            recursive=recursive,
        )
        return
    if direct or recursive:
        raise typer.BadParameter("-d/-r require -b/--branch.")
    switch.cmd(name)


__all__ = ["cmd"]

