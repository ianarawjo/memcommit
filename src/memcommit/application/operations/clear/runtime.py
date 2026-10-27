"""Authority, plan freeze, and durable execution for Clear."""

from __future__ import annotations

import uuid

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest

from memcommit.application.context_access.readable_contexts import (
    freeze_readable_context_catalog,
)
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)
from memcommit.application.operations.clear.application import ClearRequest, ClearResult
from memcommit.persistence.store import ProfileStore


def _clear_recursive(
    active_store: ProfileStore,
    access: ContextAccess,
) -> ClearResult:
    """Clear one frozen local lexical subtree as one Undoable command unit."""

    freeze_readable_context_catalog(
        active_store,
        access,
    )

    store = access.store
    catalog_names = tuple(store.list_context_names())
    context_names = list_context_and_descendant_names(
        (access.context_name,),
        catalog_names,
    )
    frames = tuple(
        (
            context,
            len(context.memories),
        )
        for context in (store.load_direct(name) for name in context_names)
    )
    changed = tuple(frame for frame in frames if frame[1] > 0)
    if not changed:
        return ClearResult(
            context_name=access.access_name,
            recursive=True,
            item_count=0,
            scope_count=len(frames),
            changed_context_count=0,
        )

    operation_uid = str(uuid.uuid4())
    membership = [
        {"uid": context.uid, "name": context.name} for context, _count in changed
    ]
    total_count = sum(count for _context, count in changed)
    changed_count = len(changed)
    tree_receipt = {
        "version": 1,
        "operation_uid": operation_uid,
        "root": access.access_name,
        "include_descendants": True,
    }

    entries = []
    unchanged_bindings = []
    for context, count in frames:
        if count == 0:
            # Empty Contexts still belong to the selected subtree and need
            # the same identity validation as its changed members.
            unchanged_bindings.append((context.name, context.uid))
            continue
        context.clear()
        entries.append(
            (
                context,
                AutoCheckpointRequest(
                    command="clear",
                    command_details={
                        "count": count,
                        "context": context.name,
                        "recursive": True,
                        "clear_tree": tree_receipt,
                        "command_contexts": membership,
                    },
                ),
            )
        )

    store.save_context_command_batch(
        entries,
        source_bindings=unchanged_bindings,
        expected_context_catalog=catalog_names,
    )
    return ClearResult(
        context_name=access.access_name,
        recursive=True,
        item_count=total_count,
        scope_count=len(frames),
        changed_context_count=changed_count,
    )


def execute_clear(
    active_store: ProfileStore,
    request: ClearRequest,
    *,
    current_name: str | None,
) -> ClearResult:
    """Resolve, revalidate, and publish one Clear request or no change."""

    access = resolve_existing_context_access(
        active_store,
        request.context_locator,
        current_name=current_name,
    ).value
    if request.recursive:
        return _clear_recursive(active_store, access)

    store = access.store
    context = store.load_direct(access.context_name)
    count = len(context.memories)
    if count == 0:
        return ClearResult(
            context_name=access.access_name,
            recursive=False,
            item_count=0,
            scope_count=1,
            changed_context_count=0,
        )

    context.clear()
    store.save(
        context,
        AutoCheckpointRequest(
            command="clear",
            command_details={
                "count": count,
                "context": access.access_name,
            },
        ),
    )
    return ClearResult(
        context_name=access.access_name,
        recursive=False,
        item_count=count,
        scope_count=1,
        changed_context_count=1,
    )
