import typer

from memcommit.commands.granted_context import attached_grants
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def cmd() -> None:
    store = MemoryStore()
    # The marker and catalog are one read-only view of the active name captured
    # at command entry; another process may switch after this snapshot.
    current = store.current_context_name()
    names = store.list_context_names()
    if not names:
        typer.echo("No contexts yet. Run 'mem init <name>' to create one.")
        return
    for name in names:
        label = display_escape_text(name)
        if name == current:
            typer.secho(f"* {label}", fg=typer.colors.GREEN, bold=True)
        else:
            typer.echo(f"  {label}")
    if current:
        try:
            registry, grants = attached_grants(current)
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        profiles = {profile.uid: profile.name for profile in registry.profiles}
        for grant in grants:
            mode = ",".join(
                permission.lower() for permission in grant.permissions
            )
            typer.echo(
                "  "
                + display_escape_text(grant.public_name)
                + "  [view "
                + mode
                + " from "
                + display_escape_text(profiles[grant.authority_profile_uid])
                + "]"
            )
