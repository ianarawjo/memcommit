"""CLI for selecting complete local MemoryStore profiles."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated, Optional

import typer

from memcommit.commands.profile_picker import ProfilePickerEntry, choose_profile
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
    invoke_without_command=True,
    no_args_is_help=False,
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


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _pick_profile() -> str | None:
    registry, inspections = _profile_rows()
    entries = tuple(
        ProfilePickerEntry(
            name=profile.name,
            context_count=len(inspection.context_names),
            current_context=inspection.current_context,
            query_source_count=inspection.query_source_count,
        )
        for profile, inspection in zip(
            registry.profiles,
            inspections,
            strict=True,
        )
    )
    try:
        return choose_profile(entries, current=registry.active.name)
    except ValueError as error:
        _fail(ProfileError(str(error)))


def _use_profile(name: str) -> None:
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


@app.callback(invoke_without_command=True)
def profile_cmd(ctx: typer.Context) -> None:
    """Open the Profile selector, or print its stable non-TTY list."""

    if ctx.invoked_subcommand is not None:
        return
    if not _interactive_terminal():
        list_cmd()
        return
    selected = _pick_profile()
    if selected is None:
        typer.echo("Profile selection cancelled.")
        return
    _use_profile(selected)


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
        action = "CURRENT" if profile.uid == registry.active_uid else "USE"
        current = inspection.current_context or "(none)"
        query_note = (
            f" · {inspection.query_source_count} query-only"
            if inspection.query_source_count
            else ""
        )
        typer.echo(
            f"{marker} {profile.name:<12} "
            f"{action:<7} "
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
        if not _interactive_terminal():
            _fail(
                ProfileError(
                    "Interactive profile selection requires a terminal. "
                    "Pass a profile name explicitly."
                )
            )
        name = _pick_profile()
        if name is None:
            typer.echo("Profile selection cancelled.")
            return
    _use_profile(name)


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
