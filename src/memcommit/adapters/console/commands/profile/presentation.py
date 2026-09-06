"""Profile inventory, operation receipts, and selector status presentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.operations.profile.config import (
    ProfileRegistry,
    profile_store_dir,
)

if TYPE_CHECKING:
    from memcommit.adapters.console.commands.profile.inventory import (
        _ProfileStudyMembership,
    )


_PROFILE_INVENTORY_ACTION_ROLES = {
    "CURRENT": SemanticColorRole.PROFILE_CURRENT,
    "USE": SemanticColorRole.PROFILE_USE,
    "STUDY": SemanticColorRole.PROFILE_STUDY,
}


def _inventory_label(inspection: object) -> str:
    """Render physical ownership separately from READ-granted knowledge."""

    return (
        f"Contexts {len(inspection.context_names)} owned + "
        f"{inspection.granted_context_count} granted · "
        f"Memories {inspection.ordinary_memory_count} owned + "
        f"{inspection.granted_memory_count} granted"
    )


def _styled_profile_inventory_action(action: str) -> str:
    """Color one typed inventory token without changing its text or width."""

    return typer.style(
        action,
        fg=semantic_color_rgb(_PROFILE_INVENTORY_ACTION_ROLES[action]),
        bold=True,
    )


def _study_role_label(membership: _ProfileStudyMembership) -> str:
    if membership.role == "PARTICIPANT":
        return "Participant"
    if membership.role == "GRANTED_MEMORY":
        return "Granted memory"
    raise ValueError(f"Unknown Study role: {membership.role!r}")


def _profile_inventory_identity_width(
    registry: ProfileRegistry,
    memberships: dict[str, _ProfileStudyMembership],
) -> int:
    """Freeze one action column across ordinary, Study, and child rows."""

    identities: list[str] = []
    displayed_studies: set[str] = set()
    for profile in registry.visible_profiles:
        membership = memberships.get(profile.uid)
        if membership is None:
            identities.append("  " + display_escape_text(profile.name))
            continue
        if membership.uid not in displayed_studies:
            identities.append("  " + display_escape_text(membership.name))
            displayed_studies.add(membership.uid)
        branch = "└─" if membership.last else "├─"
        identities.append(f"    {branch}   {_study_role_label(membership)}")
    return max(len(identity) for identity in identities)


def _echo_profile_inventory_row(
    identity: str,
    action: str,
    detail: str,
    *,
    identity_width: int,
) -> None:
    """Render one stable row while styling only its trusted action token."""

    action_padding = " " * (7 - len(action))
    typer.echo(
        f"{identity:<{identity_width}}  "
        + _styled_profile_inventory_action(action)
        + action_padding
        + " "
        + detail
    )


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
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
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
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
    )


def _profile_removal_status(result) -> str:
    grant_label = "Grant" if result.removed_grant_count == 1 else "Grants"
    return (
        "Deleted Profile '"
        + display_escape_text(result.profile.name)
        + "' permanently · store/checkpoints deleted · "
        + f"{result.removed_grant_count} {grant_label} removed"
    )


def _profile_creation_status(result) -> str:
    return (
        "Created empty Profile '"
        + display_escape_text(result.profile.name)
        + "' · 0 Contexts · active Profile unchanged: "
        + display_escape_text(result.active_profile_name)
    )


def _print_profile_creation(result) -> None:
    typer.secho(
        "Created empty Profile '" + display_escape_text(result.profile.name) + "'.",
        fg=semantic_color_rgb(SemanticColorRole.CREATE),
    )
    typer.echo("Profile UID: " + display_escape_text(result.profile.uid))
    typer.echo("Store: " + display_escape_text(str(result.inspection.root)))
    typer.echo("Contexts 0 owned + 0 granted · Memories 0 owned + 0 granted")
    typer.echo(
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
    )
    typer.echo(
        "Use it with: mem profile use " + display_escape_text(result.profile.name)
    )
    typer.echo("Then create its first Context with: mem init CONTEXT")


def _profile_rename_status(result) -> str:
    if not result.changed:
        return "Profile '" + display_escape_text(result.profile.name) + "' unchanged"
    return (
        "Renamed Profile '"
        + display_escape_text(result.previous_name)
        + "' to '"
        + display_escape_text(result.profile.name)
        + "' · UID and store unchanged"
    )


def _study_rename_status(result) -> str:
    if not result.changed:
        return "Study '" + display_escape_text(result.name) + "' unchanged"
    return (
        "Renamed Study '"
        + display_escape_text(result.previous_name)
        + "' to '"
        + display_escape_text(result.name)
        + "' · UID unchanged"
        + " · member Profile names unchanged"
    )


def _print_profile_rename(result) -> None:
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
        "Use it with: mem profile use " + display_escape_text(result.profile.name)
    )


def _print_study_rename(result) -> None:
    if not result.changed:
        typer.echo(
            "Study '" + display_escape_text(result.name) + "' already has that name."
        )
        return
    typer.secho(
        f"Renamed Study '{display_escape_text(result.previous_name)}' to "
        f"'{display_escape_text(result.name)}'.",
        fg=typer.colors.GREEN,
    )
    typer.echo("Study UID unchanged: " + display_escape_text(result.uid))
    typer.echo("Member Profile display names unchanged.")
    typer.echo("Profile UIDs, stores, Contexts, Memories, and Grants unchanged.")
    typer.echo(
        "Active Profile unchanged: " + display_escape_text(result.active_profile_name)
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


def _print_profile_inventory(registry, inspections, memberships) -> None:
    identity_width = _profile_inventory_identity_width(registry, memberships)
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
        placements_by_grant_uid = {
            placement.grant_uid: placement
            for placement in registry.grant_placements
            if placement.grantee_profile_uid == profile.uid
        }
        granted_views = [
            placements_by_grant_uid[grant.uid].access_name
            for grant in registry.grants
            if grant.grantee_profile_uid == profile.uid
            and grant.uid in placements_by_grant_uid
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
                _echo_profile_inventory_row(
                    "  " + display_escape_text(membership.name),
                    "STUDY",
                    "created="
                    + display_escape_text(membership.created_at)
                    + removal_note,
                    identity_width=identity_width,
                )
            branch = "└─" if membership.last else "├─"
            _echo_profile_inventory_row(
                f"    {branch} {marker} {_study_role_label(membership)}",
                action,
                f"profile={profile_label} · "
                f"{profile.kind.lower()} · {_inventory_label(inspection)}"
                f"{query_note}{view_note} · current={current}",
                identity_width=identity_width,
            )
            continue
        _echo_profile_inventory_row(
            f"{marker} {profile_label}",
            action,
            f"{profile.kind.lower():<9} "
            f"{_inventory_label(inspection)}"
            f"{query_note}{view_note} · current={current}",
            identity_width=identity_width,
        )
    typer.echo("Granted views are permission projections, not copied Profiles.")
    typer.echo("Authority Profiles are ordinary switchable owners of source data.")
    if registry.removed_profile_uids:
        typer.echo(
            f"Deleted Profile tombstones hidden from this list: "
            f"{len(registry.removed_profile_uids)}"
        )


def _print_current_profile(registry, inspections) -> None:
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
