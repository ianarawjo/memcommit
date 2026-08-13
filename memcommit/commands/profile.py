"""CLI for selecting complete local MemoryStore profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Annotated, Callable, Optional

import typer

from memcommit.command_attempts import current_command_attempt_uid
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.profile_group import ProfileAliasGroup
from memcommit.commands.profile_picker import (
    ProfilePickerAction,
    ProfilePickerEntry,
    ProfilePickerRefresh,
    choose_profile,
)
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import (
    ProfileError,
    STUDY_BASELINE_PROFILE_NAME,
    archive_legacy_study,
    create_authority_grant,
    default_study_bundle_root,
    delete_authority_grant,
    import_profile,
    import_study_profiles,
    list_authority_grants,
    list_profiles,
    remove_profile,
    remove_study,
    refresh_study_profile,
    rename_profile,
    study_run_profile_pairs,
    study_profile_groups,
    update_authority_grant,
    use_profile,
)
from memcommit.study_action_log import (
    StudyActionError,
    record_study_action,
    record_study_action_for_profile,
)


app = typer.Typer(
    cls=ProfileAliasGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    subcommand_metavar="COMMAND|PROFILE",
    help=(
        "Register and select complete local MemoryStore profiles. "
        "Use 'mem profile NAME' to select one."
    ),
)

grant_app = typer.Typer(
    no_args_is_help=True,
    help="Grant, inspect, revise, or revoke cross-Profile Context views.",
)
app.add_typer(grant_app, name="grant")


def _fail(error: Exception) -> None:
    typer.secho(
        f"Error: {display_escape_text(str(error))}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(1)


def _profile_rows() -> tuple[object, tuple[object, ...]]:
    try:
        return list_profiles()
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _inventory_label(inspection: object) -> str:
    """Render physical ownership separately from READ-granted knowledge."""

    return (
        f"Contexts {len(inspection.context_names)} owned + "
        f"{inspection.granted_context_count} granted · "
        f"Memories {inspection.ordinary_memory_count} owned + "
        f"{inspection.granted_memory_count} granted"
    )


def _grant_permissions_label(permissions: tuple[str, ...]) -> str:
    return ",".join(permission.lower() for permission in permissions)


@dataclass(frozen=True)
class _ProfileStudyMembership:
    uid: str
    name: str
    created_at: str
    role: str
    task: int | None
    first: bool
    last: bool
    profile_count: int
    removed_count: int


def _study_memberships(registry) -> dict[str, _ProfileStudyMembership]:
    try:
        groups = study_profile_groups(registry.profiles)
        pairs = study_run_profile_pairs(registry.profiles)
    except (ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    study_names = [group.name.casefold() for group in groups] + [
        pair.name.casefold() for pair in pairs
    ]
    if len(study_names) != len(set(study_names)):
        _fail(ProfileError("Study display names must be unique."))
    profile_positions = {
        profile.uid: index for index, profile in enumerate(registry.profiles)
    }
    memberships: dict[str, _ProfileStudyMembership] = {}
    for group in groups:
        members = (*group.profiles, *group.support_profiles)
        visible_members = tuple(
            profile for profile in members if not registry.is_removed(profile)
        )
        for index, profile in enumerate(members):
            is_task = index < len(group.profiles)
            task = index + 1 if is_task else index - len(group.profiles) + 1
            memberships[profile.uid] = _ProfileStudyMembership(
                uid=group.uid,
                name=group.name,
                created_at=group.created_at,
                role="TASK" if is_task else "AUTHORITY",
                task=task,
                first=bool(visible_members and profile.uid == visible_members[0].uid),
                last=bool(visible_members and profile.uid == visible_members[-1].uid),
                profile_count=len(members),
                removed_count=len(members) - len(visible_members),
            )
    for pair in pairs:
        if (
            profile_positions[pair.authority.uid]
            != profile_positions[pair.participant.uid] + 1
        ):
            _fail(ProfileError("Study run Profile pair must remain contiguous."))
        pair_members = (
            (pair.participant, "PARTICIPANT"),
            (pair.authority, "GRANTED_MEMORY"),
        )
        visible_members = tuple(
            profile
            for profile, _role in pair_members
            if not registry.is_removed(profile)
        )
        for profile, role in pair_members:
            if profile.uid in memberships:
                _fail(ProfileError("Profile has conflicting Study provenance."))
            memberships[profile.uid] = _ProfileStudyMembership(
                uid=pair.uid,
                name=pair.name,
                created_at=pair.created_at,
                role=role,
                task=None,
                first=bool(visible_members and profile.uid == visible_members[0].uid),
                last=bool(visible_members and profile.uid == visible_members[-1].uid),
                profile_count=len(pair_members),
                removed_count=len(pair_members) - len(visible_members),
            )
    return memberships


def _print_grant(registry, grant, *, prefix: str = "") -> None:
    profiles = {profile.uid: profile.name for profile in registry.profiles}
    authority = display_escape_text(profiles[grant.authority_profile_uid])
    grantee = display_escape_text(profiles[grant.grantee_profile_uid])
    public = display_escape_text(grant.public_name)
    resource = display_escape_text(grant.resource_name)
    attachment = display_escape_text(grant.attachment_context_name)
    typer.echo(
        f"{prefix}{grant.uid[:8]} · {authority}:{resource} -> "
        f"{grantee}:{attachment}/{public} · "
        f"{_grant_permissions_label(grant.permissions)} · "
        f"{len(grant.contexts)} Context(s) · revision {grant.revision}"
    )


def _pick_profile(
    *,
    initial_status: str = "",
    initial_row_index: int | None = None,
    apply_removal: Callable[[ProfilePickerAction], str] | None = None,
) -> ProfilePickerAction | ProfilePickerRefresh | None:
    registry, inspections = _profile_rows()
    memberships = _study_memberships(registry)
    entries = tuple(
        ProfilePickerEntry(
            name=profile.name,
            context_count=len(inspection.context_names),
            memory_count=inspection.ordinary_memory_count,
            current_context=inspection.current_context,
            granted_context_count=inspection.granted_context_count,
            granted_memory_count=inspection.granted_memory_count,
            query_source_count=inspection.query_source_count,
            query_source_names=inspection.query_source_names,
            uid=profile.uid,
            study_uid=(
                memberships[profile.uid].uid
                if profile.uid in memberships
                else None
            ),
            study_name=(
                memberships[profile.uid].name
                if profile.uid in memberships
                else None
            ),
            study_created_at=(
                memberships[profile.uid].created_at
                if profile.uid in memberships
                else None
            ),
            study_task=(
                memberships[profile.uid].task
                if profile.uid in memberships
                else None
            ),
            study_role=(
                memberships[profile.uid].role
                if profile.uid in memberships
                else None
            ),
            study_profile_count=(
                memberships[profile.uid].profile_count
                if profile.uid in memberships
                else 0
            ),
            study_removed_count=(
                memberships[profile.uid].removed_count
                if profile.uid in memberships
                else 0
            ),
            removal_block=(
                "The fixed authoring Profile cannot be removed"
                if profile.kind == "AUTHORING"
                else (
                    "The fixed study-baseline Profile cannot be removed"
                    if profile.name.casefold()
                    == STUDY_BASELINE_PROFILE_NAME.casefold()
                    else None
                )
            ),
        )
        for profile, inspection in zip(
            registry.visible_profiles,
            inspections,
            strict=True,
        )
    )
    try:
        picker_kwargs = (
            {"initial_status": initial_status} if initial_status else {}
        )
        if apply_removal is not None:
            picker_kwargs["apply_removal"] = apply_removal
        if initial_row_index is not None:
            picker_kwargs["initial_row_index"] = initial_row_index
        selected = choose_profile(
            entries,
            current=registry.active.name,
            registry_generation=registry.generation,
            **picker_kwargs,
        )
        # Compatibility for narrow tests and callers that supplied the former
        # name-only picker result while the typed action contract rolled out.
        if isinstance(selected, str):
            target = registry.by_name(selected)
            return ProfilePickerAction(
                kind="USE",
                name=selected,
                uid=target.uid if target is not None else None,
                registry_generation=registry.generation,
            )
        return selected
    except ValueError as error:
        _fail(ProfileError(str(error)))


def _print_profile_removal(result) -> None:
    typer.secho(
        "Permanently deleted Profile '"
        + display_escape_text(result.profile.name)
        + "'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "Deleted store and all checkpoints: "
        + display_escape_text(str(result.deleted_store))
    )
    typer.echo(f"Connected Grants removed: {result.removed_grant_count}")
    typer.echo(
        "The Profile UID and Study provenance remain only as a tombstone; "
        "content cannot be recovered."
    )
    if result.study_name is not None:
        typer.echo(
            "Study "
            + display_escape_text(result.study_name)
            + f": {result.study_profile_count - result.study_removed_count} active · "
            + f"{result.study_removed_count} removed"
        )
    typer.echo(
        "Active Profile unchanged: "
        + display_escape_text(result.active_profile_name)
    )


def _print_study_removal(result) -> None:
    typer.secho(
        "Permanently deleted Study '"
        + display_escape_text(result.name)
        + "' Profile stores.",
        fg=typer.colors.GREEN,
    )
    typer.echo(
        "Profile stores and checkpoint histories deleted: "
        + str(result.newly_removed_count)
    )
    typer.echo(f"Connected Grants removed: {result.removed_grant_count}")
    typer.echo(
        "Profile UIDs and Study provenance remain only as tombstones; content "
        "cannot be recovered."
    )
    typer.echo(
        "Active Profile unchanged: "
        + display_escape_text(result.active_profile_name)
    )


def _profile_removal_status(result) -> str:
    grant_label = "Grant" if result.removed_grant_count == 1 else "Grants"
    return (
        "Deleted Profile '"
        + display_escape_text(result.profile.name)
        + "' permanently · store/checkpoints deleted · "
        + f"{result.removed_grant_count} {grant_label} removed"
    )


def _study_removal_status(result) -> str:
    grant_label = "Grant" if result.removed_grant_count == 1 else "Grants"
    return (
        "Deleted Study '"
        + display_escape_text(result.name)
        + "' permanently · "
        + f"{result.newly_removed_count} stores/checkpoint histories deleted · "
        + f"{result.removed_grant_count} {grant_label} removed"
    )


def _apply_profile_picker_action(
    action: ProfilePickerAction,
    *,
    print_receipt: bool = True,
    propagate_errors: bool = False,
) -> str | None:
    if action.kind == "USE":
        _use_profile(action.name)
        return None
    try:
        if action.kind == "REMOVE_PROFILE":
            result = remove_profile(
                action.name,
                expected_uid=action.uid,
                expected_generation=action.registry_generation,
            )
        else:
            result = remove_study(
                action.name,
                expected_uid=action.uid,
                expected_generation=action.registry_generation,
            )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        if propagate_errors:
            raise
        _fail(error)
    if action.kind == "REMOVE_PROFILE":
        if print_receipt:
            _print_profile_removal(result)
        return _profile_removal_status(result)
    if print_receipt:
        _print_study_removal(result)
    return _study_removal_status(result)


def _run_profile_selector() -> None:
    """Keep the selector open after deletion and reload its frozen catalog."""

    status = ""
    preferred_row_index: int | None = None
    completed_removal = False
    while True:
        action = _pick_profile(
            initial_status=status,
            initial_row_index=preferred_row_index,
            apply_removal=lambda reviewed: (
                _apply_profile_picker_action(
                    reviewed,
                    print_receipt=False,
                    propagate_errors=True,
                )
                or "Profile deletion completed"
            ),
        )
        if action is None:
            if not completed_removal:
                typer.echo("Profile selection cancelled.")
            return
        if isinstance(action, ProfilePickerRefresh):
            if action.error is not None:
                _fail(action.error)
            status = action.status
            preferred_row_index = action.preferred_row_index
            completed_removal = True
            if action.close_requested:
                return
            continue
        if action.kind == "USE":
            _apply_profile_picker_action(action)
            return
        # A completed destructive action must never reuse the catalog or
        # registry generation that was frozen for its review. Re-entering the
        # picker reloads both while keeping the person in the selector flow.
        status = _apply_profile_picker_action(
            action,
            print_receipt=False,
            propagate_errors=False,
        ) or "Profile deletion completed"
        completed_removal = True


def _use_profile(name: str) -> None:
    try:
        previous_profile = load_profile_registry().active
        registry, inspection, changed = use_profile(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    if not changed:
        typer.echo(
            "Already using profile '" + display_escape_text(registry.active.name) + "'."
        )
        return
    attempt_uid = current_command_attempt_uid()
    if attempt_uid is not None:
        try:
            record_study_action(
                "PROFILE_LEFT",
                other_profile_uid=registry.active.uid,
                other_profile_name=registry.active.name,
            )
            record_study_action_for_profile(
                registry.active,
                attempt_uid=attempt_uid,
                event_kind="PROFILE_ENTERED",
                other_profile_uid=previous_profile.uid,
                other_profile_name=previous_profile.name,
            )
        except (OSError, ProfileConfigError, StudyActionError, ValueError) as error:
            typer.secho(
                "Error: Profile selection changed, but its Study action ledger "
                "could not be written: " + display_escape_text(str(error)),
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
    typer.secho(
        f"Selected profile '{display_escape_text(registry.active.name)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo("The next mem command will see " + _inventory_label(inspection) + ".")
    current_label = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.echo(f"Current Context: {current_label}")
    if inspection.query_source_count:
        typer.echo(
            "Query-only: "
            f"{', '.join(display_escape_text(name) for name in inspection.query_source_names)} "
            "(visible by name; hidden from 'mem switch')."
        )


@app.callback(invoke_without_command=True)
def profile_cmd(ctx: typer.Context) -> None:
    """Enter the Profile selector, or print its stable non-TTY list."""

    if ctx.invoked_subcommand is not None:
        return
    if not _interactive_terminal():
        list_cmd()
        return
    _run_profile_selector()


@app.command("list")
def list_cmd() -> None:
    """List locally registered whole-store profiles."""

    registry, inspections = _profile_rows()
    memberships = _study_memberships(registry)
    for profile, inspection in zip(
        registry.visible_profiles,
        inspections,
        strict=True,
    ):
        marker = "*" if profile.uid == registry.active_uid else " "
        action = "CURRENT" if profile.uid == registry.active_uid else "USE"
        profile_label = display_escape_text(profile.name)
        current = (
            display_escape_text(inspection.current_context)
            if inspection.current_context
            else "(none)"
        )
        query_note = (
            " · query="
            + ",".join(
                display_escape_text(name) for name in inspection.query_source_names
            )
            if inspection.query_source_names
            else (
                f" · {inspection.query_source_count} query-only"
                if inspection.query_source_count
                else ""
            )
        )
        granted_views = [
            grant.public_name
            for grant in registry.grants
            if grant.grantee_profile_uid == profile.uid
        ]
        view_note = (
            " · views=" + ",".join(display_escape_text(name) for name in granted_views)
            if granted_views
            else ""
        )
        membership = memberships.get(profile.uid)
        if membership is not None:
            if membership.first:
                removal_note = (
                    f" · {membership.removed_count} removed"
                    if membership.removed_count
                    else ""
                )
                typer.echo(
                    "  "
                    + display_escape_text(membership.name)
                    + "  STUDY   created="
                    + display_escape_text(membership.created_at)
                    + removal_note
                )
            branch = "└─" if membership.last else "├─"
            if membership.role == "PARTICIPANT":
                role_label = "Participant"
            elif membership.role == "GRANTED_MEMORY":
                role_label = "Granted memory"
            else:
                role_name = "Task" if membership.role == "TASK" else "Authority"
                role_label = f"{role_name} {membership.task}"
            typer.echo(
                f"    {branch} {marker} {role_label}  "
                f"{action:<7} profile={profile_label} · "
                f"{profile.kind.lower()} · {_inventory_label(inspection)}"
                f"{query_note}{view_note} · current={current}"
            )
            continue
        typer.echo(
            f"{marker} {profile_label:<12} "
            f"{action:<7} "
            f"{profile.kind.lower():<9} "
            f"{_inventory_label(inspection)}"
            f"{query_note}{view_note} · current={current}"
        )
    typer.echo("Granted views are permission projections, not copied Profiles.")
    typer.echo("Authority Profiles are ordinary switchable owners of source data.")
    if registry.removed_profile_uids:
        typer.echo(
            f"Deleted Profile tombstones hidden from this list: "
            f"{len(registry.removed_profile_uids)}"
        )


app.command("ls", hidden=True)(list_cmd)


@grant_app.command("list")
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


grant_app.command("ls", hidden=True)(grant_list_cmd)


@grant_app.command("create")
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
    attachment: Annotated[
        str,
        typer.Option("--into", help="Existing grantee Context that owns the view"),
    ],
    permissions: Annotated[
        list[str],
        typer.Option(
            "--allow",
            help=(
                "Permission to grant; repeat CREATE, READ, UPDATE/EDIT, "
                "DELETE, QUERY, SESSION_LOG, DERIVE, COMBINE, EXPORT, "
                "ACCEPT_DERIVED, SAVE_BOUND_ANALYSIS, SAVE_ANALYSIS, or SHARE"
            ),
        ),
    ],
    public_name: Annotated[
        Optional[str],
        typer.Option("--as", help="Public view path; defaults to the resource path"),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            help="Freeze the resource's current descendants into this grant",
        ),
    ] = False,
) -> None:
    """Grant a frozen Context view or SHARE delivery endpoint."""

    try:
        registry, grant = create_authority_grant(
            authority_name=authority,
            grantee_name=grantee,
            resource_name=resource,
            attachment_name=attachment,
            permissions=permissions,
            public_name=public_name,
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


@grant_app.command("update")
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
            "--refresh-scope",
            help="Replace the frozen scope with all current descendants",
        ),
    ] = False,
    root_only: Annotated[
        bool,
        typer.Option(
            "--root-only",
            help="Replace the frozen scope with only its root Context",
        ),
    ] = False,
) -> None:
    """Replace permissions and optionally refresh one grant's frozen scope."""

    if refresh_scope and root_only:
        _fail(ProfileError("Choose either --refresh-scope or --root-only."))
    recursive = True if refresh_scope else False if root_only else None
    try:
        registry, grant = update_authority_grant(
            selector,
            permissions=permissions,
            recursive=recursive,
        )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho("Updated authority grant.", fg=typer.colors.GREEN)
    _print_grant(registry, grant, prefix="  ")


@grant_app.command("delete")
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
    _print_grant(registry, grant, prefix="  ")


@app.command("current")
def current_cmd() -> None:
    """Show the selected profile and its current Context."""

    registry, inspections = _profile_rows()
    visible_profiles = registry.visible_profiles
    index = next(
        index
        for index, profile in enumerate(visible_profiles)
        if profile.uid == registry.active_uid
    )
    inspection = inspections[index]
    typer.echo(f"Profile: {display_escape_text(registry.active.name)}")
    typer.echo(f"Store: {display_escape_text(str(inspection.root))}")
    typer.echo(_inventory_label(inspection))
    current_label = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.echo(f"Current Context: {current_label}")
    if inspection.query_source_names:
        typer.echo(
            "Query-only: "
            + ", ".join(
                display_escape_text(name) for name in inspection.query_source_names
            )
        )


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
        _run_profile_selector()
        return
    _use_profile(name)


@app.command("remove")
def remove_cmd(
    name: Annotated[
        str,
        typer.Argument(
            help="Managed Profile whose complete store will be deleted"
        ),
    ],
    force: Annotated[
        bool,
        typer.Option("-f", "--force", help="Skip the confirmation prompt"),
    ] = False,
) -> None:
    """Permanently delete one Profile store and all of its checkpoints."""

    if not force:
        typer.echo(
            "WARNING: This permanently deletes only Profile '"
            + display_escape_text(name)
            + "', its complete store, every Memory, session, and checkpoint, "
            "plus connected Grants. This cannot be undone or recovered by mem."
        )
        if not typer.confirm("Continue?", default=False):
            typer.echo("Profile removal cancelled.")
            return
    try:
        with CommandProgress(
            "profile remove",
            "deleting store and checkpoints",
            total=1,
        ):
            result = remove_profile(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    _print_profile_removal(result)


@app.command("remove-study")
def remove_study_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Legacy or current Study name"),
    ],
    force: Annotated[
        bool,
        typer.Option("-f", "--force", help="Skip the confirmation prompt"),
    ] = False,
) -> None:
    """Permanently delete every Profile store and checkpoint in one Study."""

    if not force:
        typer.echo(
            "WARNING: This permanently deletes every Profile in Study '"
            + display_escape_text(name)
            + "', including every store, Memory, session, checkpoint, and "
            "connected Grant. This cannot be undone or recovered by mem."
        )
        if not typer.confirm("Continue?", default=False):
            typer.echo("Study removal cancelled.")
            return
    try:
        with CommandProgress(
            "profile remove-study",
            "deleting stores and checkpoints",
            total=1,
        ):
            result = remove_study(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    _print_study_removal(result)


@app.command("rename")
def rename_cmd(
    profile_or_new: Annotated[
        str,
        typer.Argument(
            metavar="NAME",
            help=(
                "New name for the current Profile, or existing Profile when "
                "NEW is also supplied"
            )
        ),
    ],
    new_name: Annotated[
        Optional[str],
        typer.Argument(
            metavar="NEW",
            help="New name for the explicitly named Profile",
        ),
    ] = None,
) -> None:
    """Rename one managed Profile without moving or rewriting its store."""

    old_name = profile_or_new if new_name is not None else None
    destination = new_name if new_name is not None else profile_or_new
    try:
        result = rename_profile(destination, old_name=old_name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    if not result.changed:
        typer.echo(
            "Profile '"
            + display_escape_text(result.profile.name)
            + "' already has that name."
        )
        return

    prefix = "Renamed active Profile" if result.was_active else "Renamed Profile"
    typer.secho(
        f"{prefix} '{display_escape_text(result.previous_name)}' to "
        f"'{display_escape_text(result.profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo("Profile UID unchanged: " + display_escape_text(result.profile.uid))
    typer.echo(
        "Store unchanged: "
        + display_escape_text(str(profile_store_dir(result.profile)))
    )
    if result.was_active:
        typer.echo(
            "The same Profile remains current under its new name: "
            + display_escape_text(result.active_profile_name)
        )
    else:
        typer.echo(
            "Active Profile unchanged: "
            + display_escape_text(result.active_profile_name)
        )
    typer.echo(
        "Store data, Contexts, Memories, grants, and provenance were not modified."
    )
    typer.echo(
        "Use it with: mem profile use "
        + display_escape_text(result.profile.name)
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
    typer.secho(
        f"Imported profile '{display_escape_text(profile.name)}'.",
        fg=typer.colors.GREEN,
    )
    current_label = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.echo(f"{_inventory_label(inspection)} · current={current_label}")
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
    """Bootstrap one editable Profile containing the complete Study baseline."""

    bundle_root = source or default_study_bundle_root()
    try:
        result = import_study_profiles(bundle_root)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho("Imported editable Study baseline.", fg=typer.colors.GREEN)
    for profile, inspection in zip(
        result.profiles,
        result.inspections,
        strict=True,
    ):
        current_label = (
            display_escape_text(inspection.current_context)
            if inspection.current_context
            else "(none)"
        )
        typer.echo(
            f"  {display_escape_text(profile.name)}: "
            f"{_inventory_label(inspection)} · current={current_label} · "
            f"kind={display_escape_text(profile.kind.lower())}"
        )
    typer.echo("The authoring store and generated package sources were not modified.")
    typer.echo(
        "Authoring checkpoints, sessions, caches, locks, and run logs "
        "were not imported."
    )
    typer.echo(
        "Edit it with: mem profile use "
        + display_escape_text(STUDY_BASELINE_PROFILE_NAME)
    )
    typer.echo(
        "Clone it as an isolated participant/authority run with: "
        "mem init-study NAME"
    )


@app.command("refresh-study")
def refresh_study_cmd(
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
    replace_edited_baseline: Annotated[
        bool,
        typer.Option(
            "--replace-edited-baseline",
            help="Replace local edits made since the previous Study import",
        ),
    ] = False,
) -> None:
    """Refresh the editable Study baseline from validated fixture packages."""

    bundle_root = source or default_study_bundle_root()
    try:
        result = refresh_study_profile(
            bundle_root,
            replace_edited_baseline=replace_edited_baseline,
        )
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    profile = result.profiles[0]
    inspection = result.inspections[0]
    current_label = (
        display_escape_text(inspection.current_context)
        if inspection.current_context
        else "(none)"
    )
    typer.secho("Refreshed editable Study baseline.", fg=typer.colors.GREEN)
    typer.echo(
        f"  {display_escape_text(profile.name)}: "
        f"{_inventory_label(inspection)} · current={current_label} · "
        f"kind={display_escape_text(profile.kind.lower())}"
    )
    typer.echo("The Profile identity and active Profile selection were preserved.")
    typer.echo("New Study runs will use this refreshed baseline.")


@app.command("archive-study")
def archive_study_cmd(
    name: Annotated[
        str,
        typer.Argument(help="Complete legacy split Study name"),
    ],
) -> None:
    """Detach a legacy split Study while preserving all of its store data."""

    try:
        result = archive_legacy_study(name)
    except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
        _fail(error)
    typer.secho(
        "Archived legacy Study '" + display_escape_text(result.name) + "'.",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Profiles removed from selector: {len(result.profiles)}")
    typer.echo(f"Internal grants recorded in archive: {len(result.grants)}")
    typer.echo(
        "Archive manifest: " + display_escape_text(str(result.manifest_path))
    )
    typer.echo(
        "Active Profile unchanged: "
        + display_escape_text(result.active_profile_name)
    )
    typer.echo("No Memory data was moved or deleted.")
    typer.echo("To create a merged replacement from an available Study baseline:")
    typer.echo("  mem init-study " + display_escape_text(result.name))
