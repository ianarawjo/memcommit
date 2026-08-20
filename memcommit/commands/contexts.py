import typer

from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context_targeting.catalog import (
    freeze_granted_context_navigation,
    grant_navigation_capability_text,
)
from memcommit.context_targeting.resolution import order_context_names_by_hierarchy
from memcommit.interfaces.console.theme import SOURCE_CAPABILITY_RGB
from memcommit.profile_config import ProfileConfigError, load_profile_registry
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


_OWNED_PREFIX = "       "


def _context_name(name: str, *, current: bool) -> str:
    label = display_escape_text(name)
    if not current:
        return label
    return typer.style(label, fg=typer.colors.GREEN, bold=True)


def _current_marker(current: bool) -> str:
    if not current:
        return "  "
    return typer.style("* ", fg=typer.colors.GREEN, bold=True)


def _owned_context_line(name: str, *, current: bool) -> str:
    return (
        _current_marker(current)
        + _OWNED_PREFIX
        + _context_name(
            name,
            current=current,
        )
    )


def _granted_context_line(
    name: str,
    *,
    current: bool,
    capabilities: str,
    authority_profile: str,
) -> str:
    ownership = typer.style("GRANT", bold=True) + "  "
    access = typer.style(
        capabilities,
        fg=SOURCE_CAPABILITY_RGB,
        bold=True,
    )
    return (
        _current_marker(current)
        + ownership
        + _context_name(name, current=current)
        + "  "
        + access
        + " · FROM "
        + display_escape_text(authority_profile)
    )


def cmd() -> None:
    store = MemoryStore()
    # The marker and catalog are one read-only view of the active name captured
    # at command entry; another process may switch after this snapshot.
    current = store.current_context_name()
    names = store.list_context_names()
    if not names:
        typer.echo("No contexts yet. Run 'mem init <name>' to create one.")
        return
    try:
        granted_navigation = freeze_granted_context_navigation(store)
        virtual_names = granted_navigation.names
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
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
    public_names = order_context_names_by_hierarchy(
        (*names, *(name for name in virtual_names if name not in local_names))
    )
    # Contexts is an orientation command, so a terminal receives the same
    # stable catalog as a pipe. Project the local-plus-Grant snapshot through
    # the same public-name hierarchy as Switch instead of creating a second,
    # ownership-grouped ordering; the GRANT prefix carries ownership meaning.
    for name in public_names:
        if name in local_names:
            typer.echo(_owned_context_line(name, current=name == current))
            continue
        candidates = tuple(
            grant
            for grant in active_grants
            if name == grant.public_name or name.startswith(grant.public_name + "/")
        )
        if not candidates:
            continue
        effective = max(
            candidates,
            key=lambda grant: len(grant.public_name.split("/")),
        )
        line = _granted_context_line(
            name,
            current=name == current,
            capabilities=grant_navigation_capability_text(effective.permissions),
            authority_profile=profiles[effective.authority_profile_uid],
        )
        typer.echo(line)
