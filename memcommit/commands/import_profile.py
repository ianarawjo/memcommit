"""Import Profiles, Contexts, or Memories while preserving identity."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError, import_baseline_profile
from memcommit.resource_import import (
    import_context_from_profile,
    import_memory_from_profile,
    import_profile_from_profile,
)


_RESOURCE_KINDS = {"profile", "context", "memory"}


def _fail(message: str) -> None:
    typer.secho(
        "Error: " + display_escape_text(message),
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(1)


def _reject_options(
    values: dict[str, object],
    *,
    allowed: set[str],
) -> None:
    unexpected = sorted(
        name
        for name, value in values.items()
        if name not in allowed and value not in {None, False}
    )
    if unexpected:
        _fail("Unsupported option(s) for this import: " + ", ".join(unexpected))


def _profile_import(
    name: str,
    *,
    source: Path | None,
    source_profile: str | None,
) -> None:
    if (source is None) == (source_profile is None):
        _fail("Profile import requires exactly one of --from or --from-profile.")
    if source_profile is not None:
        profile, inspection = import_profile_from_profile(name, source_profile)
    else:
        assert source is not None
        profile, inspection = import_baseline_profile(name, source)

    typer.secho(
        f"Imported clean baseline Profile '{display_escape_text(profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    current = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.echo(
        f"Contexts {len(inspection.context_names)} · "
        f"Memories {inspection.ordinary_memory_count} · current={current}"
    )
    source_record = profile.source or {}
    typer.echo("Baseline SHA-256: " + str(source_record.get("baseline_sha256", "")))
    typer.echo(
        "Checkpoint history, sessions, caches, locks, and run logs were not imported."
    )
    typer.echo("The source and active Profile were not changed.")


def cmd(
    kind_or_name: Annotated[
        str,
        typer.Argument(
            help=(
                "Resource kind (profile/context/memory), or a Profile name "
                "for the legacy 'mem import NAME --from PATH' form"
            )
        ),
    ],
    resource_name: Annotated[
        Optional[str],
        typer.Argument(
            help="New Profile name, source Context locator, or source Memory UID"
        ),
    ] = None,
    source: Annotated[
        Optional[Path],
        typer.Option("--from", help="External source .mem store or package"),
    ] = None,
    source_profile: Annotated[
        Optional[str],
        typer.Option("--from-profile", help="Registered source Profile name"),
    ] = None,
    source_context: Annotated[
        Optional[str],
        typer.Option("--context", help="Source Context containing a Memory"),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option("--as", help="New root name for an imported Context"),
    ] = None,
    target_context: Annotated[
        Optional[str],
        typer.Option("--into", help="Existing active-Profile Context for a Memory"),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", help="Include lexical descendant Contexts"),
    ] = False,
) -> None:
    """Import one resource by value without copying source operational history."""

    options: dict[str, object] = {
        "--from": source,
        "--from-profile": source_profile,
        "--context": source_context,
        "--as": target_name,
        "--into": target_context,
        "--recursive": recursive,
    }
    kind = kind_or_name.casefold()
    if kind not in _RESOURCE_KINDS:
        if resource_name is not None:
            _fail("Legacy Profile import accepts only one positional Profile name.")
        _reject_options(options, allowed={"--from"})
        if source is None:
            _fail("Legacy Profile import requires --from PATH.")
        kind = "profile"
        resource_name = kind_or_name
    elif resource_name is None:
        _fail(f"{kind.title()} import requires a resource name or selector.")

    assert resource_name is not None
    try:
        if kind == "profile":
            _reject_options(options, allowed={"--from", "--from-profile"})
            _profile_import(
                resource_name,
                source=source,
                source_profile=source_profile,
            )
            return

        if kind == "context":
            _reject_options(
                options,
                allowed={"--from-profile", "--as", "--recursive"},
            )
            if source_profile is None:
                _fail("Context import requires --from-profile NAME.")
            result = import_context_from_profile(
                source_profile,
                resource_name,
                target_name=target_name,
                recursive=recursive,
            )
            typer.secho(
                f"Imported {result.context_count} Context(s) from Profile "
                f"'{display_escape_text(result.source_profile)}'.",
                fg=typer.colors.GREEN,
            )
            typer.echo(
                "Contexts: "
                + ", ".join(
                    display_escape_text(name) for name in result.target_contexts
                )
            )
            typer.echo(
                f"Direct Memories: {result.memory_count} · "
                "source and active Profile selection unchanged"
            )
            return

        _reject_options(
            options,
            allowed={"--from-profile", "--context", "--into"},
        )
        if source_profile is None or source_context is None:
            _fail("Memory import requires --from-profile NAME and --context SOURCE.")
        result = import_memory_from_profile(
            source_profile,
            source_context,
            resource_name,
            target_context_locator=target_context,
        )
        typer.secho(
            f"Imported Memory [{result.memory.uid[:8]}] into Context "
            f"'{display_escape_text(result.target_context)}'.",
            fg=typer.colors.GREEN,
        )
        typer.echo(display_escape_text(result.memory.content))
        typer.echo("Source and active Profile selection unchanged.")
    except typer.Exit:
        raise
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _fail(str(error))
