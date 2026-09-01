"""Compose Add's interactive workbench target catalog."""

from __future__ import annotations

from memcommit.application.context_access.access import (
    context_access_display_facts,
    resolve_context_access,
)
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
    current_name: str | None,
    requested_context: str | None,
) -> AddWorkbenchSetup:
    """Freeze visible Context rows and their CREATE availability."""

    local_context_names = tuple(store.list_context_names())
    granted_contexts = freeze_granted_context_navigation(store)
    granted_context_names = granted_contexts.names
    visible_context_names = set(local_context_names) | set(granted_context_names)
    selectable_context_names = set(local_context_names)
    annotations_by_context_name = {
        context_name: annotation
        for context_name, annotation in granted_contexts.annotations.items()
        if context_name not in local_context_names
    }

    for context_name in granted_context_names:
        if context_name in local_context_names:
            continue
        try:
            context_access = resolve_context_access(
                store,
                context_name,
                current_name=current_name,
                required_permission="CREATE",
            )
        except (FileNotFoundError, OSError, ProfileError, RuntimeError, ValueError):
            continue
        selectable_context_names.add(context_access.display_name)

    selected_context_name: str | None = None
    if requested_context is not None:
        context_access = resolve_existing_context_access(
            store,
            requested_context,
            current_name=current_name,
            required_permission="CREATE",
        ).value
        selected_context_name = context_access.display_name
        visible_context_names.add(selected_context_name)
        selectable_context_names.add(selected_context_name)
        if context_access.is_granted:
            annotations_by_context_name[selected_context_name] = (
                context_access_display_facts(context_access)
            )
    elif current_name in selectable_context_names:
        selected_context_name = current_name
    elif selectable_context_names:
        selected_context_name = sorted(selectable_context_names, key=str.casefold)[0]

    if selected_context_name is None:
        raise ValueError(
            "Interactive Add requires a local or CREATE-granted target Context."
        )
    return AddWorkbenchSetup(
        names=tuple(sorted(visible_context_names, key=str.casefold)),
        selectable_names=frozenset(selectable_context_names),
        selected_context=selected_context_name,
        current_context=current_name,
        annotations=tuple(
            (context_name, annotations_by_context_name[context_name])
            for context_name in sorted(annotations_by_context_name, key=str.casefold)
            if context_name in visible_context_names
        ),
    )


__all__ = ["build_add_workbench_setup"]
