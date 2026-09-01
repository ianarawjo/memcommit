"""Resolve one placed Context through the active Profile's Grant metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.profile.config import (
    AuthorityGrant,
    GrantPlacement,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    validate_grant_permission,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    _context_record_at,
)


@dataclass(frozen=True)
class GrantedContextView:
    """One validated Context view resolved for a grantee Profile."""

    grant: AuthorityGrant
    placement: GrantPlacement
    authority: ProfileEntry
    grantee: ProfileEntry
    access_name: str
    authority_context_name: str
    authority_root: Path


def active_grant_placements(
    *,
    registry: ProfileRegistry | None = None,
) -> tuple[tuple[GrantPlacement, AuthorityGrant], ...]:
    """Return the active Profile's placements joined to exact Grants."""

    registry = registry or load_profile_registry()
    grantee = registry.active
    grants_by_uid = {grant.uid: grant for grant in registry.grants}
    return tuple(
        sorted(
            (
                (placement, grants_by_uid[placement.grant_uid])
                for placement in registry.grant_placements
                if placement.grantee_profile_uid == grantee.uid
                and placement.grant_uid in grants_by_uid
                and grants_by_uid[placement.grant_uid].grantee_profile_uid
                == grantee.uid
            ),
            key=lambda item: item[0].access_name,
        )
    )


def resolve_granted_context_view(
    requested_name: str,
    *,
    required_permission: str,
    registry: ProfileRegistry | None = None,
    expected_grant_uid: str | None = None,
) -> GrantedContextView:
    """Resolve the most-specific grant and fail closed on narrower overrides."""

    registry = registry or load_profile_registry()
    permission = validate_grant_permission(required_permission)
    grantee = registry.active
    placed = active_grant_placements(registry=registry)
    candidates = [
        (placement, grant)
        for placement, grant in placed
        if requested_name == placement.access_name
        or requested_name.startswith(placement.access_name + "/")
    ]
    if not candidates:
        raise ProfileError(f"Granted view {requested_name!r} does not exist.")
    placement, grant = max(
        candidates,
        key=lambda item: len(item[0].access_name.split("/")),
    )
    if expected_grant_uid is not None and grant.uid != expected_grant_uid:
        raise ProfileError("The Grant placement behind this persisted access changed.")
    suffix = requested_name[len(placement.access_name) :]
    authority_name = grant.resource_name + suffix
    bindings = {binding.name: binding.uid for binding in grant.contexts}
    authority_uid = bindings.get(authority_name)
    if authority_uid is None:
        raise ProfileError(f"Context {requested_name!r} is not included in this Grant.")
    if permission not in grant.permissions:
        raise ProfileError(
            f"Grant {grant.uid[:8]} does not allow {permission.lower()} access "
            f"to {requested_name!r}."
        )
    authority = next(
        profile
        for profile in registry.profiles
        if profile.uid == grant.authority_profile_uid
    )
    authority_root = profile_store_dir(authority)
    # Runtime view resolution must not inspect sibling or narrower authority
    # Contexts merely to validate one frozen binding. This is especially
    # important when a readable parent has a query-only nested override.
    context = _context_record_at(authority_root, authority_name)
    if context is None or context.uid != authority_uid:
        raise ProfileError("Granted authority Context identity changed.")
    return GrantedContextView(
        grant=grant,
        placement=placement,
        authority=authority,
        grantee=grantee,
        access_name=requested_name,
        authority_context_name=authority_name,
        authority_root=authority_root,
    )


__all__ = [
    "GrantedContextView",
    "active_grant_placements",
    "resolve_granted_context_view",
]
