"""Compose a readable Merge Source picker without opening Memory content."""

from __future__ import annotations

from memcommit.authority.access import resolve_context_access
from memcommit.context_targeting.readable_catalog import (
    freeze_profile_context_navigation,
)
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
    # ALL READABLE CONTEXTS is Profile-wide. A granted current Target is only
    # orientation, so anchor discovery at its local attachment and retain each
    # Source name's exact frozen READ binding through the common catalog.
    orientation_name = (
        target.attachment_name if target.is_granted else target.display_name
    )
    orientation = resolve_context_access(
        port.store,
        orientation_name,
        current_name=port.current_context_name,
        required_permission="READ",
    )
    navigation = freeze_profile_context_navigation(port.store, orientation)
    names = tuple(
        sorted(
            (*navigation.local_names, *navigation.selectable_virtual_names),
            key=str.casefold,
        )
    )
    selectable = set(names) - {target.display_name}
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
            (name, navigation.virtual_annotations[name])
            for name in names
            if name in navigation.virtual_annotations
        ),
    )
