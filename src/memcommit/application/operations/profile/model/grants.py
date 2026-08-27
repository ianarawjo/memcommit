"""Authority Grant lifecycle and cross-Profile Context resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid
from memcommit.core.context import Context
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.operations.profile.config import (
    AuthorityGrant,
    GRANT_RESOURCE_CONTEXT_TREE,
    GrantContextBinding,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    canonical_grant_permissions,
    validate_grant_permission,
    validate_grant_resource_name,
)

from ._storage import (
    ProfileError as ProfileError,
    _context_record_at as _context_record_at,
    _context_records as _context_records,
    _registry_lock as _registry_lock,
    _write_registry as _write_registry,
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


@dataclass(frozen=True)
class ShareEndpoint:
    """One grant-backed cross-Profile delivery target."""

    grant: AuthorityGrant
    authority: ProfileEntry
    sender: ProfileEntry
    public_name: str
    receiver_context_name: str
    receiver_root: Path


def _grant_selector(
    registry: ProfileRegistry,
    selector: str,
) -> AuthorityGrant:
    matches = [grant for grant in registry.grants if grant.uid.startswith(selector)]
    if not matches:
        raise ProfileError(f"Grant {selector!r} does not exist.")
    if len(matches) > 1:
        raise ProfileError(
            f"Grant selector {selector!r} is ambiguous: "
            + ", ".join(grant.uid[:8] for grant in matches)
        )
    return matches[0]


def _grant_scope(
    contexts: dict[str, Context],
    resource_name: str,
    *,
    recursive: bool,
) -> tuple[GrantContextBinding, ...]:
    root = contexts.get(resource_name)
    if root is None:
        raise ProfileError(f"Authority Context {resource_name!r} does not exist.")
    scope = ContextScope.create(
        (resource_name,),
        include_descendants=recursive,
    )
    names = expand_lexical_context_names(scope, sorted(contexts))
    return tuple(
        GrantContextBinding(uid=contexts[name].uid, name=name) for name in names
    )


def _assert_grantee_attachment(
    grantee: ProfileEntry,
    attachment_name: str,
) -> Context:
    contexts, _ = _context_records(profile_store_dir(grantee))
    attachment = contexts.get(attachment_name)
    if attachment is None:
        raise ProfileError(
            f"Grantee Context {attachment_name!r} does not exist in "
            f"Profile {grantee.name!r}."
        )
    return attachment


def _assert_public_view_available(
    registry: ProfileRegistry,
    *,
    grantee: ProfileEntry,
    attachment: Context,
    public_name: str,
    replacing_uid: str | None = None,
) -> None:
    grantee_contexts, _ = _context_records(profile_store_dir(grantee))
    public_folded = public_name.casefold()
    for name in grantee_contexts:
        name_folded = name.casefold()
        if name_folded == public_folded or name_folded.startswith(public_folded + "/"):
            raise ProfileError(
                f"Granted view {public_name!r} overlaps local Context {name!r}."
            )
        # A lexical local ancestor is safe and lets a borrowed view appear
        # below its task namespace. The granted leaf and its descendants must
        # still remain absent locally or local resolution would bypass grants.
    for grant in registry.grants:
        if grant.uid == replacing_uid:
            continue
        if (
            grant.grantee_profile_uid == grantee.uid
            and grant.attachment_context_uid == attachment.uid
            and grant.public_name.casefold() == public_folded
        ):
            raise ProfileError(
                f"Granted view {public_name!r} already exists on {attachment.name!r}."
            )


def create_authority_grant(
    *,
    authority_name: str,
    grantee_name: str,
    resource_name: str,
    attachment_name: str,
    permissions: object,
    public_name: str | None = None,
    recursive: bool = False,
    grant_uid: str | None = None,
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Create one exact cross-Profile Context view under the registry lock."""

    canonical_permissions = canonical_grant_permissions(permissions)
    # Existing legacy Grants remain readable, but a new Grant must not publish
    # or attach another shell-dependent Context locator.
    validate_portable_context_name(resource_name)
    validate_portable_context_name(attachment_name)
    with _registry_lock():
        registry = load_profile_registry()
        authority = registry.by_name(authority_name)
        grantee = registry.by_name(grantee_name)
        if authority is None:
            raise ProfileError(f"Profile {authority_name!r} does not exist.")
        if grantee is None:
            raise ProfileError(f"Profile {grantee_name!r} does not exist.")
        if registry.is_removed(authority) or registry.is_removed(grantee):
            raise ProfileError(
                "A removed Profile cannot be used to create a new Grant."
            )
        if authority.uid == grantee.uid:
            raise ProfileError("A Profile cannot grant a view to itself.")
        authority_contexts, _ = _context_records(profile_store_dir(authority))
        scope = _grant_scope(
            authority_contexts,
            resource_name,
            recursive=recursive,
        )
        for binding in scope:
            validate_portable_context_name(binding.name)
        attachment = _assert_grantee_attachment(grantee, attachment_name)
        public = public_name or resource_name
        public = validate_portable_context_name(public)
        _assert_public_view_available(
            registry,
            grantee=grantee,
            attachment=attachment,
            public_name=public,
        )
        uid = grant_uid or str(uuid.uuid4())
        try:
            uid = str(uuid.UUID(uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ProfileError("Grant uid must be a canonical UUID.") from error
        if grant_uid is not None and uid != grant_uid:
            raise ProfileError("Grant uid must be a canonical UUID.")
        if any(grant.uid == uid for grant in registry.grants):
            raise ProfileError(f"Grant {uid!r} already exists.")
        root = scope[0]
        grant = AuthorityGrant(
            uid=uid,
            revision=1,
            authority_profile_uid=authority.uid,
            grantee_profile_uid=grantee.uid,
            attachment_context_uid=attachment.uid,
            attachment_context_name=attachment.name,
            resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
            resource_uid=root.uid,
            resource_name=root.name,
            public_name=public,
            permissions=canonical_permissions,
            contexts=scope,
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=(*registry.grants, grant),
            removed_profile_uids=registry.removed_profile_uids,
        )
        _write_registry(updated)
        return updated, grant


def update_authority_grant(
    selector: str,
    *,
    permissions: object,
    recursive: bool | None = None,
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Replace one grant's permissions and optionally refresh its exact scope."""

    canonical_permissions = canonical_grant_permissions(permissions)
    with _registry_lock():
        registry = load_profile_registry()
        existing = _grant_selector(registry, selector)
        authority = next(
            profile
            for profile in registry.profiles
            if profile.uid == existing.authority_profile_uid
        )
        grantee = next(
            profile
            for profile in registry.profiles
            if profile.uid == existing.grantee_profile_uid
        )
        attachment = _assert_grantee_attachment(
            grantee,
            existing.attachment_context_name,
        )
        if attachment.uid != existing.attachment_context_uid:
            raise ProfileError("Grant attachment Context identity changed.")
        authority_contexts, _ = _context_records(profile_store_dir(authority))
        if recursive is None:
            scope = existing.contexts
            for binding in scope:
                current = authority_contexts.get(binding.name)
                if current is None or current.uid != binding.uid:
                    raise ProfileError("Grant authority Context scope changed.")
        else:
            scope = _grant_scope(
                authority_contexts,
                existing.resource_name,
                recursive=recursive,
            )
            for binding in scope:
                validate_portable_context_name(binding.name)
        replacement = AuthorityGrant(
            uid=existing.uid,
            revision=existing.revision + 1,
            authority_profile_uid=existing.authority_profile_uid,
            grantee_profile_uid=existing.grantee_profile_uid,
            attachment_context_uid=existing.attachment_context_uid,
            attachment_context_name=existing.attachment_context_name,
            resource_kind=existing.resource_kind,
            resource_uid=scope[0].uid,
            resource_name=scope[0].name,
            public_name=existing.public_name,
            permissions=canonical_permissions,
            contexts=scope,
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=tuple(
                replacement if grant.uid == existing.uid else grant
                for grant in registry.grants
            ),
            removed_profile_uids=registry.removed_profile_uids,
        )
        _write_registry(updated)
        return updated, replacement


def delete_authority_grant(
    selector: str,
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Revoke one exact grant without touching either Profile's data."""

    with _registry_lock():
        registry = load_profile_registry()
        removed = _grant_selector(registry, selector)
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=tuple(
                grant for grant in registry.grants if grant.uid != removed.uid
            ),
            removed_profile_uids=registry.removed_profile_uids,
        )
        _write_registry(updated)
        return updated, removed


def list_authority_grants() -> tuple[ProfileRegistry, tuple[AuthorityGrant, ...]]:
    registry = load_profile_registry()
    return registry, registry.grants


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
    # Contexts merely to validate one frozen binding.  This is especially
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


def resolve_share_endpoint(
    public_name: str,
    *,
    registry: ProfileRegistry | None = None,
) -> ShareEndpoint:
    """Resolve an exact SHARE grant without projecting receiver contents.

    SHARE is deliberately an endpoint capability rather than a readable view.
    The sender can address the public grant name, but learns no receiver data
    and cannot redirect delivery to an arbitrary Profile or Context path.
    """

    registry = registry or load_profile_registry()
    canonical = validate_grant_resource_name(public_name)
    sender = registry.active
    candidates = [
        grant
        for grant in registry.grants
        if grant.grantee_profile_uid == sender.uid
        and grant.public_name == canonical
        and "SHARE" in grant.permissions
    ]
    if not candidates:
        raise ProfileError(f"Share endpoint {canonical!r} does not exist.")
    if len(candidates) != 1:
        raise ProfileError(f"Share endpoint {canonical!r} is ambiguous.")
    grant = candidates[0]

    attachment = _context_record_at(
        profile_store_dir(sender),
        grant.attachment_context_name,
    )
    if attachment is None or attachment.uid != grant.attachment_context_uid:
        raise ProfileError("Share endpoint attachment Context identity changed.")

    authority = next(
        profile
        for profile in registry.profiles
        if profile.uid == grant.authority_profile_uid
    )
    receiver_root = profile_store_dir(authority)
    receiver = _context_record_at(receiver_root, grant.resource_name)
    if receiver is None or receiver.uid != grant.resource_uid:
        raise ProfileError("Share endpoint receiver Context identity changed.")
    if not any(
        binding.uid == receiver.uid and binding.name == receiver.name
        for binding in grant.contexts
    ):
        raise ProfileError("Share endpoint grant does not contain its receiver root.")
    return ShareEndpoint(
        grant=grant,
        authority=authority,
        sender=sender,
        public_name=canonical,
        receiver_context_name=receiver.name,
        receiver_root=receiver_root,
    )
