"""Frozen Merge endpoint choices and request validation, independent of the console."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_context_navigation,
)
from memcommit.application.operations.merge.inputs import (
    MergeMethod,
    MergeRequest,
)
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.presentation import SourceDisplayValue


def merge_target_permission(method: MergeMethod) -> str:
    """Authority needed to select a Target; Apply checks the reviewed effects."""
    if method not in {"SEMANTIC", "LITERAL"}:
        raise ValueError("Unknown Merge method.")
    return "CREATE" if method == "LITERAL" else "READ"


@dataclass(frozen=True)
class MergeSetup:
    """Frozen endpoints; Semantic Target mutation authority follows reviewed effects."""

    names: tuple[str, ...]
    selectable_names: frozenset[str]
    selected_source: str
    target_names: tuple[str, ...]
    target_selectable_names: frozenset[str]
    target_context: str
    method: MergeMethod = "SEMANTIC"
    local_names: frozenset[str] = frozenset()
    create_target_names: frozenset[str] = frozenset()
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    target_annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Merge setup requires a distinct visible catalog.")
        if not self.selectable_names or not self.selectable_names <= set(self.names):
            raise ValueError("Merge setup requires one readable Source.")
        if self.selected_source not in self.selectable_names:
            raise ValueError("Initial Merge Source is unavailable.")
        if (
            not self.target_names
            or len(set(self.target_names)) != len(self.target_names)
            or any(not isinstance(name, str) or not name for name in self.target_names)
        ):
            raise ValueError("Merge setup requires a distinct Target catalog.")
        if not self.target_selectable_names or not self.target_selectable_names <= set(
            self.target_names
        ):
            raise ValueError("Merge setup requires one available Target.")
        if self.target_context not in self.target_selectable_names:
            raise ValueError("Initial Merge Target is unavailable.")
        merge_target_permission(self.method)
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Merge setup annotations are outside the catalog.")
        target_labels = dict(self.target_annotations)
        if len(target_labels) != len(self.target_annotations) or set(
            target_labels
        ) - set(self.target_names):
            raise ValueError("Merge setup Target annotations are outside the catalog.")

    def request(
        self,
        source: str,
        target: str,
        *,
        method: MergeMethod,
        literal_only: bool = False,
    ) -> MergeRequest:
        """Validate a selection against this frozen catalog without opening content."""
        request = MergeRequest(source, target, method)
        if source not in self.selectable_names:
            raise ValueError("Merge requires READ access to the Source.")
        if method == "SEMANTIC":
            if literal_only:
                raise ValueError(
                    "Bulk conflict options require Literal. Select Literal to continue."
                )
            if target not in self.selectable_names:
                raise ValueError("Semantic Merge requires READ access to the Target.")
        elif target not in self.local_names | self.create_target_names:
            raise ValueError("Literal Merge requires CREATE access to the Target.")
        return request


def build_merge_setup(
    store: MemoryStore,
    *,
    current_name: str | None,
    method: MergeMethod = "SEMANTIC",
    requested_target: str | None = None,
) -> MergeSetup:
    """Freeze readable Sources and the union of each method's Target choices."""

    # With no current Context, an existing local Context can orient the form.
    # Do not require CREATE on a READ-only current Context just to browse.
    if requested_target is None:
        local_names = tuple(store.list_context_names())
        requested_target = (
            current_name
            if current_name in local_names
            else next(iter(local_names), current_name)
        )
    target = resolve_existing_context_access(
        store,
        requested_target,
        current_name=current_name,
        required_permission=merge_target_permission(method),
    ).value
    # ALL READABLE CONTEXTS is Profile-wide. The selected Target fixes only
    # initial orientation; a Grant Placement has no local attachment object.
    navigation = freeze_profile_context_navigation(store, target)
    source_names = tuple(
        sorted(
            (*navigation.local_names, *navigation.selectable_virtual_names),
            key=str.casefold,
        )
    )
    source_selectable = set(source_names)
    # Semantic needs READ to inspect the baseline, then authorizes exact effects
    # before Apply. Literal retains CREATE at entry, including after a mode switch.
    create_targets = set(navigation.local_names)
    for name in navigation.virtual_names:
        try:
            access = resolve_context_access(
                store,
                name,
                current_name=current_name,
                required_permission="CREATE",
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            continue
        create_targets.add(access.access_name)
    target_selectable = source_selectable | create_targets
    # The explicitly resolved initial Target is authoritative even when its
    # public Grant row was reached through a non-local command-start snapshot.
    target_selectable.add(target.access_name)
    target_names = tuple(sorted(target_selectable, key=str.casefold))
    # Keep the initial draft executable when an alternate exists, but do not
    # turn Source/Target distinctness into a disabled picker row. The reviewed
    # endpoint result and runtime own that semantic rejection.
    selected = next(
        (
            name
            for name in sorted(
                source_selectable,
                key=lambda name: (name.casefold(),),
            )
            if name != target.access_name
        ),
        target.access_name,
    )
    return MergeSetup(
        names=source_names,
        selectable_names=frozenset(source_selectable),
        selected_source=selected,
        target_names=target_names,
        target_selectable_names=frozenset(target_selectable),
        target_context=target.access_name,
        method=method,
        local_names=frozenset(navigation.local_names),
        create_target_names=frozenset(create_targets),
        current_context=current_name,
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
