"""Compose Add's interactive workbench target catalog."""

from __future__ import annotations

from memcommit.application.capabilities.context_locator import (
    find_nearest_context_ancestor,
)
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.context_access.granted_context_navigation import (
    freeze_granted_context_navigation,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.adapters.console.commands.add.workbench.model import (
    AddWorkbenchSetup,
)
from memcommit.persistence.store import MemoryStore


def build_add_workbench_setup(
    store: MemoryStore,
    *,
    current_context_name: str | None,
    specified_context_locator: str | None,
) -> AddWorkbenchSetup:
    """Freeze visible Context rows and their CREATE availability."""

    # Combine local and granted Context names into one visible target catalog.
    local_context_names = tuple(store.list_context_names())
    granted_contexts = freeze_granted_context_navigation(store)
    granted_context_names = granted_contexts.names
    visible_context_names = set(local_context_names) | set(granted_context_names)

    # Local names take precedence, so annotate only grant-only rows.
    grant_annotations_by_context_name = {
        context_name: grant_annotation
        for context_name, grant_annotation in granted_contexts.annotations.items()
        if context_name not in local_context_names
    }

    # Determine which Contexts are selectable for Add: local Contexts qualify
    # by default, while granted Contexts require CREATE.
    selectable_context_names = set(local_context_names)
    for context_name in granted_context_names:
        if context_name in local_context_names:
            continue
        try:
            context_access = resolve_context_access(
                store,
                context_name,
                current_name=current_context_name,
                required_permission="CREATE",
            )
        except (FileNotFoundError, OSError, ProfileError, RuntimeError, ValueError):
            continue
        selectable_context_names.add(context_access.display_name)

    if not selectable_context_names:
        raise ValueError(
            "Interactive Add requires a local or CREATE-granted target Context."
        )

    # Choose the Context initially selected when the workbench opens.
    if specified_context_locator is not None:
        specified_context_access = resolve_existing_context_access(
            store,
            specified_context_locator,
            current_name=current_context_name,
            required_permission="CREATE",
        ).value
        selected_context_name = specified_context_access.display_name
        visible_context_names.add(selected_context_name)
        selectable_context_names.add(selected_context_name)
    elif current_context_name in selectable_context_names:
        selected_context_name = current_context_name
    elif (
        nearest_context_ancestor := find_nearest_context_ancestor(
            current_context_name,
            selectable_context_names,
        )
    ) is not None:
        selected_context_name = nearest_context_ancestor
    else:
        selected_context_name = min(
            selectable_context_names,
            key=str.casefold,
        )
    return AddWorkbenchSetup(
        names=tuple(sorted(visible_context_names, key=str.casefold)),
        selectable_names=frozenset(selectable_context_names),
        selected_context=selected_context_name,
        current_context=current_context_name,
        annotations=tuple(
            (context_name, grant_annotations_by_context_name[context_name])
            for context_name in sorted(
                grant_annotations_by_context_name,
                key=str.casefold,
            )
            if context_name in visible_context_names
        ),
    )
