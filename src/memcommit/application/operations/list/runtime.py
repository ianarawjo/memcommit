"""MemoryStore composition for the read-only List operation."""

from __future__ import annotations

from memcommit.application.context_access.access import (
    ContextAccess,
)
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
    freeze_profile_readable_context_catalog,
    freeze_readable_context_catalog,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.operations.list.application import (
    ListRequest,
    ListSelection,
    run_list,
)
from memcommit.models.context import Context
from memcommit.persistence.store import MemoryStore


def context_record_display_uids(context: Context) -> tuple[str, ...]:
    """Return compact identities exposed by one readable Context record."""

    values: list[str] = []
    visited: set[int] = set()

    def visit(current: Context) -> None:
        object_id = id(current)
        if object_id in visited:
            return
        visited.add(object_id)
        values.append(current.uid)
        for item in current.iter_memories():
            values.append(item.uid)

    visit(context)
    return tuple(values)


def readable_catalog_display_uids(
    catalog: ReadableContextCatalog,
) -> tuple[str, ...]:
    """Freeze local Context and Memory UIDs for collision-safe display."""

    values: list[str] = []
    for name in catalog.list_context_names():
        values.extend(context_record_display_uids(catalog.load_direct(name)))
    return tuple(dict.fromkeys(values))


def profile_readable_display_uids(
    active_store: MemoryStore,
    selected_access: ContextAccess,
) -> tuple[str, ...]:
    """Freeze Profile-wide display identities for collision-safe List prefixes."""

    catalog = freeze_profile_readable_context_catalog(
        active_store,
        selected_access,
    )
    return readable_catalog_display_uids(catalog)


class MemoryStoreListSource:
    """Resolve List authority and scope while keeping Store access out of CLI code."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def freeze(self, request: ListRequest) -> ListSelection:
        access = resolve_existing_context_access(
            self._store,
            request.context_locator,
            current_name=request.current_context_name,
        ).value
        readable_uids = profile_readable_display_uids(self._store, access)
        catalog = freeze_readable_context_catalog(self._store, access)
        context_names = tuple(catalog.list_context_names())
        # Direct presentation must not open attached READ sources merely to
        # display authority metadata; recursive presentation deliberately may.
        context = catalog.load_direct(access.access_name)
        return ListSelection(
            access=access,
            context=context,
            catalog=catalog,
            context_names=context_names,
            readable_uids=readable_uids,
        )



def execute_list(store: MemoryStore, request: ListRequest) -> ListSelection:
    """Execute one Store-backed List source selection."""

    return run_list(request, source=MemoryStoreListSource(store))


__all__ = [
    "MemoryStoreListSource",
    "context_record_display_uids",
    "execute_list",
    "profile_readable_display_uids",
    "readable_catalog_display_uids",
]
