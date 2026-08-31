"""Git-style console grammar composed from Branch and Switch."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.browse_navigate import switch
from memcommit.adapters.console.commands.create_copy_connect import branch
from memcommit.application.operations.browse_navigate.checkout import (
    CheckoutAction,
    CheckoutRequest,
    plan_checkout,
)


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

    try:
        plan = plan_checkout(
            CheckoutRequest(
                name=name,
                create_branch=b,
                direct=direct,
                recursive=recursive,
            )
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    if plan.action is CheckoutAction.BRANCH:
        branch.cmd(
            plan.name,
            source_descendants=None,
            direct=plan.direct,
            recursive=plan.recursive,
        )
        return
    switch.cmd(plan.name)


__all__ = ["cmd"]
