"""CLI for selecting complete local MemoryStore profiles."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated, Optional

import typer

from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import (
    ProfileError,
    default_study_bundle_root,
    import_profile,
    import_study_profiles,
    list_profiles,
    use_profile,
)


app = typer.Typer(
    no_args_is_help=True,
    help="Register and select complete local MemoryStore profiles.",
)


def _fail(error: Exception) -> None:
    typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _profile_rows() -> tuple[object, tuple[object, ...]]:
    try:
        return list_profiles()
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)


@app.command("list")
def list_cmd() -> None:
    """List locally registered whole-store profiles."""

    registry, inspections = _profile_rows()
    for profile, inspection in zip(
        registry.profiles,
        inspections,
        strict=True,
    ):
        marker = "*" if profile.uid == registry.active_uid else " "
        current = inspection.current_context or "(none)"
        query_note = (
            f" · {inspection.query_source_count} query-only"
            if inspection.query_source_count
            else ""
        )
        typer.echo(
            f"{marker} {profile.name:<12} "
            f"{profile.kind.lower():<9} "
            f"{len(inspection.context_names)} Contexts "
            f"· current={current}{query_note}"
        )
    typer.echo("Query-only sources are hidden from 'mem switch'.")


app.command("ls", hidden=True)(list_cmd)


@app.command("current")
def current_cmd() -> None:
    """Show the selected profile and its current Context."""

    registry, inspections = _profile_rows()
    index = next(
        index
        for index, profile in enumerate(registry.profiles)
        if profile.uid == registry.active_uid
    )
    inspection = inspections[index]
    typer.echo(f"Profile: {registry.active.name}")
    typer.echo(f"Store: {inspection.root}")
    typer.echo(f"Current Context: {inspection.current_context or '(none)'}")


@app.command("use")
def use_cmd(
    name: Annotated[
        Optional[str],
        typer.Argument(help="Registered profile name; omit to enter it interactively"),
    ] = None,
) -> None:
    """Select the complete store used by the next mem invocation."""

    if name is None:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            _fail(
                ProfileError(
                    "Interactive profile selection requires a terminal. "
                    "Pass a profile name explicitly."
                )
            )
        registry, _inspections = _profile_rows()
        typer.echo("Profiles: " + ", ".join(item.name for item in registry.profiles))
        name = typer.prompt("Use profile", default=registry.active.name)
    try:
        registry, inspection, changed = use_profile(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    if not changed:
        typer.echo(f"Already using profile '{registry.active.name}'.")
        return
    typer.secho(
        f"Selected profile '{registry.active.name}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        f"The next mem command will see {len(inspection.context_names)} "
        "ordinary Contexts."
    )
    typer.echo(f"Current Context: {inspection.current_context or '(none)'}")
    if inspection.query_source_count:
        typer.echo(
            f"{inspection.query_source_count} query-only source(s) remain "
            "hidden from 'mem switch'."
        )


@app.command("import")
def import_cmd(
    name: Annotated[str, typer.Argument(help="New managed profile name")],
    source: Annotated[
        Path,
        typer.Option("--from", help="Complete .mem store or package directory"),
    ],
) -> None:
    """Copy one complete store into a new editable managed profile."""

    try:
        profile, inspection = import_profile(name, source)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho(f"Imported profile '{profile.name}'.", fg=typer.colors.GREEN)
    typer.echo(
        f"{len(inspection.context_names)} ordinary Contexts · "
        f"current={inspection.current_context or '(none)'}"
    )
    typer.echo("The source store was not modified.")


@app.command("import-study")
def import_study_cmd(
    source: Annotated[
        Optional[Path],
        typer.Option(
            "--from",
            help=(
                "Directory containing task-1, task-2, and task-3 packages; "
                "defaults to this checkout's generated bundles"
            ),
        ),
    ] = None,
) -> None:
    """Copy all three study packages into editable isolated profiles."""

    bundle_root = source or default_study_bundle_root()
    try:
        result = import_study_profiles(bundle_root)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho("Imported editable study profiles.", fg=typer.colors.GREEN)
    for profile, inspection in zip(
        result.profiles,
        result.inspections,
        strict=True,
    ):
        typer.echo(
            f"  {profile.name}: {len(inspection.context_names)} ordinary "
            f"Contexts · current={inspection.current_context or '(none)'} · "
            f"{inspection.query_source_count} query-only source(s)"
        )
    typer.echo("The authoring store and generated package sources were not modified.")
    typer.echo("Use one with: mem profile use task-1")
