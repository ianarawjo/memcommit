"""Unify readable Contexts into one Store-like namespace."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.application.context_access.granted_view import (
    active_grant_placements,
)
from memcommit.core.context import Context, QueryContextRef
from memcommit.application.context_access.granted_context_navigation import (
    GrantedContextNavigation,
    freeze_granted_context_navigation,
)
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.operations.profile.config import (
    AuthorityGrant,
    GrantPlacement,
    ProfileConfigError,
    ProfileRegistry,
    default_store_dir,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.source_projection.presentation import SourceDisplayValue
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class ReadableContextBinding:
    """Bind one access name to the exact store-authority used to read it."""

    access_name: str
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
        """Return every visible access name in deterministic tree order."""

        return tuple(sorted((*self.local_names, *self.virtual_names)))


class ReadableContextCatalog:
    """Expose local and READ-granted Contexts through one access-name catalog.

    Namespace membership comes from canonical local and Grant access names.
    A Placement supplies naming only and is not an authority hierarchy edge.
    """

    def __init__(
        self,
        active_store: MemoryStore,
        root_access: ContextAccess,
        *,
        registry: ProfileRegistry | None = None,
        include_query_routes: bool = True,
        profile_wide: bool = False,
    ) -> None:
        self._active_store = active_store
        self._root_access = root_access
        self._include_query_routes = include_query_routes
        self._granted_stores: dict[str, GrantedReadStore] = {}
        self._bindings: dict[str, ReadableContextBinding] = {}
        self._query_routes_by_parent: dict[str, tuple[QueryContextRef, ...]] = {}

        if root_access.is_granted and not profile_wide:
            granted = GrantedReadStore(root_access, registry=registry)
            self._granted_stores[root_access.access_name] = granted
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
                    access_name=name,
                    permission="READ",
                ),
            )

        registry = self._active_registry(registry)
        if registry is not None:
            valid_grants = tuple(self._valid_active_grants(registry))
            self._add_granted_bindings(registry, valid_grants)
            if include_query_routes:
                self._freeze_query_routes(registry, valid_grants)
        self._names = tuple(sorted(self._bindings))

    def _active_registry(
        self,
        registry: ProfileRegistry | None,
    ) -> ProfileRegistry | None:
        try:
            value = registry or load_profile_registry()
        except ProfileConfigError:
            if self._active_store.store_dir.resolve() != default_store_dir().resolve():
                return None
            raise
        # An isolated or explicitly rooted MemoryStore must never inherit the
        # host Profile's virtual grants merely because a registry is present.
        if (
            self._active_store.store_dir.resolve()
            != profile_store_dir(value.active).resolve()
        ):
            return None
        return value

    def _valid_active_grants(self, registry: ProfileRegistry):
        yield from active_grant_placements(registry=registry)

    def _add_granted_bindings(
        self,
        registry: ProfileRegistry,
        grants: Sequence[tuple[GrantPlacement, AuthorityGrant]],
    ) -> None:
        candidate_names: set[str] = set()
        for placement, grant in grants:
            for binding in grant.contexts:
                suffix = binding.name[len(grant.resource_name) :]
                candidate_names.add(placement.access_name + suffix)

        for access_name in sorted(candidate_names):
            try:
                access = resolve_context_access(
                    self._active_store,
                    access_name,
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
            self._bindings[access_name] = ReadableContextBinding(
                access_name,
                access,
            )

    def _freeze_query_routes(
        self,
        registry: ProfileRegistry,
        grants: Sequence[tuple[GrantPlacement, AuthorityGrant]],
    ) -> None:
        by_parent: dict[str, list[QueryContextRef]] = {}
        seen_names: set[str] = set()
        for placement, grant in grants:
            access_name = placement.access_name
            if access_name in seen_names:
                continue
            try:
                resolve_context_access(
                    self._active_store,
                    access_name,
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
                    access_name,
                    current_name=self._root_access.context_name,
                    required_permission="QUERY",
                    registry=registry,
                )
            except (FileNotFoundError, ProfileError):
                continue
            parent, separator, _ = access_name.rpartition("/")
            if not separator or parent not in self._bindings:
                continue
            seen_names.add(access_name)
            by_parent.setdefault(parent, []).append(
                QueryContextRef(
                    uid=query_access.view.grant.uid,
                    name=access_name,
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

    def context_exists(self, access_name: str) -> bool:
        return access_name in self._bindings

    def access_for(self, access_name: str) -> ContextAccess:
        """Return the exact ownership/authority binding for one access name."""

        binding = self._bindings.get(access_name)
        if binding is None:
            raise FileNotFoundError(f"Context '{access_name}' is outside the view.")
        return binding.access

    def granted_names_below(self, root_name: str) -> tuple[str, ...]:
        """Return readable granted names in the root's access namespace."""

        scope = ContextScope.create((root_name,), include_descendants=True)
        return tuple(
            name
            for name in expand_lexical_context_names(scope, self._names)[1:]
            if self._bindings[name].access.is_granted
        )

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

    def load_direct(self, access_name: str) -> Context:
        binding = self._bindings.get(access_name)
        if binding is None:
            raise FileNotFoundError(f"Context '{access_name}' is outside the view.")
        access = binding.access
        if access.is_granted:
            return self._granted_store(access).load_direct(access_name)
        return self._project_local_query_routes(
            self._active_store.load_direct(access_name)
        )

    def load_without_attached_reads(self, access_name: str) -> Context:
        """Resolve persisted refs while excluding process-local READ sources."""

        binding = self._bindings.get(access_name)
        if binding is None:
            raise FileNotFoundError(f"Context '{access_name}' is outside the view.")
        access = binding.access
        if access.is_granted:
            return self._granted_store(access).load(access_name)
        return self._project_local_query_routes(self._active_store.load(access_name))

    def load(self, access_name: str, _loading=frozenset()) -> Context:
        return self.load_without_attached_reads(access_name)


def freeze_readable_context_catalog(
    active_store: MemoryStore,
    root_access: ContextAccess,
    *,
    include_query_routes: bool = True,
) -> ReadableContextCatalog:
    """Freeze one command's unified access namespace and exact read bindings."""

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
    boundary of a control explicitly labelled PROFILE. Ordinary local names
    and every valid READ placement share the same frozen access hierarchy.
    """

    catalog = ReadableContextCatalog(
        active_store,
        selected_access,
        registry=registry,
        include_query_routes=include_query_routes,
        profile_wide=True,
    )
    if not catalog.context_exists(selected_access.access_name):
        raise ProfileError("Selected readable Context left the frozen Profile view.")
    if selected_access.is_granted:
        frozen_access = catalog.access_for(selected_access.access_name)
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
    if selected_access.access_name not in (
        set(local_names) | set(selectable_virtual_names)
    ):
        raise ProfileError("Selected readable Context left Profile navigation.")
    return ProfileContextNavigation(
        catalog=catalog,
        local_names=local_names,
        virtual_names=virtual_names,
        selectable_virtual_names=selectable_virtual_names,
        virtual_annotations={name: grants.annotations[name] for name in virtual_names},
    )
