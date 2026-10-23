"""Frozen Merge endpoint choices and request validation, independent of the console."""

from __future__ import annotations

from dataclasses import dataclass

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
        if self.method not in {"SEMANTIC", "LITERAL"}:
            raise ValueError("Unknown Merge method.")
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
            raise ValueError("Merge Source is outside the frozen local catalog.")
        if target not in self.target_selectable_names:
            raise ValueError("Merge Target is outside the frozen local catalog.")
        if method == "SEMANTIC" and literal_only:
            raise ValueError(
                "Bulk conflict options require Literal. Select Literal to continue."
            )
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
    ).value
    navigation = freeze_profile_context_navigation(store, target)
    source_names = tuple(
        navigation.catalog.list_context_names(sort_order="alphabetical")
    )
    source_selectable = set(source_names)
    target_names = source_names
    target_selectable = source_selectable
    # Keep the initial draft executable when an alternate exists, but do not
    # turn Source/Target distinctness into a disabled picker row. The reviewed
    # endpoint result and runtime own that semantic rejection.
    selected = next(
        (
            name
            for name in source_names
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
        current_context=current_name,
    )
