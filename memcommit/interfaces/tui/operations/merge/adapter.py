"""Compose a readable Merge Source picker without opening Memory content."""

from __future__ import annotations

from memcommit.authority.access import resolve_context_access
from memcommit.context_targeting.catalog import freeze_granted_context_navigation
from memcommit.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.merge_runtime import MemoryStoreMergePort


def build_merge_tui_setup(
    port: MemoryStoreMergePort,
    *,
    initial_recursive: bool,
) -> MergeTuiSetup:
    """Freeze local and READ-granted public names for one TUI launch."""

    target = resolve_context_access(
        port.store,
        None,
        current_name=port.current_context_name,
        required_permission="CREATE",
    )
    local_names = tuple(port.store.list_context_names())
    navigation = freeze_granted_context_navigation(port.store)
    names = tuple(sorted(set(local_names) | set(navigation.names), key=str.casefold))
    selectable = (set(local_names) | set(navigation.readable_names)) - {
        target.display_name
    }
    if not selectable:
        raise ValueError(
            "Interactive Merge requires a readable Source distinct from its Target."
        )
    selected = sorted(selectable, key=str.casefold)[0]
    return MergeTuiSetup(
        names=names,
        selectable_names=frozenset(selectable),
        selected_source=selected,
        target_context=target.display_name,
        initial_recursive=initial_recursive,
        current_context=port.current_context_name,
        annotations=tuple(
            (name, navigation.annotations[name])
            for name in navigation.names
            if name in names
        ),
    )
