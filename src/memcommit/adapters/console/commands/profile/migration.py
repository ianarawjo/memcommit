"""Legacy Context name migration preview and exact Apply adapter."""

from __future__ import annotations

import shlex
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.profile._support import _fail
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import (
    AuthorityGrant,
    ProfileConfigError,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.core.context_targeting.naming import is_portable_context_name


def _context_migration_grant_blockers(
    old_name: str,
) -> tuple[ProfileRegistry, tuple[AuthorityGrant, ...]]:
    """Return Grants whose frozen locator identity would be invalidated."""

    registry = load_profile_registry()

    def moved(name: str) -> bool:
        return name == old_name or name.startswith(old_name + "/")

    blockers = tuple(
        grant
        for grant in registry.grants
        if (
            grant.authority_profile_uid == registry.active.uid
            and (
                moved(grant.resource_name)
                or any(moved(binding.name) for binding in grant.contexts)
            )
        )
    )
    return registry, blockers


def _migration_shell_join(argv: tuple[str, ...]) -> str:
    """Render a copyable zsh/bash command without raw display controls."""

    def quote(argument: str) -> str:
        if display_escape_text(argument) == argument:
            return shlex.quote(argument)
        escaped: list[str] = []
        for character in argument:
            codepoint = ord(character)
            if character in {"'", "\\"}:
                escaped.append("\\" + character)
            elif 0x20 <= codepoint <= 0x7E:
                escaped.append(character)
            elif codepoint <= 0xFFFF:
                escaped.append(f"\\u{codepoint:04x}")
            else:
                escaped.append(f"\\U{codepoint:08x}")
        return "$'" + "".join(escaped) + "'"

    return " ".join(quote(argument) for argument in argv)


def migrate_context_cmd(
    old_name: Annotated[
        str,
        typer.Argument(
            metavar="LEGACY_CONTEXT",
            help="Existing non-portable ordinary Context namespace root",
        ),
    ],
    new_name: Annotated[
        str,
        typer.Argument(
            metavar="PORTABLE_CONTEXT",
            help="New portable namespace root",
        ),
    ],
    apply_migration: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Apply the exact plan; omit to preview without changing data",
        ),
    ] = False,
    expected_profile_uid: Annotated[
        Optional[str],
        typer.Option(
            "--expect-profile",
            metavar="UUID",
            help="Require the exact Profile identity printed by the preview",
        ),
    ] = None,
    expected_graph_digest: Annotated[
        Optional[str],
        typer.Option(
            "--expect-graph",
            metavar="SHA256",
            help="Require the exact Context graph printed by the preview",
        ),
    ] = None,
) -> None:
    """Migrate one legacy Context namespace to a portable canonical name."""

    from memcommit.persistence.store import MemoryStore

    if is_portable_context_name(old_name):
        _fail(
            ValueError(
                f"Context name {old_name!r} is already portable. This command "
                "only migrates legacy names and is not a general rename route."
            )
        )
    if apply_migration and (
        expected_profile_uid is None or expected_graph_digest is None
    ):
        _fail(
            ValueError("Preview this migration first and run its exact Apply command.")
        )
    if not apply_migration and (
        expected_profile_uid is not None or expected_graph_digest is not None
    ):
        _fail(
            ValueError(
                "--expect-profile and --expect-graph belong to the previewed "
                "--apply command."
            )
        )
    try:
        registry, blockers = _context_migration_grant_blockers(old_name)
        if (
            expected_profile_uid is not None
            and registry.active.uid != expected_profile_uid
        ):
            raise ProfileError(
                "The active Profile changed after this migration was reviewed."
            )
        # Freeze the same Profile root whose Grant relationships were
        # inspected. A concurrent `profile use` must not retarget this plan.
        store = MemoryStore(
            create=False,
            root=profile_store_dir(registry.active),
        )
        plan = store.plan_context_rename(old_name, new_name)
        if (
            expected_graph_digest is not None
            and plan.graph_digest != expected_graph_digest
        ):
            raise RuntimeError(
                "The Context graph changed after this migration was reviewed."
            )
    except (
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        _fail(error)

    typer.echo("Context name migration")
    typer.echo(f"  Profile: {display_escape_text(registry.active.name)}")
    typer.echo(f"  Source: {display_escape_text(plan.old_name)}")
    typer.echo(f"  Destination: {display_escape_text(plan.new_name)}")
    typer.echo(f"  Contexts: {len(plan.bindings)}")
    remaining_legacy = tuple(
        binding.new_name
        for binding in plan.bindings
        if not is_portable_context_name(binding.new_name)
    )
    typer.echo(f"  Remaining legacy descendants: {len(remaining_legacy)}")
    typer.echo(f"  Live references: {plan.reference_count}")
    typer.echo(f"  Checkpoint references: {plan.checkpoint_reference_count}")
    typer.echo(
        "  Derived bindings: "
        f"translation {plan.translation_artifact_count}, "
        f"Meld {plan.meld_session_count}"
    )
    if blockers:
        typer.echo("  Grant blockers: " + ", ".join(item.uid for item in blockers))
        typer.echo(
            "Revoke each listed Grant with 'mem profile grant delete GRANT', "
            "run the migration, then recreate the Grant with portable names."
        )
        if apply_migration:
            _fail(
                ProfileError(
                    "Context migration is blocked by frozen cross-Profile Grants that "
                    "still reference the current name."
                )
            )
        typer.echo("PLAN ONLY · APPLY BLOCKED · NOTHING CHANGED")
        return

    if not apply_migration:
        command = _migration_shell_join(
            (
                "mem",
                "profile",
                "migrate-context",
                "--expect-profile",
                registry.active.uid,
                "--expect-graph",
                plan.graph_digest,
                "--apply",
                "--",
                old_name,
                new_name,
            )
        )
        typer.echo("PLAN ONLY · NOTHING CHANGED")
        typer.echo(f"Apply: {command}")
        return

    try:
        result = store.rename_contexts(plan)
    except (OSError, ProfileConfigError, RuntimeError, ValueError) as error:
        _fail(error)
    typer.secho("Context name migration applied.", fg=typer.colors.GREEN)
    typer.echo(
        f"Migrated {result.renamed_context_count} Context(s); "
        f"current={display_escape_text(result.current_context or '(none)')}."
    )
    if remaining_legacy:
        typer.echo(
            "Run another migration for each remaining legacy descendant: "
            + ", ".join(display_escape_text(name) for name in remaining_legacy)
        )
