"""Compose Merge Source and Target pickers without opening Memory content."""

from __future__ import annotations

from memcommit.authority.access import resolve_context_access
from memcommit.context_targeting.readable_catalog import (
    freeze_profile_context_navigation,
)
from memcommit.interfaces.tui.operations.merge.model import MergeTuiSetup
from memcommit.operations.merge.runtime import MemoryStoreMergePort


def build_merge_tui_setup(
    port: MemoryStoreMergePort,
    *,
    initial_recursive: bool,
    requested_target: str | None = None,
) -> MergeTuiSetup:
    """Freeze readable Sources and CREATE-authorized Targets for one launch."""

    target = resolve_context_access(
        port.store,
        requested_target,
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
    source_names = tuple(
        sorted(
            (*navigation.local_names, *navigation.selectable_virtual_names),
            key=str.casefold,
        )
    )
    source_selectable = set(source_names)
    # Target selection has a narrower authority contract than Source
    # selection. Resolve each visible Grant row for CREATE now so a READ-only
    # Source can never be mistaken for a writable Target by the shared picker.
    target_selectable = set(navigation.local_names)
    for name in navigation.virtual_names:
        try:
            access = resolve_context_access(
                port.store,
                name,
                current_name=port.current_context_name,
                required_permission="CREATE",
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            continue
        target_selectable.add(access.display_name)
    # The explicitly resolved initial Target is authoritative even when its
    # public Grant row was reached through a non-local command-start snapshot.
    target_selectable.add(target.display_name)
    target_names = tuple(sorted(target_selectable, key=str.casefold))
    # Keep the initial draft executable when an alternate exists, but do not
    # turn Source/Target distinctness into a disabled picker row. The reviewed
    # endpoint result and runtime own that semantic rejection.
    selected = next(
        (
            name
            for name in sorted(source_selectable, key=str.casefold)
            if name != target.display_name
        ),
        target.display_name,
    )
    return MergeTuiSetup(
        names=source_names,
        selectable_names=frozenset(source_selectable),
        selected_source=selected,
        target_names=target_names,
        target_selectable_names=frozenset(target_selectable),
        target_context=target.display_name,
        initial_recursive=initial_recursive,
        current_context=port.current_context_name,
        annotations=tuple(
            (name, navigation.virtual_annotations[name])
            for name in source_names
            if name in navigation.virtual_annotations
        ),
        target_annotations=tuple(
            (name, navigation.virtual_annotations[name])
            for name in target_names
            if name in navigation.virtual_annotations
        ),
    )
