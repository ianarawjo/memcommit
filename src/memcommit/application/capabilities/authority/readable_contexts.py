"""Unify readable Contexts into one Store-like namespace."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    GrantedReadStore,
    resolve_context_access,
    top_level_grants,
)
from memcommit.core.context import Context, QueryContextRef
from memcommit.application.capabilities.retained_history.context_snapshot import ContextSnapshotRef
from memcommit.application.capabilities.authority.granted_context_navigation import (
    GrantedContextNavigation,
    freeze_granted_context_navigation,
)
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.operations.profile.config import (
    AuthorityGrant,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.source_projection.presentation import SourceDisplayValue
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class ReadableContextBinding:
    """Bind one public name to the exact store-authority used to read it."""

    public_name: str
    access: ContextAccess


@dataclass(frozen=True)
class ProfileContextNavigation:
    """One switch-compatible Profile tree with exact readable bindings."""

    catalog: ReadableContextCatalog
    local_names: tuple[str, ...]
    virtual_names: tuple[str, ...]
    selectable_virtual_names: frozenset[str]
    virtual_annotations: dict[str, SourceDisplayValue]

    @property
    def names(self) -> tuple[str, ...]:
        """Return every visible public name in deterministic tree order."""

        return tuple(sorted((*self.local_names, *self.virtual_names)))


class ReadableContextCatalog:
    """Expose local and READ-granted Contexts through one public-name catalog.

    Public namespace membership comes from canonical Context names. Grant
    attachment remains authorization metadata and is deliberately not treated
    as a semantic parent/child edge.
    """

    def __init__(
        self,
        active_store: MemoryStore,
        root_access: ContextAccess,
        *,
        registry: ProfileRegistry | None = None,
        include_query_routes: bool = True,
    ) -> None:
        self._active_store = active_store
        self._root_access = root_access
        self._include_query_routes = include_query_routes
        self._granted_stores: dict[str, GrantedReadStore] = {}
        self._bindings: dict[str, ReadableContextBinding] = {}
        self._attached_read_names_by_parent: dict[str, tuple[str, ...]] = {}
        self._query_routes_by_parent: dict[str, tuple[QueryContextRef, ...]] = {}

        if root_access.is_granted:
            granted = GrantedReadStore(root_access, registry=registry)
            self._granted_stores[root_access.display_name] = granted
            for name in granted.list_context_names():
                self._bindings[name] = ReadableContextBinding(name, root_access)
            self._names = tuple(granted.list_context_names())
            return

        local_names = tuple(active_store.list_context_names())
        for name in local_names:
            self._bindings[name] = ReadableContextBinding(
                name,
                ContextAccess(
                    store=active_store,
                    context_name=name,
                    display_name=name,
                    attachment_name=None,
                    permission="READ",
                ),
            )

        registry = self._active_registry(registry)
        if registry is not None:
            valid_grants = tuple(self._valid_active_grants(registry))
            self._add_granted_bindings(registry, valid_grants)
            self._freeze_attached_read_names(valid_grants)
            if include_query_routes:
                self._freeze_query_routes(registry, valid_grants)
        self._names = tuple(sorted(self._bindings))

    def _active_registry(
        self,
        registry: ProfileRegistry | None,
    ) -> ProfileRegistry | None:
        value = registry or load_profile_registry()
        # An isolated or explicitly rooted MemoryStore must never inherit the
        # host Profile's virtual grants merely because a registry is present.
        if (
            self._active_store.store_dir.resolve()
            != profile_store_dir(value.active).resolve()
        ):
            return None
        return value

    def _valid_active_grants(self, registry: ProfileRegistry):
        for grant in registry.grants:
            if grant.grantee_profile_uid != registry.active.uid:
                continue
            if not self._active_store.context_exists(grant.attachment_context_name):
                continue
            attachment = self._active_store.load_direct(grant.attachment_context_name)
            if attachment.uid != grant.attachment_context_uid:
                continue
            yield grant

    def _add_granted_bindings(
        self,
        registry: ProfileRegistry,
        grants: Sequence[AuthorityGrant],
    ) -> None:
        candidate_names: set[str] = set()
        for grant in grants:
            for binding in grant.contexts:
                suffix = binding.name[len(grant.resource_name) :]
                candidate_names.add(grant.public_name + suffix)

        for public_name in sorted(candidate_names):
            try:
                access = resolve_context_access(
                    self._active_store,
                    public_name,
                    current_name=self._root_access.context_name,
                    required_permission="READ",
                    registry=registry,
                )
            except FileNotFoundError:
                continue
            except ProfileError:
                # QUERY-only overrides, stale bindings, and ambiguous public
                # routes are all absent from the readable catalog. Exact use
                # still reports the resolver's detailed failure; enumeration
                # must never guess which authority view was intended.
                continue
            if not access.is_granted:
                continue
            self._bindings[public_name] = ReadableContextBinding(
                public_name,
                access,
            )

    def _freeze_attached_read_names(
        self,
        grants: Sequence[AuthorityGrant],
    ) -> None:
        """Freeze exact attachment projections without changing hierarchy.

        A Grant attachment remains authorization metadata: it does not enter
        ``list_context_names`` as a parent edge and lexical expansion continues
        to use only canonical public names.  A selected local Context does,
        however, display its top-level READ grants as directly available source
        rows.  Following readable embeds must open those displayed rows through
        their already-frozen bindings instead of leaving them as empty shells.
        """

        by_attachment: dict[str, list[AuthorityGrant]] = {}
        for grant in grants:
            by_attachment.setdefault(grant.attachment_context_name, []).append(grant)

        frozen: dict[str, tuple[str, ...]] = {}
        for attachment_name, attached in by_attachment.items():
            names: list[str] = []
            for grant in top_level_grants(tuple(attached)):
                if "READ" not in grant.permissions:
                    continue
                binding = self._bindings.get(grant.public_name)
                if binding is None or not binding.access.is_granted:
                    continue
                access = binding.access
                if (
                    access.attachment_name != attachment_name
                    or access.view is None
                    or access.view.grant.uid != grant.uid
                ):
                    continue
                names.append(grant.public_name)
            if names:
                frozen[attachment_name] = tuple(sorted(set(names), key=str.casefold))
        self._attached_read_names_by_parent = frozen

    def _freeze_query_routes(
        self,
        registry: ProfileRegistry,
        grants: Sequence[AuthorityGrant],
    ) -> None:
        by_parent: dict[str, list[QueryContextRef]] = {}
        seen_names: set[str] = set()
        for grant in grants:
            public_name = grant.public_name
            if public_name in seen_names:
                continue
            try:
                resolve_context_access(
                    self._active_store,
                    public_name,
                    current_name=self._root_access.context_name,
                    required_permission="READ",
                    registry=registry,
                )
                continue
            except (FileNotFoundError, ProfileError):
                pass
            try:
                query_access = resolve_context_access(
                    self._active_store,
                    public_name,
                    current_name=self._root_access.context_name,
                    required_permission="QUERY",
                    registry=registry,
                )
            except (FileNotFoundError, ProfileError):
                continue
            parent, separator, _ = public_name.rpartition("/")
            if not separator or parent not in self._bindings:
                continue
            seen_names.add(public_name)
            by_parent.setdefault(parent, []).append(
                QueryContextRef(
                    uid=query_access.view.grant.uid,
                    name=public_name,
                    target_source_uid=query_access.view.grant.resource_uid,
                    provider="authority-grant",
                )
            )
        self._query_routes_by_parent = {
            parent: tuple(sorted(routes, key=lambda item: item.name))
            for parent, routes in by_parent.items()
        }

    def list_context_names(self) -> list[str]:
        return list(self._names)

    def context_exists(self, public_name: str) -> bool:
        return public_name in self._bindings

    def access_for(self, public_name: str) -> ContextAccess:
        """Return the exact ownership/authority binding for one public name."""

        binding = self._bindings.get(public_name)
        if binding is None:
            raise FileNotFoundError(f"Context '{public_name}' is outside the view.")
        return binding.access

    def granted_names_below(self, root_name: str) -> tuple[str, ...]:
        """Return readable granted names in the root's public namespace."""

        scope = ContextScope.create((root_name,), include_descendants=True)
        return tuple(
            name
            for name in expand_lexical_context_names(scope, self._names)[1:]
            if self._bindings[name].access.is_granted
        )

    def attached_read_names(self, parent_name: str) -> tuple[str, ...]:
        """Return top-level READ projections attached to one exact local row."""

        return self._attached_read_names_by_parent.get(parent_name, ())

    def _granted_store(self, access: ContextAccess) -> GrantedReadStore:
        assert access.is_granted
        key = access.view.grant.uid
        store = self._granted_stores.get(key)
        if store is None:
            store = GrantedReadStore(access)
            self._granted_stores[key] = store
        return store

    def _project_local_query_routes(self, context: Context) -> Context:
        if not self._include_query_routes:
            return context
        projected = copy.deepcopy(context)

        def visit(current: Context) -> None:
            for route in self._query_routes_by_parent.get(current.name, ()):
                existing = current.memories.get(route.uid)
                if existing is None:
                    current.add(copy.deepcopy(route))
                elif not (
                    isinstance(existing, QueryContextRef)
                    and existing.name == route.name
                ):
                    raise ProfileError(
                        "A query-only grant identity collides with a local item."
                    )
            for item in current.iter_items():
                if isinstance(item, Context):
                    visit(item)

        visit(projected)
        return projected

    def _project_local_attached_reads(
        self,
        context: Context,
        *,
        loading: frozenset[str],
    ) -> Context:
        """Resolve displayed READ projections as process-local source edges."""

        projected = copy.deepcopy(context)

        def visit(current: Context, ancestors: frozenset[str]) -> None:
            binding = self._bindings.get(current.name)
            if binding is not None and not binding.access.is_granted:
                for public_name in self.attached_read_names(current.name):
                    if public_name in ancestors:
                        continue
                    child = self.load(public_name, ancestors | {current.name})
                    existing = current.memories.get(child.uid)
                    if existing is None:
                        current.add(child)
                    elif not (
                        isinstance(existing, Context)
                        and existing.name == child.name
                    ):
                        raise ProfileError(
                            "A granted view identity collides with an existing "
                            "direct item."
                        )
            for item in tuple(current.iter_items()):
                if isinstance(item, Context) and not isinstance(
                    item,
                    ContextSnapshotRef,
                ):
                    child_binding = self._bindings.get(item.name)
                    if child_binding is not None and not child_binding.access.is_granted:
                        visit(item, ancestors | {current.name})

        visit(projected, loading)
        return projected

    def load_direct(self, public_name: str) -> Context:
        binding = self._bindings.get(public_name)
        if binding is None:
            raise FileNotFoundError(f"Context '{public_name}' is outside the view.")
        access = binding.access
        if access.is_granted:
            return self._granted_store(access).load_direct(public_name)
        return self._project_local_query_routes(
            self._active_store.load_direct(public_name)
        )

    def load_without_attached_reads(self, public_name: str) -> Context:
        """Resolve persisted refs while excluding process-local READ sources."""

        binding = self._bindings.get(public_name)
        if binding is None:
            raise FileNotFoundError(f"Context '{public_name}' is outside the view.")
        access = binding.access
        if access.is_granted:
            return self._granted_store(access).load(public_name)
        return self._project_local_query_routes(
            self._active_store.load(public_name)
        )

    def load(self, public_name: str, _loading=frozenset()) -> Context:
        context = self.load_without_attached_reads(public_name)
        if self.access_for(public_name).is_granted:
            return context
        return self._project_local_attached_reads(
            context,
            loading=_loading | {public_name},
        )


def freeze_readable_context_catalog(
    active_store: MemoryStore,
    root_access: ContextAccess,
    *,
    include_query_routes: bool = True,
) -> ReadableContextCatalog:
    """Freeze one command's unified public namespace and exact read bindings."""

    return ReadableContextCatalog(
        active_store,
        root_access,
        include_query_routes=include_query_routes,
    )


def freeze_profile_readable_context_catalog(
    active_store: MemoryStore,
    selected_access: ContextAccess,
    *,
    include_query_routes: bool = True,
    registry: ProfileRegistry | None = None,
) -> ReadableContextCatalog:
    """Freeze all readable Profile names without losing granted orientation.

    A selected granted view identifies the initial row, not the namespace
    boundary of a control explicitly labelled PROFILE.  Anchor discovery at
    the grant's local attachment so ordinary local names and every valid READ
    grant share the same frozen public hierarchy.
    """

    root_access = selected_access
    if selected_access.is_granted:
        if selected_access.attachment_name is None or selected_access.view is None:
            raise ProfileError("Granted readable Context has no local attachment.")
        attachment_name = selected_access.attachment_name
        attachment = active_store.load_direct(attachment_name)
        if attachment.uid != selected_access.view.grant.attachment_context_uid:
            raise ProfileError("Granted readable Context attachment changed.")
        root_access = ContextAccess(
            store=active_store,
            context_name=attachment_name,
            display_name=attachment_name,
            attachment_name=None,
            permission="READ",
        )

    catalog = ReadableContextCatalog(
        active_store,
        root_access,
        registry=registry,
        include_query_routes=include_query_routes,
    )
    if not catalog.context_exists(selected_access.display_name):
        raise ProfileError("Selected readable Context left the frozen Profile view.")
    if selected_access.is_granted:
        frozen_access = catalog.access_for(selected_access.display_name)
        if (
            not frozen_access.is_granted
            or frozen_access.view is None
            or frozen_access.view.grant != selected_access.view.grant
        ):
            raise ProfileError("Selected readable Context grant changed.")
    return catalog


def freeze_profile_context_navigation(
    active_store: MemoryStore,
    selected_access: ContextAccess,
    *,
    granted_navigation: GrantedContextNavigation | None = None,
) -> ProfileContextNavigation:
    """Freeze the same Profile breadth and authority rows used by Switch.

    The selected access fixes only the initial readable row. It must never
    become an accidental namespace root for controls labelled PROFILE or ALL
    READABLE CONTEXTS. QUERY-only Grant routes remain visible orientation rows
    but stay outside the materialized, loadable subset.
    """

    catalog = freeze_profile_readable_context_catalog(
        active_store,
        selected_access,
        include_query_routes=False,
    )
    readable_names = tuple(catalog.list_context_names())
    local_names = tuple(
        name for name in readable_names if not catalog.access_for(name).is_granted
    )
    readable_virtual_names = frozenset(
        name for name in readable_names if catalog.access_for(name).is_granted
    )
    grants = granted_navigation or freeze_granted_context_navigation(active_store)
    virtual_names = tuple(
        sorted((set(grants.names) | set(readable_virtual_names)) - set(local_names))
    )
    missing_annotations = set(virtual_names) - set(grants.annotations)
    if missing_annotations:
        raise ProfileError("Granted Profile navigation annotations are incomplete.")
    selectable_virtual_names = readable_virtual_names & frozenset(virtual_names)
    if selected_access.display_name not in (
        set(local_names) | set(selectable_virtual_names)
    ):
        raise ProfileError("Selected readable Context left Profile navigation.")
    return ProfileContextNavigation(
        catalog=catalog,
        local_names=local_names,
        virtual_names=virtual_names,
        selectable_virtual_names=selectable_virtual_names,
        virtual_annotations={
            name: grants.annotations[name] for name in virtual_names
        },
    )
