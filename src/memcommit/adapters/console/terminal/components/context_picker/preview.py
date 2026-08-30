"""Lazy direct-item preview and viewport navigation for Context pickers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import AbstractSet

from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.tree import (
    ContextTreeRow,
    ContextTreeState,
)
from memcommit.adapters.console.terminal.components.context_picker.model import (
    ContextMemoryRow,
    ContextPickerNavigationUnit,
)
from memcommit.adapters.console.terminal.components.context_picker.rendering import (
    render_context_memory_previews,
)


@dataclass
class ContextMemoryPreviewController:
    """Share lazy Memory previews across embedded Context trees."""

    tree: ContextTreeState
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]]
    memory_cache: dict[str, tuple[ContextMemoryRow, ...]] = field(default_factory=dict)
    memory_anchor: tuple[str, int] | None = None

    def visible_memory_contexts(self) -> frozenset[str]:
        return frozenset(
            row.name
            for row in self.tree.visible_rows()
            if self.tree.memories_visible_for(row.name)
        )

    def load_visible_memories(self) -> None:
        """Load only readable, materialized rows whose previews are visible."""

        for row in self.tree.visible_rows():
            if (
                not row.materialized
                or not self.tree.memories_visible_for(row.name)
                or row.name in self.memory_cache
            ):
                continue
            try:
                self.memory_cache[row.name] = tuple(self.memory_loader(row.name))
            except (OSError, RuntimeError, ValueError):
                # Preview navigation is not an execution or authority boundary.
                # A concurrently changed row therefore fails inside this
                # read-only layer without changing the endpoint draft.
                self.memory_cache[row.name] = (
                    ContextMemoryRow("unavailable", "Memory preview changed"),
                )

    @property
    def memory_focused(self) -> bool:
        return self.memory_anchor is not None

    def _navigation_units(self) -> tuple[ContextPickerNavigationUnit, ...]:
        return context_picker_navigation_units(
            self.tree.visible_rows(),
            memories_by_context=self.memory_cache,
            visible_memory_contexts=self.visible_memory_contexts(),
        )

    def _current_navigation_unit(self) -> ContextPickerNavigationUnit:
        units = self._navigation_units()
        if self.memory_anchor is not None:
            candidate = ContextPickerNavigationUnit(
                "MEMORY",
                self.memory_anchor[0],
                self.memory_anchor[1],
            )
            if candidate in units:
                return candidate
        return ContextPickerNavigationUnit("CONTEXT", self.tree.selected_name)

    def move(self, direction: int) -> bool:
        """Move through Contexts and visible Memories; report a true boundary."""

        if direction not in {-1, 1}:
            raise ValueError("Preview navigation direction must be -1 or 1.")
        units = self._navigation_units()
        current = self._current_navigation_unit()
        index = units.index(current)
        next_index = max(0, min(index + direction, len(units) - 1))
        if next_index == index:
            return False
        target = units[next_index]
        self.tree.selected_name = target.context_name
        self.memory_anchor = (
            (target.context_name, target.memory_index)
            if target.kind == "MEMORY" and target.memory_index is not None
            else None
        )
        return True

    def clear_memory_focus(self) -> bool:
        if self.memory_anchor is None:
            return False
        self.memory_anchor = None
        return True

    def focused_target(self) -> DirectMemoryTarget | None:
        """Return an exact selectable Memory at the hover anchor, if any."""

        if self.memory_anchor is None:
            return None
        context_name, memory_index = self.memory_anchor
        memories = self.memory_cache.get(context_name, ())
        if not 0 <= memory_index < len(memories):
            return None
        selector = memories[memory_index].selector
        if selector is None:
            return None
        return DirectMemoryTarget(context_name, selector)

    def toggle_selected_memories(self) -> None:
        self.tree.toggle_selected_memories()
        self.load_visible_memories()
        if not self.tree.memories_visible_for(self.tree.selected_name):
            self.memory_anchor = None

    def toggle_all_memories(self) -> None:
        self.tree.toggle_memories()
        self.load_visible_memories()
        if not self.tree.memories_visible_for(self.tree.selected_name):
            self.memory_anchor = None

    def expand_selected(self) -> None:
        if self.memory_anchor is not None:
            return
        self.tree.expand_selected(include_leaf_memories=True)
        self.load_visible_memories()

    def collapse_selected(self) -> None:
        if self.clear_memory_focus():
            return
        self.tree.collapse_selected(include_leaf_memories=True)

    def toggle_expand_all(self) -> None:
        self.memory_anchor = None
        self.tree.toggle_expand_all()
        self.load_visible_memories()

    def branch_for(self, row: ContextTreeRow) -> str:
        memory_layer = row.materialized
        if row.expanded or (memory_layer and self.tree.memories_visible_for(row.name)):
            return "▾"
        if row.has_children or memory_layer:
            return "▸"
        return "·"

    def render_nested(
        self,
        row: ContextTreeRow,
        *,
        wrap_width: int | None,
        selectable_memories: bool = False,
        selected_memory: DirectMemoryTarget | None = None,
        selected_memories: AbstractSet[DirectMemoryTarget] | None = None,
    ) -> tuple[tuple[str, str], ...]:
        if row.name not in self.visible_memory_contexts() or not row.materialized:
            return ()
        return tuple(
            render_context_memory_previews(
                row,
                self.memory_cache.get(row.name, ()),
                wrap_width=wrap_width,
                memory_anchor=self.memory_anchor,
                selectable_memories=selectable_memories,
                selected_memory=selected_memory,
                selected_memories=selected_memories,
                show_selection_marker=selectable_memories,
            )
        )


def context_picker_navigation_units(
    rows: Sequence[ContextTreeRow],
    *,
    memories_by_context: Mapping[str, Sequence[ContextMemoryRow]] | None = None,
    show_memories: bool = False,
    visible_memory_contexts: AbstractSet[str] | None = None,
) -> tuple[ContextPickerNavigationUnit, ...]:
    """Interleave Context selection rows with read-only Memory viewport stops."""

    units: list[ContextPickerNavigationUnit] = []
    for row in rows:
        units.append(ContextPickerNavigationUnit("CONTEXT", row.name))
        memory_is_visible = (
            row.name in visible_memory_contexts
            if visible_memory_contexts is not None
            else show_memories
        )
        if not memory_is_visible or not row.materialized:
            continue
        units.extend(
            ContextPickerNavigationUnit("MEMORY", row.name, memory_index)
            for memory_index, _memory in enumerate(
                (memories_by_context or {}).get(row.name, ())
            )
        )
    return tuple(units)
