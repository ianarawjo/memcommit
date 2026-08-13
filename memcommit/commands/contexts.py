import typer

from memcommit.commands.switch import _granted_picker_views
from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError, load_profile_registry
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore
from memcommit.source_projection.presentation import source_display_text


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
    try:
        virtual_names, annotations = _granted_picker_views(store)
        registry = load_profile_registry()
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    profiles = {profile.uid: profile.name for profile in registry.profiles}
    active_grants = tuple(
        grant
        for grant in registry.grants
        if grant.grantee_profile_uid == registry.active.uid
    )
    local_names = frozenset(names)
    for name in virtual_names:
        if name in local_names:
            continue
        candidates = tuple(
            grant
            for grant in active_grants
            if name == grant.public_name
            or name.startswith(grant.public_name + "/")
        )
        if not candidates:
            continue
        effective = max(
            candidates,
            key=lambda grant: len(grant.public_name.split("/")),
        )
        annotation = (
            source_display_text(annotations[name])
            + " · FROM "
            + display_escape_text(profiles[effective.authority_profile_uid])
        )
        line = (
            ("* " if name == current else "  ")
            + display_escape_text(name)
            + "  "
            + annotation
        )
        if name == current:
            typer.secho(line, fg=typer.colors.GREEN, bold=True)
        else:
            typer.echo(line)
