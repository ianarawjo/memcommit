"""Resolve permissioned cross-Profile Context views for application adapters."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Literal

from memcommit.core.context import (
    Context,
    GrantedContextLink,
    GrantedMemorySource,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.context_access.granted_view import (
    GrantedContextView,
    active_grant_placements,
    resolve_granted_context_view,
)
from memcommit.application.operations.profile.config import (
    AuthorityGrant,
    ProfileRegistry,
    active_profile_registry_for_store,
    load_profile_registry,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
)
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
    context_access_facts,
)
from memcommit.application.context_access import (
    GrantedContextBinding,
    granted_context_binding_digest,
)


@dataclass(frozen=True)
class ContextAccess:
    """A local Context or a grant-resolved authority Context."""

    store: MemoryStore
    context_name: str
    access_name: str
    permission: str
    view: GrantedContextView | None = None

    @property
    def is_granted(self) -> bool:
        return self.view is not None


def _resolve_bound_granted_context(
    active_store: MemoryStore,
    access_name: str,
    *,
    grant_uid: str,
    required_permission: str,
    registry: ProfileRegistry,
) -> ContextAccess:
    """Resolve an artifact's exact Grant placement, not a general locator."""

    view = resolve_granted_context_view(
        access_name,
        required_permission=required_permission,
        registry=registry,
        expected_grant_uid=grant_uid,
    )
    return ContextAccess(
        store=MemoryStore(root=view.authority_root, create=False),
        context_name=view.authority_context_name,
        access_name=access_name,
        permission=required_permission,
        view=view,
    )


def _resolve_granted_context_identity(
    active_store: MemoryStore,
    *,
    grant_uid: str,
    authority_context_name: str,
    required_permission: str,
    registry: ProfileRegistry,
) -> ContextAccess:
    """Resolve a durable Grant identity through its current placement name."""

    placed = [
        (placement, grant)
        for placement, grant in active_grant_placements(registry=registry)
        if grant.uid == grant_uid
    ]
    if len(placed) != 1:
        raise ProfileError("The Grant behind this persisted access is unavailable.")
    placement, grant = placed[0]
    if not (
        authority_context_name == grant.resource_name
        or authority_context_name.startswith(grant.resource_name + "/")
    ):
        raise ProfileError("The persisted authority Context is outside its Grant.")
    access_name = (
        placement.access_name + authority_context_name[len(grant.resource_name) :]
    )
    return _resolve_bound_granted_context(
        active_store,
        access_name,
        grant_uid=grant_uid,
        required_permission=required_permission,
        registry=registry,
    )


def resolve_granted_context_access(
    active_store: MemoryStore,
    access_name: str,
    *,
    grant_uid: str,
    required_permission: str,
    registry: ProfileRegistry,
) -> ContextAccess:
    """Resolve one access name through an already-selected Grant placement.

    A traversal that starts from a granted root must retain that authority
    coordinate even when a local Context happens to reuse a descendant public
    name.  General operand resolution intentionally prefers local ownership;
    this narrower helper is for operation-owned traversal beneath an explicit
    granted Source.
    """

    return _resolve_bound_granted_context(
        active_store,
        access_name,
        grant_uid=grant_uid,
        required_permission=required_permission,
        registry=registry,
    )


def granted_context_link(
    access: ContextAccess,
    *,
    context_uid: str,
) -> GrantedContextLink:
    """Create one content-free persistent link from exact granted access."""

    view = access.view
    if view is None:
        raise ValueError("Granted Context links require granted access.")
    if "READ" not in view.grant.permissions:
        raise ProfileError(
            f"Grant {view.grant.uid[:8]} does not allow read access "
            f"to {access.access_name!r}."
        )
    return GrantedContextLink(
        context_uid=context_uid,
        access_name=access.access_name,
        authority_context_name=access.context_name,
        authority_profile_uid=view.authority.uid,
        grantee_profile_uid=view.grantee.uid,
        grant_uid=view.grant.uid,
        grant_revision_at_creation=view.grant.revision,
        resource_uid=view.grant.resource_uid,
        resource_name=view.grant.resource_name,
    )


def granted_memory_source(
    access: ContextAccess,
    *,
    context_uid: str,
    memory_uid: str,
) -> GrantedMemorySource:
    """Capture exact Grant provenance for a retained or live Memory relation."""

    view = access.view
    if view is None:
        raise ValueError("Granted Memory Sources require granted access.")
    return GrantedMemorySource(
        context_uid=context_uid,
        access_name=access.access_name,
        authority_context_name=access.context_name,
        authority_profile_uid=view.authority.uid,
        grantee_profile_uid=view.grantee.uid,
        grant_uid=view.grant.uid,
        grant_revision_at_creation=view.grant.revision,
        resource_uid=view.grant.resource_uid,
        resource_name=view.grant.resource_name,
        memory_uid=memory_uid,
    )


def load_granted_context_link(
    link: GrantedContextLink,
    *,
    active_store: MemoryStore,
    loading: frozenset[str] = frozenset(),
) -> Context:
    """Reauthorize and resolve one persisted link without cached content.

    Permission and effective nested overrides are checked on every recursive
    load. Grant revision may advance while the same authority/resource binding
    remains valid; revocation, scope replacement, or identity replacement fails
    closed and leaves the direct serialized link untouched.
    """

    if not isinstance(link, GrantedContextLink):
        raise TypeError("Granted Context link is invalid.")
    registry = load_profile_registry()
    if registry.active.uid != link.grantee_profile_uid:
        raise ProfileError(
            "The active Profile no longer matches the granted Context link."
        )
    access = _resolve_granted_context_identity(
        active_store,
        grant_uid=link.grant_uid,
        authority_context_name=link.authority_context_name,
        required_permission="READ",
        registry=registry,
    )
    view = access.view
    assert view is not None
    from memcommit.application.authorization.context_operation import (
        _require_granted_permissions,
    )

    _require_granted_permissions(access, ("READ",))
    grant = view.grant
    if (
        grant.uid != link.grant_uid
        or grant.revision < link.grant_revision_at_creation
        or view.authority.uid != link.authority_profile_uid
        or view.grantee.uid != link.grantee_profile_uid
        or grant.resource_uid != link.resource_uid
        or grant.resource_name != link.resource_name
        or access.context_name != link.authority_context_name
    ):
        raise ProfileError(
            "The authority Grant binding behind an embedded Context changed."
        )
    if access.access_name in loading:
        return Context(uid=link.context_uid, name=access.access_name)
    context = GrantedReadStore(
        access,
        registry=registry,
        traversal_mode="EMBED",
    ).load(access.access_name)
    if context.uid != link.context_uid:
        raise ProfileError("Granted embedded Context identity changed.")
    context._granted_link = granted_context_link(access, context_uid=context.uid)
    return context


def load_granted_memory_source(
    source: GrantedMemorySource,
    *,
    active_store: MemoryStore,
) -> Memory:
    """Reauthorize one content-free granted Memory Embed and load its value."""

    if not isinstance(source, GrantedMemorySource):
        raise TypeError("Granted Memory Source is invalid.")
    registry = load_profile_registry()
    if registry.active.uid != source.grantee_profile_uid:
        raise ProfileError(
            "The active Profile no longer matches the granted Memory link."
        )
    access = _resolve_granted_context_identity(
        active_store,
        grant_uid=source.grant_uid,
        authority_context_name=source.authority_context_name,
        required_permission="READ",
        registry=registry,
    )
    view = access.view
    assert view is not None
    from memcommit.application.authorization.context_operation import (
        _require_granted_permissions,
    )

    _require_granted_permissions(access, ("READ",))
    grant = view.grant
    if (
        grant.uid != source.grant_uid
        or grant.revision < source.grant_revision_at_creation
        or view.authority.uid != source.authority_profile_uid
        or view.grantee.uid != source.grantee_profile_uid
        or grant.resource_uid != source.resource_uid
        or grant.resource_name != source.resource_name
        or access.context_name != source.authority_context_name
    ):
        raise ProfileError(
            "The authority Grant binding behind an embedded Memory changed."
        )
    context = GrantedReadStore(access, registry=registry).load_direct(
        access.access_name
    )
    if context.uid != source.context_uid:
        raise ProfileError("Granted embedded Memory owner identity changed.")
    memory = context.memories.get(source.memory_uid)
    if not isinstance(memory, Memory):
        raise ProfileError("Granted embedded Memory is no longer available.")
    return memory


def context_access_display_facts(
    access: ContextAccess,
    *,
    reach: SourceReach = SourceReach.DIRECT,
    form: SourceForm = SourceForm.CONTEXT,
    states: tuple[SourceState, ...] = (),
) -> SourceDisplayFacts:
    """Project authority facts without leaking operation wording into callers."""

    permissions = access.view.grant.permissions if access.view is not None else ()
    return context_access_facts(
        granted=access.is_granted,
        permission=access.permission,
        permissions=permissions,
        reach=reach,
        form=form,
        states=states,
    )


def freeze_granted_context_binding(access: ContextAccess) -> GrantedContextBinding:
    """Freeze the complete control-plane identity behind one placed view.

    Read and mutation artifacts need the same Grant, Profile, resource, and
    authority-Context preconditions. Their reviewed access name remains a
    freshness precondition even though it is not authority identity.
    """

    view = access.view
    if view is None:
        raise ValueError("Expected a granted Context binding.")
    grant = view.grant
    return GrantedContextBinding(
        access_name=access.access_name,
        grantee_profile_uid=view.grantee.uid,
        authority_profile_uid=view.authority.uid,
        grant_uid=grant.uid,
        grant_revision=grant.revision,
        grant_digest=granted_context_binding_digest(grant.to_dict()),
        resource_uid=grant.resource_uid,
        resource_name=grant.resource_name,
        authority_context_name=view.authority_context_name,
        permissions=grant.permissions,
    )


def revalidate_granted_context_binding(
    binding: GrantedContextBinding,
    *,
    required_permission: str = "READ",
    registry: ProfileRegistry | None = None,
    active_store: MemoryStore | None = None,
) -> ContextAccess:
    """Resolve one frozen artifact binding against the active grant registry."""

    active_store = active_store or MemoryStore()
    registry = registry or load_profile_registry()
    if registry.active.uid != binding.grantee_profile_uid:
        raise ProfileError(
            "The active Profile no longer matches the granted artifact binding."
        )
    access = _resolve_bound_granted_context(
        active_store,
        binding.access_name,
        grant_uid=binding.grant_uid,
        required_permission=required_permission,
        registry=registry,
    )
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
            access_name=local_name,
            permission=required_permission,
        )
    # Relative spelling selects one canonical access name; it must not make
    # lookup local-only because a readable Grant may deliberately occupy the
    # namespace below an ordinary local ancestor.  An exact local record has
    # already won above, so Grant fallback cannot displace local ownership.
    access_name = local_name
    registry = active_profile_registry_for_store(
        active_store.store_dir,
        registry=registry,
    )
    if registry is None:
        raise FileNotFoundError(f"Context '{local_name}' does not exist.")
    placed = active_grant_placements(registry=registry)
    if not any(
        access_name == placement.access_name
        or access_name.startswith(placement.access_name + "/")
        for placement, _grant in placed
    ):
        raise FileNotFoundError(f"Context '{local_name}' does not exist.")
    view = resolve_granted_context_view(
        access_name,
        required_permission=required_permission,
        registry=registry,
    )
    return ContextAccess(
        store=MemoryStore(root=view.authority_root, create=False),
        context_name=view.authority_context_name,
        access_name=access_name,
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
    current = resolve_granted_context_view(
        access.access_name,
        required_permission=access.permission,
        registry=registry,
        expected_grant_uid=access.view.grant.uid,
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


def grant_checkpoint_args(access: ContextAccess) -> dict[str, object]:
    """Return authority-side audit metadata for a granted mutation."""

    if access.view is None:
        return {}
    return {
        "authority_grant": {
            "uid": access.view.grant.uid,
            "revision": access.view.grant.revision,
            "grantee_profile_uid": access.view.grantee.uid,
            "access_context": access.access_name,
        }
    }


def _access_name(
    grant: AuthorityGrant,
    placement,
    authority_name: str,
) -> str:
    if not (
        authority_name == grant.resource_name
        or authority_name.startswith(grant.resource_name + "/")
    ):
        return authority_name
    return placement.access_name + authority_name[len(grant.resource_name) :]


def _authority_name(grant: AuthorityGrant, placement, access_name: str) -> str:
    if not (
        access_name == placement.access_name
        or access_name.startswith(placement.access_name + "/")
    ):
        return access_name
    return grant.resource_name + access_name[len(placement.access_name) :]


GrantedTraversalMode = Literal["READ", "EMBED"]


class GrantedReadStore:
    """A read-only, name-remapping store constrained to one effective view."""

    def __init__(
        self,
        access: ContextAccess,
        *,
        registry: ProfileRegistry | None = None,
        traversal_mode: GrantedTraversalMode = "READ",
    ):
        if access.view is None:
            raise ValueError("GrantedReadStore requires a granted Context access.")
        if traversal_mode not in {"READ", "EMBED"}:
            raise ValueError("Granted traversal mode must be READ or EMBED.")
        self._access = access
        self._store = access.store
        self._grant = access.view.grant
        self._placement = access.view.placement
        self._registry = registry or load_profile_registry()
        # Both ordinary browsing and durable live links disclose the same raw
        # Context bytes. ``EMBED`` remains a traversal shape, not a Grant atom.
        self._required_traversal_permissions = ("READ",)
        self._all_placed = active_grant_placements(registry=self._registry)
        self._allowed_uids: dict[str, str] = {}
        self._allowed_names = self._resolve_allowed_names()
        self._nested_overrides = tuple(
            (placement, grant)
            for placement, grant in self._all_placed
            if grant.uid != self._grant.uid
            and placement.access_name.startswith(self._placement.access_name + "/")
        )

    def _resolve_allowed_names(self) -> tuple[str, ...]:
        allowed: list[str] = []
        for binding in self._grant.contexts:
            access_name = _access_name(
                self._grant,
                self._placement,
                binding.name,
            )
            candidates = [
                (placement, grant)
                for placement, grant in self._all_placed
                if access_name == placement.access_name
                or access_name.startswith(placement.access_name + "/")
            ]
            effective_placement, effective_grant = max(
                candidates,
                key=lambda item: len(item[0].access_name.split("/")),
            )
            if any(
                permission not in effective_grant.permissions
                for permission in self._required_traversal_permissions
            ):
                continue
            for permission in self._required_traversal_permissions:
                resolve_granted_context_view(
                    access_name,
                    required_permission=permission,
                    registry=self._registry,
                    expected_grant_uid=effective_grant.uid,
                )
            self._allowed_uids[access_name] = binding.uid
            allowed.append(access_name)
        return tuple(sorted(allowed))

    def list_context_names(self) -> list[str]:
        return list(self._allowed_names)

    def context_exists(self, access_name: str) -> bool:
        return access_name in self._allowed_names

    def _project(self, context: Context, access_name: str) -> Context:
        projected = copy.deepcopy(context)
        projected.name = access_name
        for item_uid, item in list(projected.iter_entries()):
            if isinstance(item, Context):
                candidate = _access_name(
                    self._grant,
                    self._placement,
                    item.name,
                )
                if candidate in self._allowed_names:
                    item.name = candidate
                else:
                    # A persisted parent pointer is not independent traversal
                    # authority. Remove it before adding any narrower QUERY
                    # projection so a restricted Context cannot appear as a
                    # second child reached under the parent's broader Grant.
                    projected.remove(item_uid)
            elif isinstance(item, MemoryRef):
                candidate = _access_name(
                    self._grant,
                    self._placement,
                    item.target_context_name,
                )
                if candidate in self._allowed_names:
                    item.target_context_name = candidate
                else:
                    # Even an unresolved reference would reveal concealed
                    # Context and Memory identities across the grant boundary.
                    projected.remove(item_uid)

        for placement, override in self._nested_overrides:
            parent, separator, _ = placement.access_name.rpartition("/")
            if (
                separator
                and parent == access_name
                and "READ" not in override.permissions
            ):
                projected.add(
                    QueryContextRef(
                        uid=override.uid,
                        name=placement.access_name,
                        target_source_uid=override.resource_uid,
                        provider="authority-grant",
                    )
                )
        return projected

    def project_direct(self, context: Context, access_name: str) -> Context:
        """Project one already-read authority record under its access name.

        Callers that freeze retained multi-Context artifacts need package bytes
        and the physical authority digest to describe the same single read.
        Accepting the raw record here avoids a second Store read that could
        otherwise race with the first before the frozen plan is assembled.
        """

        if access_name not in self._allowed_names:
            raise FileNotFoundError(f"Context '{access_name}' is outside the view.")
        authority_name = _authority_name(
            self._grant,
            self._placement,
            access_name,
        )
        if (
            context.name != authority_name
            or context.uid != self._allowed_uids[access_name]
        ):
            raise ProfileError("Granted authority Context identity changed.")
        return self._project(context, access_name)

    def load_direct(self, access_name: str) -> Context:
        if access_name not in self._allowed_names:
            raise FileNotFoundError(f"Context '{access_name}' is outside the view.")
        authority_name = _authority_name(
            self._grant,
            self._placement,
            access_name,
        )
        context = self._store.load_direct(authority_name)
        return self.project_direct(context, access_name)

    def load(self, access_name: str, _loading=frozenset()) -> Context:
        """Resolve only embedded Contexts allowed by this traversal mode."""

        context = self.load_direct(access_name)
        loading = _loading | {access_name}
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
