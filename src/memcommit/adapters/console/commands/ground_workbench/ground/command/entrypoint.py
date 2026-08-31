"""Typer surface for physical Ground workspaces."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.ground_workbench.ground.command.workflow import (
    GroundCommandRequest,
    run_ground_command,
)


def cmd(
    ground_name: Annotated[
        Optional[str],
        typer.Argument(
            metavar="[GROUND_NAME]",
            show_default=False,
            help=(
                "Context-rooted Ground workspace to create or open, or a "
                "natural-language starting request; omit to open the Ground "
                "launcher in a terminal"
            ),
        ),
    ] = None,
    request: Annotated[
        Optional[str],
        typer.Option("--request", help="Explicit unsaved starting request"),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Enter the interactive Ground workspace launcher",
        ),
    ] = False,
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            help=(
                "Initial Goal from a Context, CONTEXT:UID/UID Memory, or "
                "inline text; materialized as one /goals Memory"
            ),
        ),
    ] = None,
    set_goal: Annotated[
        Optional[str],
        typer.Option(
            "--set-goal",
            help=(
                "Add or replace the one /goals Memory from a Context, "
                "CONTEXT:UID/UID Memory, or inline text"
            ),
        ),
    ] = None,
    add_rule: Annotated[
        Optional[str],
        typer.Option("--add-rule", help="Add one reviewed Rule Memory"),
    ] = None,
    add_example: Annotated[
        Optional[str],
        typer.Option("--add-example", help="Add one reviewed Example Memory"),
    ] = None,
    add_relation: Annotated[
        Optional[str],
        typer.Option("--add-relation", help="Add one reviewed relation Memory"),
    ] = None,
    undo_local: Annotated[
        bool,
        typer.Option(
            "--undo",
            help="Undo the latest command owned by this Ground workspace",
        ),
    ] = False,
    if_ground_revision: Annotated[
        Optional[int],
        typer.Option(
            "--if-revision",
            min=0,
            help="Require this exact physical Ground revision",
        ),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option("--snapshot", help="Print the physical workspace view"),
    ] = False,
    resume_draft: Annotated[
        Optional[str],
        typer.Option("--resume-draft", hidden=True),
    ] = None,
) -> None:
    """Create, open, or edit one physical Context-rooted Ground."""

    return run_ground_command(
        GroundCommandRequest(
            ground_name=ground_name,
            request=request,
            sessions=sessions,
            goal=goal,
            set_goal=set_goal,
            add_rule=add_rule,
            add_example=add_example,
            add_relation=add_relation,
            undo_local=undo_local,
            if_ground_revision=if_ground_revision,
            snapshot=snapshot,
            resume_draft=resume_draft,
        )
    )
