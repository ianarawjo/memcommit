"""Resolve one public Context through the active Profile's Grant metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.profile.config import (
    AuthorityGrant,
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
    authority: ProfileEntry
    grantee: ProfileEntry
    requested_name: str
    authority_context_name: str
    authority_root: Path


def grants_for_attachment(
    *,
    attachment_name: str,
    registry: ProfileRegistry | None = None,
) -> tuple[AuthorityGrant, ...]:
    """Return validated grant metadata attached to one active-Profile Context."""

    registry = registry or load_profile_registry()
    grantee = registry.active
    attachment = _context_record_at(profile_store_dir(grantee), attachment_name)
    if attachment is None:
        return ()
    return tuple(
        sorted(
            (
                grant
                for grant in registry.grants
                if grant.grantee_profile_uid == grantee.uid
                and grant.attachment_context_uid == attachment.uid
                and grant.attachment_context_name == attachment.name
            ),
            key=lambda grant: grant.public_name,
        )
    )


def resolve_granted_context_view(
    requested_name: str,
    *,
    attachment_name: str,
    required_permission: str,
    registry: ProfileRegistry | None = None,
) -> GrantedContextView:
    """Resolve the most-specific grant and fail closed on narrower overrides."""

    registry = registry or load_profile_registry()
    permission = validate_grant_permission(required_permission)
    grantee = registry.active
    attached = grants_for_attachment(
        attachment_name=attachment_name,
        registry=registry,
    )
    candidates = [
        grant
        for grant in attached
        if requested_name == grant.public_name
        or requested_name.startswith(grant.public_name + "/")
    ]
    if not candidates:
        raise ProfileError(f"Granted view {requested_name!r} does not exist.")
    grant = max(candidates, key=lambda item: len(item.public_name.split("/")))
    suffix = requested_name[len(grant.public_name) :]
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
        authority=authority,
        grantee=grantee,
        requested_name=requested_name,
        authority_context_name=authority_name,
        authority_root=authority_root,
    )


__all__ = [
    "GrantedContextView",
    "grants_for_attachment",
    "resolve_granted_context_view",
]
