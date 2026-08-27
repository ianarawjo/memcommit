import typer

from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.console.theme import SOURCE_CAPABILITY_RGB
from memcommit.application.operations.contexts.application import ContextCatalogEntry
from memcommit.application.operations.contexts.runtime import load_contexts_catalog
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


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


def _owned_context_line(entry: ContextCatalogEntry) -> str:
    line = (
        _current_marker(entry.current)
        + _OWNED_PREFIX
        + _context_name(
            entry.name,
            current=entry.current,
        )
    )
    if not entry.portable_name:
        line += "  LEGACY NAME · MIGRATION REQUIRED"
    return line


def _granted_context_line(entry: ContextCatalogEntry) -> str:
    assert entry.capabilities is not None
    assert entry.authority_profile is not None
    ownership = typer.style("GRANT", bold=True) + "  "
    access = typer.style(
        entry.capabilities,
        fg=SOURCE_CAPABILITY_RGB,
        bold=True,
    )
    line = (
        _current_marker(entry.current)
        + ownership
        + _context_name(entry.name, current=entry.current)
        + "  "
        + access
        + " · FROM "
        + display_escape_text(entry.authority_profile)
    )
    if not entry.portable_name:
        line += "  LEGACY GRANT NAME · RECREATE REQUIRED"
    return line


def cmd() -> None:
    store = MemoryStore()
    try:
        catalog = load_contexts_catalog(store)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if not catalog.has_local_contexts:
        typer.echo("No contexts yet. Run 'mem init <name>' to create one.")
        return
    # Contexts is an orientation command, so a terminal receives the same
    # stable catalog as a pipe. Project the local-plus-Grant snapshot through
    # the same public-name hierarchy as Switch instead of creating a second,
    # ownership-grouped ordering; the GRANT prefix carries ownership meaning.
    for entry in catalog.entries:
        line = (
            _owned_context_line(entry)
            if entry.ownership == "OWNED"
            else _granted_context_line(entry)
        )
        typer.echo(line)
