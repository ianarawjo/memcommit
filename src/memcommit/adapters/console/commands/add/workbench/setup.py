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

    local_names = tuple(store.list_context_names())
    granted = freeze_granted_context_navigation(store)
    names = set(local_names) | set(granted.names)
    selectable = set(local_names)
    annotations = {
        name: value
        for name, value in granted.annotations.items()
        if name not in local_names
    }

    for name in granted.names:
        if name in local_names:
            continue
        try:
            access = resolve_context_access(
                store,
                name,
                current_name=current_name,
                required_permission="CREATE",
            )
        except (FileNotFoundError, OSError, ProfileError, RuntimeError, ValueError):
            continue
        selectable.add(access.display_name)

    selected: str | None = None
    if requested_context is not None:
        access = resolve_existing_context_access(
            store,
            requested_context,
            current_name=current_name,
            required_permission="CREATE",
        ).value
        selected = access.display_name
        names.add(selected)
        selectable.add(selected)
        if access.is_granted:
            annotations[selected] = context_access_display_facts(access)
    elif current_name in selectable:
        selected = current_name
    elif selectable:
        selected = sorted(selectable, key=str.casefold)[0]

    if selected is None:
        raise ValueError(
            "Interactive Add requires a local or CREATE-granted target Context."
        )
    return AddWorkbenchSetup(
        names=tuple(sorted(names, key=str.casefold)),
        selectable_names=frozenset(selectable),
        selected_context=selected,
        current_context=current_name,
        annotations=tuple(
            (name, annotations[name])
            for name in sorted(annotations, key=str.casefold)
            if name in names
        ),
    )


__all__ = ["build_add_workbench_setup"]
