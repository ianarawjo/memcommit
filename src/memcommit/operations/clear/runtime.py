"""Authority, plan freeze, and durable execution for Clear."""

from __future__ import annotations

import uuid

from memcommit.authority.access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.readable_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.operations.clear.application import ClearRequest, ClearResult
from memcommit.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore, context_record_digest


def _clear_recursive(
    active_store: MemoryStore,
    access: ContextAccess,
) -> ClearResult:
    """Clear one frozen local lexical subtree as one Undoable command unit."""

    if access.is_granted:
        raise ProfileError(
            "Recursive clear cannot cross a granted Context boundary; "
            "clear granted Contexts exactly."
        )

    readable = freeze_readable_context_catalog(
        active_store,
        access,
        include_query_routes=False,
    )
    granted_descendants = readable.granted_names_below(access.display_name)
    if granted_descendants:
        raise ProfileError(
            "Recursive clear cannot cross granted Context boundaries: "
            + ", ".join(repr(name) for name in granted_descendants)
            + ". Clear those Contexts exactly."
        )

    store = access.store
    catalog_names = tuple(store.list_context_names())
    context_names = expand_lexical_context_names(
        ContextScope.create(
            (access.context_name,),
            include_descendants=True,
        ),
        catalog_names,
    )
    frames = tuple(
        (
            context,
            context_record_digest(context),
            len(context.memories),
        )
        for context in (store.load_direct(name) for name in context_names)
    )
    changed = tuple(frame for frame in frames if frame[2] > 0)
    if not changed:
        return ClearResult(
            context_name=access.display_name,
            recursive=True,
            item_count=0,
            scope_count=len(frames),
            changed_context_count=0,
        )

    operation_uid = str(uuid.uuid4())
    membership = [
        {"uid": context.uid, "name": context.name}
        for context, _digest, _count in changed
    ]
    total_count = sum(count for _context, _digest, count in changed)
    changed_count = len(changed)
    description = (
        f"Cleared {total_count} item(s) from {changed_count} Context(s) "
        f"under '{access.display_name}'"
    )
    tree_receipt = {
        "version": 1,
        "operation_uid": operation_uid,
        "root": access.display_name,
        "include_descendants": True,
    }

    entries = []
    unchanged_bindings = []
    for context, digest, count in frames:
        if count == 0:
            # Empty members remain part of the frozen subtree so a concurrent
            # add cannot escape merely because that member needs no checkpoint.
            unchanged_bindings.append((context.name, context.uid, digest))
            continue
        context.clear()
        entries.append(
            (
                context,
                AutoCheckpoint(
                    command="clear",
                    args={
                        "count": count,
                        "context": context.name,
                        "recursive": True,
                        "clear_tree": tree_receipt,
                        "command_contexts": membership,
                    },
                    description=description,
                ),
                digest,
            )
        )

    store.save_context_command_batch(
        entries,
        source_bindings=unchanged_bindings,
        expected_context_catalog=catalog_names,
    )
    return ClearResult(
        context_name=access.display_name,
        recursive=True,
        item_count=total_count,
        scope_count=len(frames),
        changed_context_count=changed_count,
    )


def execute_clear(
    active_store: MemoryStore,
    request: ClearRequest,
    *,
    current_name: str | None,
) -> ClearResult:
    """Resolve, revalidate, and publish one Clear request or no change."""

    access = resolve_context_access(
        active_store,
        request.context_locator,
        current_name=current_name,
        required_permission="DELETE",
    )
    if request.recursive:
        return _clear_recursive(active_store, access)

    store = access.store
    context = store.load_direct(access.context_name)
    count = len(context.memories)
    if count == 0:
        return ClearResult(
            context_name=access.display_name,
            recursive=False,
            item_count=0,
            scope_count=1,
            changed_context_count=0,
        )

    context.clear()
    with authorized_context_mutation(
        access,
        required_permissions=("DELETE",),
    ):
        store.save(
            context,
            AutoCheckpoint(
                command="clear",
                args={
                    "count": count,
                    "context": access.display_name,
                    **grant_checkpoint_args(access),
                },
                description=(
                    f"Cleared all {count} item(s) from '{access.display_name}'"
                ),
            ),
        )
    return ClearResult(
        context_name=access.display_name,
        recursive=False,
        item_count=count,
        scope_count=1,
        changed_context_count=1,
    )
