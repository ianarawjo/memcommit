"""Import Profiles, Contexts, or Memories while preserving identity."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated, Optional

import typer

from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError, import_baseline_profile
from memcommit.operations.resource_import.model import (
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
    expected_source_profile_uid: str | None = None,
) -> None:
    if (source is None) == (source_profile is None):
        _fail("Profile import requires exactly one of --from or --from-profile.")
    if source_profile is not None:
        profile, inspection = import_profile_from_profile(
            name,
            source_profile,
            expected_source_profile_uid=expected_source_profile_uid,
        )
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


def _print_context_import(result) -> None:
    typer.secho(
        f"Imported {result.context_count} Context(s) from Profile "
        f"'{display_escape_text(result.source_profile)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "Contexts: "
        + ", ".join(display_escape_text(name) for name in result.target_contexts)
    )
    typer.echo(
        f"Direct Memories: {result.memory_count} · "
        "source and active Profile selection unchanged"
    )


def _print_memory_import(result) -> None:
    typer.secho(
        f"Imported Memory [{result.memory.uid[:8]}] into Context "
        f"'{display_escape_text(result.target_context)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(display_escape_text(result.memory.content))
    typer.echo("Source and active Profile selection unchanged.")


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _run_interactive_import() -> None:
    from memcommit.commands.import_workbench import choose_import_setup

    setup = choose_import_setup()
    if setup is None:
        typer.echo("Import cancelled.")
        return
    if setup.kind == "PROFILE":
        assert setup.target_name is not None
        _profile_import(
            setup.target_name,
            source=None,
            source_profile=setup.source_profile_name,
            expected_source_profile_uid=setup.source_profile_uid,
        )
        return
    if setup.kind == "CONTEXT":
        assert setup.source_context is not None
        assert setup.target_name is not None
        assert setup.context_plan is not None
        result = import_context_from_profile(
            setup.source_profile_name,
            setup.source_context,
            target_name=setup.target_name,
            recursive=setup.recursive,
            expected_plan=setup.context_plan,
        )
        _print_context_import(result)
        return
    assert setup.source_context is not None
    assert setup.memory_selector is not None
    assert setup.target_context is not None
    assert setup.memory_plan is not None
    result = import_memory_from_profile(
        setup.source_profile_name,
        setup.source_context,
        setup.memory_selector,
        target_context_locator=setup.target_context,
        expected_plan=setup.memory_plan,
    )
    _print_memory_import(result)


def cmd(
    kind_or_name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Resource kind (profile/context/memory), or a Profile name "
                "for the legacy 'mem import NAME --from PATH' form"
            )
        ),
    ] = None,
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
        typer.Option(
            "-r",
            "--recursive",
            help="Include lexical descendant Contexts",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Import only the selected Context root",
        ),
    ] = False,
) -> None:
    """Import one resource by value without copying source operational history."""

    if kind_or_name is None:
        if not _interactive_terminal():
            _fail(
                "Interactive import setup requires a terminal; pass a resource "
                "kind and operands explicitly."
            )
        try:
            _run_interactive_import()
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
        return

    try:
        recursive = (
            resolve_scope_preset(
                direct=direct,
                recursive=recursive,
                default=ContextScopePreset.DIRECT,
            )
            is ContextScopePreset.RECURSIVE
        )
    except ValueError as error:
        _fail(str(error))

    options: dict[str, object] = {
        "--from": source,
        "--from-profile": source_profile,
        "--context": source_context,
        "--as": target_name,
        "--into": target_context,
        "--direct": direct,
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
                allowed={"--from-profile", "--as", "--direct", "--recursive"},
            )
            if source_profile is None:
                _fail("Context import requires --from-profile NAME.")
            result = import_context_from_profile(
                source_profile,
                resource_name,
                target_name=target_name,
                recursive=recursive,
            )
            _print_context_import(result)
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
        _print_memory_import(result)
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
