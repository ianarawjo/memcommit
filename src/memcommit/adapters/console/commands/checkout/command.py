"""Git-style console grammar composed from Branch and Switch."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands import switch
from memcommit.adapters.console.commands import branch
from memcommit.application.operations.checkout import (
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
                "with -b provide a new branch name"
            )
        ),
    ] = None,
    b: Annotated[
        bool,
        typer.Option(
            "-b",
            "--branch",
            help="Create a branch of the current Context; requires NAME",
        ),
    ] = False,
) -> None:
    """Route Git-style checkout syntax to Switch or, with ``-b``, Branch."""

    plan = plan_checkout(CheckoutRequest(name=name, create_branch=b))
    if plan.action is CheckoutAction.BRANCH:
        # Branch owns current-Context input validation and its default range.
        branch.cmd(plan.name)
        return
    switch.cmd(plan.name)


__all__ = ["cmd"]
