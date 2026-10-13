"""Inspect and configure the selected Profile's single project root."""

import typer

from memcommit.application.operations.profile.config import load_profile_registry, profile_root_dir, profile_store_dir, ProfileConfigError
from memcommit.application.operations.profile.root_configuration import relocate_profile_root
from ._support import _fail
from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup

app = typer.Typer(cls=CanonicalCommandGroup, invoke_without_command=True, no_args_is_help=False)


@app.callback(invoke_without_command=True)
def show_configuration(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        profile = load_profile_registry().active
        typer.echo(f"Profile: {profile.name}")
        typer.echo(f"root_dir = {profile_root_dir(profile)}")
        typer.echo(f"Store = {profile_store_dir(profile)}")
        typer.echo(f"Sync = {profile_root_dir(profile)}")


@app.command("set")
def set_configuration(key: str, value: str):
    try:
        if key != "root_dir":
            raise ValueError("Profile configuration supports root_dir.")
        profile = relocate_profile_root(value)
    except (OSError, ValueError, ProfileConfigError) as error:
        _fail(error)
    typer.echo(f"Profile {profile.name}: root_dir = {profile_root_dir(profile)}")
    typer.echo("Store and connected documents verified; previous files retained.")
