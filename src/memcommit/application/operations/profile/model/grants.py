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
    GrantPlacement,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    canonical_grant_permissions,
    validate_grant_resource_name,
)
from memcommit.application.authorization.checkpoint_read_model import (
    CheckpointEmbed,
    CheckpointRead,
    CheckpointReference,
    CheckpointReadValueError,
    canonical_checkpoint_reads,
)
from memcommit.application.capabilities.history.query.checkpoint_history_slicing import (
    build_checkpoint_history_slice,
)
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    HistoryError,
)
from memcommit.application.capabilities.operand_resolution import (
    ContextOperandNotFoundError,
    resolve_existing_local_context_operand,
)
from memcommit.application.capabilities.context_locator import (
    is_relative_context_locator,
)
from memcommit.application.capabilities.durable_uid_resolution import (
    is_unresolved_uid_selector,
)
from memcommit.persistence.store import MemoryStore

from ._storage import (
    ProfileError as ProfileError,
    _context_record_at as _context_record_at,
    _context_records as _context_records,
    _registry_lock as _registry_lock,
    _write_registry as _write_registry,
)


@dataclass(frozen=True)
class ShareEndpoint:
    """One grant-backed cross-Profile delivery target."""

    grant: AuthorityGrant
    placement: GrantPlacement
    authority: ProfileEntry
    sender: ProfileEntry
    access_name: str
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


def _grant_checkpoint_reads(
    value: object,
    *,
    permissions: tuple[str, ...],
    contexts: tuple[GrantContextBinding, ...],
) -> tuple[CheckpointRead, ...]:
    try:
        reads = canonical_checkpoint_reads(value)
    except CheckpointReadValueError as error:
        raise ProfileError(str(error)) from error
    if reads and "READ" not in permissions:
        raise ProfileError("Checkpoint reads require READ permission.")
    context_uids = {context.uid for context in contexts}
    if any(read.context_uid not in context_uids for read in reads):
        raise ProfileError("Checkpoint read names a Context outside its Grant scope.")
    return reads


def _assert_checkpoint_reads_retained(
    authority: ProfileEntry,
    contexts: tuple[GrantContextBinding, ...],
    reads: tuple[CheckpointRead, ...],
) -> None:
    """Reject a newly authored right whose immutable anchor is already absent."""

    if not reads:
        return
    names_by_uid = {context.uid: context.name for context in contexts}
    store = MemoryStore(
        root=profile_store_dir(authority),
        create=False,
        resolve_granted_links=False,
    )
    histories = {}
    try:
        for read in reads:
            history = histories.get(read.context_uid)
            if history is None:
                history = build_checkpoint_history_slice(
                    store,
                    names_by_uid[read.context_uid],
                )
                histories[read.context_uid] = history
            if isinstance(read.scope, CheckpointReference):
                history.reference(read.scope.checkpoint_uids)
            elif isinstance(read.scope, CheckpointEmbed):
                history.after(read.scope.checkpoint_uid)
    except (KeyError, HistoryError) as error:
        raise ProfileError(
            f"Checkpoint read does not name retained authority History: {error}"
        ) from error


def _assert_access_name_available(
    registry: ProfileRegistry,
    *,
    grantee: ProfileEntry,
    access_name: str,
    replacing_uid: str | None = None,
) -> None:
    grantee_contexts, _ = _context_records(profile_store_dir(grantee))
    access_folded = access_name.casefold()
    for name in grantee_contexts:
        name_folded = name.casefold()
        if name_folded == access_folded or name_folded.startswith(access_folded + "/"):
            raise ProfileError(
                f"Granted access {access_name!r} overlaps local Context {name!r}."
            )
        # A lexical local ancestor is safe and lets a borrowed view appear
        # below its task namespace. The granted leaf and its descendants must
        # still remain absent locally or local resolution would bypass grants.
    for placement in registry.grant_placements:
        if placement.grant_uid == replacing_uid:
            continue
        if (
            placement.grantee_profile_uid == grantee.uid
            and placement.access_name.casefold() == access_folded
        ):
            raise ProfileError(f"Granted access {access_name!r} already exists.")


def grant_placement(
    registry: ProfileRegistry,
    grant: AuthorityGrant | str,
) -> GrantPlacement:
    """Return the grantee-owned placement for one exact Grant."""

    grant_uid = grant.uid if isinstance(grant, AuthorityGrant) else grant
    matches = tuple(
        placement
        for placement in registry.grant_placements
        if placement.grant_uid == grant_uid
    )
    if len(matches) != 1:
        raise ProfileError("Authority Grant access path is missing or ambiguous.")
    return matches[0]


def create_authority_grant(
    *,
    authority_name: str,
    grantee_name: str,
    resource_name: str,
    permissions: object,
    recursive: bool = False,
    grant_uid: str | None = None,
    checkpoint_reads: object = (),
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Create one exact cross-Profile Context view under the registry lock."""

    canonical_permissions = canonical_grant_permissions(permissions)
    # Fail invalid names before opening either Profile store. Relative
    # locators and UID selectors are the only existing-Context spellings that
    # are not themselves canonical portable names.
    if not is_relative_context_locator(
        resource_name
    ) and not is_unresolved_uid_selector(resource_name):
        validate_portable_context_name(resource_name)
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
        authority_store = MemoryStore(
            root=profile_store_dir(authority),
            create=False,
        )
        try:
            resolved_resource = resolve_existing_local_context_operand(
                authority_store,
                resource_name,
                current=authority_store.current_context_name(),
            )
        except ContextOperandNotFoundError as error:
            raise ProfileError(
                f"Authority Context {resource_name!r} does not exist."
            ) from error
        resource_name = resolved_resource.name
        # A new Grant persists canonical ordinary names even when its CLI
        # operand used relative spelling or a durable Context UID.
        validate_portable_context_name(resource_name)
        authority_contexts, _ = _context_records(profile_store_dir(authority))
        authority_root = authority_contexts.get(resource_name)
        if authority_root is None or authority_root.uid != resolved_resource.uid:
            raise ProfileError(
                "Authority Context changed identity during Grant resolution."
            )
        scope = _grant_scope(
            authority_contexts,
            resource_name,
            recursive=recursive,
        )
        for binding in scope:
            validate_portable_context_name(binding.name)
        canonical_reads = _grant_checkpoint_reads(
            checkpoint_reads,
            permissions=canonical_permissions,
            contexts=scope,
        )
        _assert_checkpoint_reads_retained(authority, scope, canonical_reads)
        access_name = validate_portable_context_name(
            f"granted/{authority.name}/{resource_name}"
        )
        _assert_access_name_available(
            registry,
            grantee=grantee,
            access_name=access_name,
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
            resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
            resource_uid=root.uid,
            resource_name=root.name,
            permissions=canonical_permissions,
            contexts=scope,
            checkpoint_reads=canonical_reads,
        )
        placement = GrantPlacement(
            grant_uid=grant.uid,
            grantee_profile_uid=grantee.uid,
            access_name=access_name,
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=(*registry.grants, grant),
            removed_profile_uids=registry.removed_profile_uids,
            grant_placements=(*registry.grant_placements, placement),
        )
        _write_registry(updated)
        return updated, grant


def update_authority_grant(
    selector: str,
    *,
    permissions: object,
    recursive: bool | None = None,
    checkpoint_reads: object | None = None,
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
        canonical_reads = _grant_checkpoint_reads(
            (
                existing.checkpoint_reads
                if checkpoint_reads is None
                else checkpoint_reads
            ),
            permissions=canonical_permissions,
            contexts=scope,
        )
        _assert_checkpoint_reads_retained(authority, scope, canonical_reads)
        replacement = AuthorityGrant(
            uid=existing.uid,
            revision=existing.revision + 1,
            authority_profile_uid=existing.authority_profile_uid,
            grantee_profile_uid=existing.grantee_profile_uid,
            resource_kind=existing.resource_kind,
            resource_uid=scope[0].uid,
            resource_name=scope[0].name,
            permissions=canonical_permissions,
            contexts=scope,
            checkpoint_reads=canonical_reads,
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
            grant_placements=registry.grant_placements,
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
            grant_placements=tuple(
                placement
                for placement in registry.grant_placements
                if placement.grant_uid != removed.uid
            ),
        )
        _write_registry(updated)
        return updated, removed


def list_authority_grants() -> tuple[ProfileRegistry, tuple[AuthorityGrant, ...]]:
    registry = load_profile_registry()
    return registry, registry.grants


def resolve_share_endpoint(
    access_name: str,
    *,
    registry: ProfileRegistry | None = None,
) -> ShareEndpoint:
    """Resolve an exact SHARE grant without projecting receiver contents.

    SHARE is deliberately an endpoint capability rather than a readable view.
    The sender can address its Grant access name, but learns no receiver data
    and cannot redirect delivery to an arbitrary Profile or Context path.
    """

    registry = registry or load_profile_registry()
    canonical = validate_grant_resource_name(access_name)
    sender = registry.active
    placements = {
        placement.grant_uid: placement
        for placement in registry.grant_placements
        if placement.grantee_profile_uid == sender.uid
        and placement.access_name == canonical
    }
    candidates = [
        grant
        for grant in registry.grants
        if grant.grantee_profile_uid == sender.uid
        and grant.uid in placements
        and "SHARE" in grant.permissions
    ]
    if not candidates:
        raise ProfileError(f"Share endpoint {canonical!r} does not exist.")
    if len(candidates) != 1:
        raise ProfileError(f"Share endpoint {canonical!r} is ambiguous.")
    grant = candidates[0]
    placement = placements[grant.uid]

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
        placement=placement,
        authority=authority,
        sender=sender,
        access_name=canonical,
        receiver_context_name=receiver.name,
        receiver_root=receiver_root,
    )
