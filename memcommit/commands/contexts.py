import sys

import typer

from memcommit.commands.context_picker import choose_context, context_memory_rows
from memcommit.authority.access import (
    resolve_context_access,
)
from memcommit.commands.readable_context_catalog import (
    freeze_profile_context_navigation,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context_targeting.catalog import (
    freeze_granted_context_navigation,
)
from memcommit.profile_config import ProfileConfigError, load_profile_registry
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore
from memcommit.source_projection.presentation import source_display_text


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _browse_contexts(
    store: MemoryStore,
    *,
    current: str | None,
    names: list[str],
) -> None:
    """Open the shared Context tree without returning an executable target."""

    granted_navigation = freeze_granted_context_navigation(store)
    readable_names = set(names) | set(granted_navigation.selectable_names)
    initial_name = current if current in readable_names else names[0]
    initial_access = resolve_context_access(
        store,
        initial_name,
        current_name=current,
        required_permission="READ",
    )
    navigation = freeze_profile_context_navigation(
        store,
        initial_access,
        granted_navigation=granted_navigation,
    )

    def load_memories(context_name: str):
        return context_memory_rows(navigation.catalog.load(context_name))

    # The return value is intentionally discarded. Browse mode never produces
    # a Context target, and this command has no state-writing continuation.
    choose_context(
        navigation.local_names,
        current=initial_name,
        title="Browse Contexts",
        virtual_names=navigation.virtual_names,
        selectable_virtual_names=navigation.selectable_virtual_names,
        virtual_annotations=navigation.virtual_annotations,
        memory_loader=load_memories,
        browse_only=True,
        initially_expand_selected=False,
        initially_expand_all=False,
        initially_show_memories=False,
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
    if _interactive_terminal():
        try:
            _browse_contexts(
                store,
                current=current,
                names=names,
            )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        return

    try:
        granted_navigation = freeze_granted_context_navigation(store)
        virtual_names = granted_navigation.names
        annotations = granted_navigation.annotations
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Noninteractive output remains a stable, line-oriented catalog for pipes,
    # test runners, and agents that cannot drive the full-screen browser.
    for name in names:
        label = display_escape_text(name)
        if name == current:
            typer.secho(f"* {label}", fg=typer.colors.GREEN, bold=True)
        else:
            typer.echo(f"  {label}")
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
    for name in virtual_names:
        if name in local_names:
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
