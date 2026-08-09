"""Process-local tree navigation over a frozen Context-name catalog."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import AbstractSet


@dataclass(frozen=True)
class ContextTreeRow:
    """One currently visible catalog Context."""

    name: str
    depth: int
    has_children: bool
    expanded: bool
    materialized: bool


@dataclass(frozen=True)
class ContextTree:
    """Read-only tree derived only from the picker catalog snapshot."""

    roots: tuple[str, ...]
    children_by_name: dict[str, tuple[str, ...]]
    parent_by_name: dict[str, str | None]
    materialized_names: frozenset[str]

    @property
    def expandable_names(self) -> frozenset[str]:
        return frozenset(
            name for name, children in self.children_by_name.items() if children
        )


def build_context_tree(
    options: Sequence[str],
    *,
    materialized_names: AbstractSet[str] | None = None,
) -> ContextTree:
    """Arrange only catalog Contexts below their nearest real catalog parent."""

    materialized = frozenset(
        options if materialized_names is None else materialized_names
    )
    if not materialized.issubset(options):
        raise ValueError("Materialized Context names must be in the picker catalog.")
    ordered_names = tuple(dict.fromkeys(options))
    option_set = frozenset(ordered_names)
    parent_by_name: dict[str, str | None] = {}
    children: dict[str | None, list[str]] = {None: []}
    for name in ordered_names:
        segments = name.split("/")
        parent = next(
            (
                "/".join(segments[:length])
                for length in range(len(segments) - 1, 0, -1)
                if "/".join(segments[:length]) in option_set
            ),
            None,
        )
        parent_by_name[name] = parent
        children.setdefault(parent, []).append(name)
        children.setdefault(name, [])
    # A missing prefix is not a Context and therefore receives no synthetic
    # navigation row. Callers that need a grouping parent must persist an
    # ordinary zero-Memory Context and include it in the frozen catalog.
    return ContextTree(
        roots=tuple(children[None]),
        children_by_name={name: tuple(children[name]) for name in ordered_names},
        parent_by_name=parent_by_name,
        materialized_names=materialized,
    )


def context_ancestors(tree: ContextTree, name: str) -> set[str]:
    """Return lexical tree ancestors from parent to root."""

    ancestors: set[str] = set()
    parent = tree.parent_by_name.get(name)
    while parent is not None:
        ancestors.add(parent)
        parent = tree.parent_by_name[parent]
    return ancestors


def expandable_context_subtree(tree: ContextTree, name: str) -> set[str]:
    """Return every expandable branch at or below one selected tree node."""

    expandable: set[str] = set()
    pending = [name]
    while pending:
        candidate = pending.pop()
        children = tree.children_by_name[candidate]
        if not children:
            continue
        expandable.add(candidate)
        pending.extend(children)
    return expandable


def visible_context_rows(
    tree: ContextTree,
    expanded: AbstractSet[str],
) -> tuple[ContextTreeRow, ...]:
    """Project process-local expansion state into depth-first visible rows."""

    rows: list[ContextTreeRow] = []
    pending = [(name, 0) for name in reversed(tree.roots)]
    while pending:
        name, depth = pending.pop()
        children = tree.children_by_name[name]
        is_expanded = bool(children) and name in expanded
        rows.append(
            ContextTreeRow(
                name=name,
                depth=depth,
                has_children=bool(children),
                expanded=is_expanded,
                materialized=name in tree.materialized_names,
            )
        )
        if is_expanded:
            pending.extend((child, depth + 1) for child in reversed(children))
    return tuple(rows)


@dataclass
class ContextTreeState:
    """Embeddable process-local navigation over one frozen Context catalog."""

    tree: ContextTree
    selected_name: str
    expanded: set[str] = field(default_factory=set)
    all_expanded: bool = False
    show_memories: bool = False
    memory_visibility_overrides: dict[str, bool] = field(default_factory=dict)
    _before_expand_all: set[str] = field(default_factory=set, repr=False)

    @classmethod
    def create(cls, tree: ContextTree, *, selected: str) -> "ContextTreeState":
        if selected not in tree.parent_by_name:
            raise ValueError("Selected Context is not in the picker catalog.")
        expanded = context_ancestors(tree, selected)
        return cls(
            tree=tree,
            selected_name=selected,
            expanded=expanded,
            _before_expand_all=set(expanded),
        )

    def visible_rows(self) -> tuple[ContextTreeRow, ...]:
        return visible_context_rows(self.tree, self.expanded)

    def selected_row_index(self) -> int:
        return next(
            index
            for index, row in enumerate(self.visible_rows())
            if row.name == self.selected_name
        )

    def move(self, delta: int) -> None:
        rows = self.visible_rows()
        index = self.selected_row_index()
        next_index = max(0, min(index + delta, len(rows) - 1))
        self.selected_name = rows[next_index].name

    def _enter_manual_expansion(self) -> None:
        if self.all_expanded:
            self.all_expanded = False
            self._before_expand_all = set(self.expanded)

    def _expandable_levels(self, root: str) -> dict[int, set[str]]:
        """Group expandable nodes by depth below one selected anchor."""

        levels: dict[int, set[str]] = {}
        pending = [(root, 0)]
        while pending:
            name, depth = pending.pop()
            children = self.tree.children_by_name[name]
            if not children:
                continue
            levels.setdefault(depth, set()).add(name)
            pending.extend((child, depth + 1) for child in children)
        return levels

    def expand_selected(self, *, include_leaf_memories: bool = False) -> None:
        """Reveal one more descendant depth or a leaf's Memory layer."""

        name = self.selected_name
        children = self.tree.children_by_name[name]
        levels = self._expandable_levels(name)
        collapsed_by_depth = {
            depth: names - self.expanded
            for depth, names in levels.items()
            if names - self.expanded
        }
        if collapsed_by_depth:
            self._enter_manual_expansion()
            self.expanded.update(collapsed_by_depth[min(collapsed_by_depth)])
        elif children:
            self.selected_name = children[0]
        elif include_leaf_memories and name in self.tree.materialized_names:
            # A materialized leaf still has one presentational layer: its
            # direct Memories. Treating that layer as expandable keeps the
            # glyph and arrow-key behavior consistent with what ``m`` shows.
            self.memory_visibility_overrides[name] = True

    def collapse_selected(self, *, include_leaf_memories: bool = False) -> None:
        """Hide the deepest descendant depth or a leaf's Memory layer."""

        name = self.selected_name
        if (
            include_leaf_memories
            and not self.tree.children_by_name[name]
            and name in self.tree.materialized_names
            and self.memories_visible_for(name)
        ):
            self.memory_visibility_overrides[name] = False
            return
        expanded_by_depth = {
            depth: names & self.expanded
            for depth, names in self._expandable_levels(name).items()
            if names & self.expanded
        }
        if expanded_by_depth:
            self._enter_manual_expansion()
            self.expanded.difference_update(expanded_by_depth[max(expanded_by_depth)])
            return
        parent = self.tree.parent_by_name[name]
        if parent is not None:
            self.selected_name = parent

    def toggle_expand_all(self) -> None:
        if self.all_expanded:
            restored = set(self._before_expand_all)
            # A row first reached while fully expanded must remain visible.
            restored.update(context_ancestors(self.tree, self.selected_name))
            self.expanded.clear()
            self.expanded.update(restored)
            self.all_expanded = False
            return
        self._before_expand_all = set(self.expanded)
        self.expanded.update(self.tree.expandable_names)
        self.all_expanded = True

    def toggle_memories(self) -> None:
        """Show or hide every Memory projection as one fresh global state."""

        self.show_memories = not self.show_memories
        self.memory_visibility_overrides.clear()

    def memories_visible_for(self, name: str) -> bool:
        """Return effective Memory visibility for one Context node."""

        return self.memory_visibility_overrides.get(name, self.show_memories)

    def toggle_selected_memories(self) -> None:
        """Toggle only the selected Context against the current global state."""

        name = self.selected_name
        self.memory_visibility_overrides[name] = not self.memories_visible_for(name)
