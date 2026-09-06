"""Authority Grant subcommands and their console presentation."""

from __future__ import annotations

from typing import Annotated

import typer

from memcommit.adapters.console.commands.profile._support import _fail
from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    canonical_grant_permissions,
)
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.application.operations.profile.model.grants import (
    create_authority_grant,
    delete_authority_grant,
    grant_placement,
    list_authority_grants,
    update_authority_grant,
)

grant_app = typer.Typer(
    cls=CanonicalCommandGroup,
    no_args_is_help=True,
    help="Grant, inspect, revise, or revoke cross-Profile Context views.",
)


def _grant_permissions_label(permissions: tuple[str, ...]) -> str:
    return ",".join(permission.lower() for permission in permissions)


def _print_grant(registry, grant, *, prefix: str = "") -> None:
    profiles = {profile.uid: profile.name for profile in registry.profiles}
    authority = display_escape_text(profiles[grant.authority_profile_uid])
    grantee = display_escape_text(profiles[grant.grantee_profile_uid])
    access_name = display_escape_text(
        grant_placement(registry, grant).access_name
    )
    resource = display_escape_text(grant.resource_name)
    typer.echo(
        f"{prefix}{grant.uid[:8]} · {authority}:{resource} -> "
        f"{grantee}:{access_name} · "
        f"{_grant_permissions_label(grant.permissions)} · "
        f"{len(grant.contexts)} Context(s) · revision {grant.revision}"
    )


def grant_list_cmd() -> None:
    """List cross-Profile Context views without opening authority content."""

    try:
        registry, grants = list_authority_grants()
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    if not grants:
        typer.echo("No authority grants.")
        return
    for grant in grants:
        _print_grant(registry, grant)


def grant_create_cmd(
    authority: Annotated[
        str,
        typer.Argument(help="Profile that owns the ordinary source Context"),
    ],
    grantee: Annotated[
        str,
        typer.Argument(help="Profile receiving the view"),
    ],
    resource: Annotated[
        str,
        typer.Argument(help="Authority Context-tree root"),
    ],
    permissions: Annotated[
        list[str],
        typer.Option(
            "--allow",
            help=(
                "Permission to grant; repeat QUERY, CREATE, READ, "
                "UPDATE/EDIT, DELETE, or SHARE"
            ),
        ),
    ],
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include the resource's current descendants in this grant",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Include only the selected resource root in this grant",
        ),
    ] = False,
) -> None:
    """Grant a frozen Context view or SHARE delivery endpoint."""

    try:
        recursive = (
            resolve_scope_preset(
                direct=direct,
                recursive=recursive,
                default=ContextScopePreset.DIRECT,
            )
            is ContextScopePreset.RECURSIVE
        )
        permissions = list(canonical_grant_permissions(permissions))
        registry, grant = create_authority_grant(
            authority_name=authority,
            grantee_name=grantee,
            resource_name=resource,
            permissions=permissions,
            recursive=recursive,
        )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho("Created authority grant.", fg=typer.colors.GREEN)
    _print_grant(registry, grant, prefix="  ")
    typer.echo(
        "The source remains ordinary data owned by the authority Profile; "
        "the grantee receives only this view."
    )


def grant_update_cmd(
    selector: Annotated[
        str,
        typer.Argument(help="Full or unambiguous leading grant uid"),
    ],
    permissions: Annotated[
        list[str],
        typer.Option("--allow", help="Replacement permission; repeat as needed"),
    ],
    refresh_scope: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            "--refresh-scope",
            help="Replace the grant scope with all current descendants",
        ),
    ] = False,
    root_only: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            "--root-only",
            help="Replace the grant scope with only its root Context",
        ),
    ] = False,
) -> None:
    """Replace permissions and optionally refresh one grant's frozen scope."""

    if refresh_scope and root_only:
        _fail(ProfileError("Choose either --refresh-scope or --root-only."))
    recursive = True if refresh_scope else False if root_only else None
    try:
        permissions = list(canonical_grant_permissions(permissions))
        registry, grant = update_authority_grant(
            selector,
            permissions=permissions,
            recursive=recursive,
        )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho("Updated authority grant.", fg=typer.colors.GREEN)
    _print_grant(registry, grant, prefix="  ")


def grant_delete_cmd(
    selector: Annotated[
        str,
        typer.Argument(help="Full or unambiguous leading grant uid"),
    ],
) -> None:
    """Revoke a view immediately without deleting either Profile's data."""

    try:
        registry, grant = delete_authority_grant(selector)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho("Revoked authority grant.", fg=typer.colors.GREEN)
    profiles = {profile.uid: profile.name for profile in registry.profiles}
    typer.echo(
        f"  {grant.uid[:8]} · "
        f"{display_escape_text(profiles[grant.authority_profile_uid])}:"
        f"{display_escape_text(grant.resource_name)} -> "
        f"{display_escape_text(profiles[grant.grantee_profile_uid])}"
    )


grant_app.command("list")(grant_list_cmd)


grant_app.command("ls", hidden=True)(grant_list_cmd)


grant_app.command("create")(grant_create_cmd)


grant_app.command("update")(grant_update_cmd)


grant_app.command("delete")(grant_delete_cmd)
