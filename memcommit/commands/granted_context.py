"""Resolve permissioned cross-Profile Context views for ordinary commands."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from memcommit.context import Context, MemoryRef, QueryContextRef
from memcommit.context_locator import resolve_context_locator
from memcommit.profile_config import AuthorityGrant, ProfileRegistry, load_profile_registry
from memcommit.profiles import (
    GrantedContextView,
    ProfileError,
    authority_grant_snapshot_lock,
    grants_for_attachment,
    resolve_granted_context_view,
)
from memcommit.store import MemoryStore
from memcommit.update import GrantedUpdateTarget, granted_target_digest


@dataclass(frozen=True)
class ContextAccess:
    """A local Context or a grant-resolved authority Context."""

    store: MemoryStore
    context_name: str
    display_name: str
    attachment_name: str | None
    permission: str
    view: GrantedContextView | None = None

    @property
    def is_granted(self) -> bool:
        return self.view is not None


def freeze_granted_context_binding(access: ContextAccess) -> GrantedUpdateTarget:
    """Freeze the complete control-plane identity behind one public view.

    ``GrantedUpdateTarget`` remains the serialized compatibility name, but the
    receipt itself is operation-neutral: read artifacts need the same grant,
    Profile, attachment, resource, and authority-Context preconditions as an
    update target.
    """

    view = access.view
    if view is None or access.attachment_name is None:
        raise ValueError("Expected a granted update target.")
    grant = view.grant
    return GrantedUpdateTarget(
        public_name=access.display_name,
        grantee_profile_uid=view.grantee.uid,
        authority_profile_uid=view.authority.uid,
        attachment_context_uid=grant.attachment_context_uid,
        attachment_context_name=access.attachment_name,
        grant_uid=grant.uid,
        grant_revision=grant.revision,
        grant_digest=granted_target_digest(grant.to_dict()),
        resource_uid=grant.resource_uid,
        resource_name=grant.resource_name,
        authority_context_name=view.authority_context_name,
        permissions=grant.permissions,
    )


def freeze_granted_update_target(access: ContextAccess) -> GrantedUpdateTarget:
    """Compatibility wrapper for persisted Update-session bindings."""

    return freeze_granted_context_binding(access)


def revalidate_granted_context_binding(
    binding: GrantedUpdateTarget,
    *,
    required_permission: str = "READ",
    registry: ProfileRegistry | None = None,
) -> ContextAccess:
    """Resolve one frozen artifact binding against the active grant registry."""

    active_store = MemoryStore()
    registry = registry or load_profile_registry()
    if registry.active.uid != binding.grantee_profile_uid:
        raise ProfileError(
            "The active Profile no longer matches the granted artifact binding."
        )
    access = resolve_context_access(
        active_store,
        binding.public_name,
        current_name=binding.attachment_context_name,
        required_permission=required_permission,
        registry=registry,
    )
    if not access.is_granted:
        raise ProfileError("The artifact no longer resolves to a granted Context.")
    if freeze_granted_context_binding(access) != binding:
        raise ProfileError(
            "The authority grant changed after this artifact was created."
        )
    return access


def resolve_context_access(
    active_store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
    required_permission: str,
    registry: ProfileRegistry | None = None,
) -> ContextAccess:
    """Prefer an ordinary local Context, then resolve an explicit granted view."""

    if operand is None:
        if not current_name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        operand = current_name

    local_name = resolve_context_locator(operand, current=current_name)
    if active_store.context_exists(local_name):
        return ContextAccess(
            store=active_store,
            context_name=local_name,
            display_name=local_name,
            attachment_name=None,
            permission=required_permission,
        )
    relative = operand.startswith(".")
    if (
        relative
        and current_name
        and active_store.context_exists(current_name)
    ):
        raise FileNotFoundError(f"Context '{local_name}' not found.")
    public_name = local_name if relative else operand
    registry = registry or load_profile_registry()
    attachment_names: list[str] = []
    if current_name and active_store.context_exists(current_name):
        attachment_names.append(current_name)
    for grant in registry.grants:
        if grant.grantee_profile_uid != registry.active.uid:
            continue
        if not (
            public_name == grant.public_name
            or public_name.startswith(grant.public_name + "/")
        ):
            continue
        if not active_store.context_exists(grant.attachment_context_name):
            continue
        attachment = active_store.load_direct(grant.attachment_context_name)
        if attachment.uid != grant.attachment_context_uid:
            continue
        if grant.attachment_context_name not in attachment_names:
            attachment_names.append(grant.attachment_context_name)

    resolved: list[GrantedContextView] = []
    errors: list[ProfileError] = []
    for attachment_name in attachment_names:
        try:
            candidate = resolve_granted_context_view(
                public_name,
                attachment_name=attachment_name,
                required_permission=required_permission,
                registry=registry,
            )
        except ProfileError as error:
            errors.append(error)
            continue
        if candidate not in resolved:
            resolved.append(candidate)
    if not resolved:
        if errors:
            raise errors[0]
        raise FileNotFoundError(f"Context '{local_name}' not found.")
    identities = {
        (
            candidate.grant.uid,
            candidate.grant.revision,
            candidate.authority.uid,
            candidate.authority_context_name,
        )
        for candidate in resolved
    }
    if len(identities) != 1:
        raise ProfileError(
            f"Granted view '{public_name}' is ambiguous across attachment Contexts."
        )
    view = resolved[0]
    return ContextAccess(
        store=MemoryStore(root=view.authority_root, create=False),
        context_name=view.authority_context_name,
        display_name=public_name,
        attachment_name=view.grant.attachment_context_name,
        permission=required_permission,
        view=view,
    )


def revalidate_context_access(
    access: ContextAccess,
    *,
    registry: ProfileRegistry | None = None,
) -> None:
    """Recheck a grant immediately before an authority-store mutation."""

    if access.view is None:
        return
    assert access.attachment_name is not None
    current = resolve_granted_context_view(
        access.display_name,
        attachment_name=access.attachment_name,
        required_permission=access.permission,
        registry=registry,
    )
    expected = access.view
    if (
        current.grant.uid != expected.grant.uid
        or current.grant.revision != expected.grant.revision
        or current.authority.uid != expected.authority.uid
        or current.grantee.uid != expected.grantee.uid
        or current.authority_context_name != expected.authority_context_name
    ):
        raise ProfileError(
            "The authority grant changed during this command; no change was saved."
        )


def _require_granted_permissions(
    access: ContextAccess,
    required_permissions: tuple[str, ...],
) -> None:
    if access.view is None:
        return
    missing = sorted(set(required_permissions) - set(access.view.grant.permissions))
    if missing:
        raise ProfileError(
            f"Grant {access.view.grant.uid[:8]} does not allow "
            + " + ".join(missing)
            + f" access to {access.display_name!r}."
        )


@contextmanager
def authorized_context_mutation(
    access: ContextAccess,
    *,
    required_permissions: tuple[str, ...] = (),
) -> Iterator[None]:
    """Keep every required grant permission valid through authority save."""

    if access.view is None:
        yield
        return
    _require_granted_permissions(access, required_permissions)
    # Grant changes and Profile switching use this same registry lock. Holding
    # it across the authority-store save closes the revoke-after-check race.
    with authority_grant_snapshot_lock() as registry:
        revalidate_context_access(access, registry=registry)
        _require_granted_permissions(access, required_permissions)
        yield


def grant_checkpoint_args(access: ContextAccess) -> dict[str, object]:
    """Return authority-side audit metadata for a granted mutation."""

    if access.view is None:
        return {}
    return {
        "authority_grant": {
            "uid": access.view.grant.uid,
            "revision": access.view.grant.revision,
            "grantee_profile_uid": access.view.grantee.uid,
            "public_context": access.display_name,
        }
    }


def attached_grants(
    attachment_name: str,
) -> tuple[ProfileRegistry, tuple[AuthorityGrant, ...]]:
    registry = load_profile_registry()
    return registry, grants_for_attachment(
        attachment_name=attachment_name,
        registry=registry,
    )


def top_level_grants(
    grants: tuple[AuthorityGrant, ...],
) -> tuple[AuthorityGrant, ...]:
    """Hide nested overrides from the attachment row that contains their parent."""

    return tuple(
        grant
        for grant in grants
        if not any(
            other.uid != grant.uid
            and grant.public_name.startswith(other.public_name + "/")
            for other in grants
        )
    )


def project_grants_into_context(
    context: Context,
    grants: tuple[AuthorityGrant, ...],
) -> Context:
    """Return a process-local navigation projection; never persist grant pointers."""

    projected = copy.deepcopy(context)
    for grant in top_level_grants(grants):
        if grant.resource_uid in projected.memories:
            raise ProfileError(
                "A granted view identity collides with an existing direct item."
            )
        if "READ" in grant.permissions:
            projected.add(Context(uid=grant.resource_uid, name=grant.public_name))
        elif "QUERY" in grant.permissions:
            projected.add(
                QueryContextRef(
                    uid=grant.uid,
                    name=grant.public_name,
                    target_source_uid=grant.resource_uid,
                    provider="authority-grant",
                )
            )
    return projected


def _public_name(grant: AuthorityGrant, authority_name: str) -> str:
    if not (
        authority_name == grant.resource_name
        or authority_name.startswith(grant.resource_name + "/")
    ):
        return authority_name
    return grant.public_name + authority_name[len(grant.resource_name) :]


def _authority_name(grant: AuthorityGrant, public_name: str) -> str:
    if not (
        public_name == grant.public_name
        or public_name.startswith(grant.public_name + "/")
    ):
        return public_name
    return grant.resource_name + public_name[len(grant.public_name) :]


class GrantedReadStore:
    """A read-only, name-remapping store constrained to one effective READ view."""

    def __init__(
        self,
        access: ContextAccess,
        *,
        registry: ProfileRegistry | None = None,
    ):
        if access.view is None or access.attachment_name is None:
            raise ValueError("GrantedReadStore requires a granted Context access.")
        self._access = access
        self._store = access.store
        self._grant = access.view.grant
        self._attachment = access.attachment_name
        self._registry = registry or load_profile_registry()
        self._all_grants = grants_for_attachment(
            attachment_name=self._attachment,
            registry=self._registry,
        )
        self._allowed_uids: dict[str, str] = {}
        self._allowed_names = self._resolve_allowed_names()
        self._nested_overrides = tuple(
            grant
            for grant in self._all_grants
            if grant.uid != self._grant.uid
            and grant.public_name.startswith(self._grant.public_name + "/")
        )

    def _resolve_allowed_names(self) -> tuple[str, ...]:
        allowed: list[str] = []
        for binding in self._grant.contexts:
            public = _public_name(self._grant, binding.name)
            candidates = [
                grant
                for grant in self._all_grants
                if public == grant.public_name
                or public.startswith(grant.public_name + "/")
            ]
            effective = max(
                candidates,
                key=lambda grant: len(grant.public_name.split("/")),
            )
            if "READ" not in effective.permissions:
                continue
            resolve_granted_context_view(
                public,
                attachment_name=self._attachment,
                required_permission="READ",
                registry=self._registry,
            )
            self._allowed_uids[public] = binding.uid
            allowed.append(public)
        return tuple(sorted(allowed))

    def list_context_names(self) -> list[str]:
        return list(self._allowed_names)

    def context_exists(self, public_name: str) -> bool:
        return public_name in self._allowed_names

    def _project(self, context: Context, public_name: str) -> Context:
        projected = copy.deepcopy(context)
        projected.name = public_name
        for item_uid, item in list(projected.iter_entries()):
            if isinstance(item, Context):
                candidate = _public_name(self._grant, item.name)
                if candidate in self._allowed_names:
                    item.name = candidate
                else:
                    # A persisted parent pointer is not independent READ
                    # authority.  Remove it before adding any narrower QUERY
                    # projection so the concealed Context cannot appear as a
                    # second, apparently readable child.
                    projected.remove(item_uid)
            elif isinstance(item, MemoryRef):
                candidate = _public_name(self._grant, item.target_context_name)
                if candidate in self._allowed_names:
                    item.target_context_name = candidate
                else:
                    # Even an unresolved reference would reveal concealed
                    # Context and Memory identities across the grant boundary.
                    projected.remove(item_uid)

        for override in self._nested_overrides:
            parent, separator, _ = override.public_name.rpartition("/")
            if separator and parent == public_name and "READ" not in override.permissions:
                projected.add(
                    QueryContextRef(
                        uid=override.uid,
                        name=override.public_name,
                        target_source_uid=override.resource_uid,
                        provider="authority-grant",
                    )
                )
        return projected

    def load_direct(self, public_name: str) -> Context:
        if public_name not in self._allowed_names:
            raise FileNotFoundError(f"Context '{public_name}' is outside the view.")
        authority_name = _authority_name(self._grant, public_name)
        context = self._store.load_direct(authority_name)
        if context.uid != self._allowed_uids[public_name]:
            raise ProfileError("Granted authority Context identity changed.")
        return self._project(context, public_name)

    def load(self, public_name: str, _loading=frozenset()) -> Context:
        """Resolve only embedded Contexts that remain inside the READ view."""

        context = self.load_direct(public_name)
        loading = _loading | {public_name}
        for item_uid, item in list(context.iter_entries()):
            if not isinstance(item, Context):
                continue
            if item.name in loading:
                context.remove(item_uid)
                continue
            child = self.load(item.name, loading)
            if child.uid != item.uid:
                raise ProfileError("Granted authority Context identity changed.")
            context.memories[item_uid] = child
        return context
