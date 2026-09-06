"""Typer composition and entry routing for Profile commands."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.profile._support import (
    _fail,
    _interactive_terminal,
)
from memcommit.adapters.console.commands.profile.grants import grant_app
from memcommit.adapters.console.commands.profile.group import ProfileAliasGroup
from memcommit.adapters.console.commands.profile.inventory import current_cmd, list_cmd
from memcommit.adapters.console.commands.profile.lifecycle import (
    _use_profile,
    create_cmd,
    import_cmd,
    remove_cmd,
    rename_cmd,
)
from memcommit.adapters.console.commands.profile.migration import migrate_context_cmd
from memcommit.adapters.console.commands.profile.selector import _run_profile_selector
from memcommit.adapters.console.commands.profile.study_profile import (
    archive_study_cmd,
    remove_study_cmd,
    rename_study_cmd,
)
from memcommit.application.operations.profile.model._storage import ProfileError

app = typer.Typer(
    cls=ProfileAliasGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    subcommand_metavar="COMMAND|PROFILE",
    help=(
        "Create, register, and select complete local MemoryStore profiles. "
        "Use 'mem profile NAME' to select one."
    ),
)
app.add_typer(grant_app, name="grant")


def profile_cmd(ctx: typer.Context) -> None:
    """Enter the Profile selector, or print its stable non-TTY list."""

    if ctx.invoked_subcommand is not None:
        return
    if not _interactive_terminal():
        list_cmd()
        return
    _run_profile_selector()


def use_cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(help="Registered profile name; omit to enter it interactively"),
    ] = None,
) -> None:
    """Select the complete store used by the next mem invocation."""

    if name is None:
        if not _interactive_terminal():
            _fail(
                ProfileError(
                    "Interactive profile selection requires a terminal. "
                    "Pass a profile name explicitly."
                )
            )
        _run_profile_selector()
        return
    _use_profile(name)


# Register here so handler modules never depend back on the root app.
app.callback(invoke_without_command=True)(profile_cmd)
app.command("list")(list_cmd)
app.command("ls", hidden=True)(list_cmd)
app.command("current")(current_cmd)
app.command("create")(create_cmd)
app.command("use")(use_cmd)
app.command("remove")(remove_cmd)
app.command("remove-study")(remove_study_cmd)
app.command("rename")(rename_cmd)
app.command("rename-study")(rename_study_cmd)
app.command("migrate-context")(migrate_context_cmd)
app.command("import")(import_cmd)
app.command("archive-study")(archive_study_cmd)
