"""Reusable exact direct-Memory selector composed with a Context tree."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from prompt_toolkit.application.current import get_app

from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.core.context_targeting.model import ContextSelectionMode
from memcommit.core.context_targeting.tui.memory_selection import (
    DirectMemorySelectionState,
)
from memcommit.adapters.console.terminal.components.context_picker.model import (
    ContextMemoryRow,
)
from memcommit.adapters.console.terminal.components.context_picker.preview import (
    ContextMemoryPreviewController,
)
from memcommit.core.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorRowProjection,
    ContextSelectorView,
)
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class DirectMemorySelectorView:
    """Frozen Context catalog and presentation for one Memory role."""

    names: tuple[str, ...]
    selected_context: str
    label: str
    current_context: str | None = None
    selectable_names: frozenset[str] | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    mode: ContextSelectionMode = "SINGLE"


class DirectMemorySelectorControl:
    """Keep Context navigation, Memory hover, and exact choice in one control.

    A Context row selects only the namespace location whose direct items are
    visible.  It never doubles as a Memory receipt.  Only Enter on a row with
    an exact selector updates ``selection``.
    """

    def __init__(
        self,
        view: DirectMemorySelectorView,
        *,
        memory_loader: Callable[[str], Sequence[ContextMemoryRow]],
        height: int = 8,
    ) -> None:
        self.view = view
        self.contexts = ContextSelectorControl(
            ContextSelectorView(
                names=view.names,
                selected=(view.selected_context,),
                label=view.label,
                current_context=view.current_context,
                selectable_names=view.selectable_names,
                annotations=view.annotations,
            ),
            height=height,
        )
        self.preview = ContextMemoryPreviewController(
            self.contexts.tree,
            memory_loader,
        )
        self.selection = DirectMemorySelectionState(mode=view.mode)
        self.contexts.row_projector = self._project_row
        # A direct-Memory role should expose the selected Context's item layer
        # on entry; making the person discover a separate visibility toggle
        # would turn namespace expansion into hidden operation semantics.
        self.preview.toggle_selected_memories()

    @property
    def control(self):
        return self.contexts.control

    @property
    def frame(self):
        return self.contexts.frame

    @property
    def selected(self) -> DirectMemoryTarget | None:
        return self.selection.selected

    @property
    def selected_many(self) -> tuple[DirectMemoryTarget, ...]:
        """Return checked targets in explicit check or command-edit order."""

        selected = self.selection.selected_targets
        for target in selected:
            rows = self.preview.memory_cache.get(target.context_name, ())
            if not any(row.selector == target.memory_uid for row in rows):
                raise RuntimeError("A selected direct Memory left the frozen selector.")
        return selected

    def _project_row(self, row, focused: bool) -> ContextSelectorRowProjection:
        width = max(1, get_app().output.get_size().columns - 8)
        memory_focused = (
            self.preview.memory_focused
            and self.preview.memory_anchor is not None
            and self.preview.memory_anchor[0] == row.name
        )
        return ContextSelectorRowProjection(
            branch=self.preview.branch_for(row),
            nested_fragments=self.preview.render_nested(
                row,
                wrap_width=width,
                selectable_memories=True,
                selected_memory=(
                    None if self.selection.multiple else self.selection.selected
                ),
                selected_memories=(
                    self.selection.selected_set if self.selection.multiple else None
                ),
            ),
            show_context_cursor=not (focused and memory_focused),
        )

    def move(self, delta: int) -> bool:
        return self.preview.move(delta)

    def choose_cursor(self) -> bool:
        """Select one exact Memory, or open the hovered Context's item layer."""

        if not self.preview.memory_focused:
            name = self.contexts.tree.selected_name
            self.contexts.choose_cursor()
            changed = self.selection.clear_unless_context(name)
            self.preview.toggle_selected_memories()
            return changed
        target = self.preview.focused_target()
        if target is None:
            raise ValueError("Only a directly owned ordinary Memory can be selected.")
        changed = self.selection.choose(target)
        self.contexts.selection.choose(target.context_name)
        return changed

    def resolve_target(
        self,
        context_name: str,
        selector: str,
    ) -> DirectMemoryTarget:
        """Resolve one exact/unambiguous visible Memory selector without staging it."""

        if context_name not in self.contexts.selectable:
            raise ValueError("That Source Context is unavailable for this role.")
        if not isinstance(selector, str) or not selector:
            raise ValueError("Direct Memory selector must be nonempty text.")
        rows = self.preview.memory_cache.get(context_name)
        if rows is None:
            rows = tuple(self.preview.memory_loader(context_name))
            self.preview.memory_cache[context_name] = rows
        matches = tuple(
            row.selector
            for row in rows
            if row.selector is not None and row.selector.startswith(selector)
        )
        if not matches:
            raise ValueError(
                f"No directly owned Memory matches '{selector}' in '{context_name}'."
            )
        if len(matches) > 1:
            raise ValueError(
                f"Memory selector '{selector}' is ambiguous in '{context_name}'."
            )
        return DirectMemoryTarget(context_name, matches[0])

    def select_target(self, target: DirectMemoryTarget) -> bool:
        """Stage one previously resolved target through the common selector state."""

        if not isinstance(target, DirectMemoryTarget):
            raise TypeError("Direct Memory selection requires a typed target.")
        resolved = self.resolve_target(target.context_name, target.memory_uid)
        if resolved != target:
            raise ValueError("Direct Memory target changed before it was selected.")
        self.contexts.select_name(target.context_name)
        self.contexts.tree.memory_visibility_overrides[target.context_name] = True
        rows = self.preview.memory_cache[target.context_name]
        self.preview.memory_anchor = (
            target.context_name,
            next(
                index
                for index, row in enumerate(rows)
                if row.selector == target.memory_uid
            ),
        )
        return self.selection.choose(target)

    def replace_targets(self, targets: Sequence[DirectMemoryTarget]) -> bool:
        """Resolve and atomically stage an exact set through the shared control."""

        resolved = tuple(
            self.resolve_target(target.context_name, target.memory_uid)
            for target in targets
        )
        if resolved != tuple(targets):
            raise ValueError("A direct Memory target changed before it was selected.")
        changed = self.selection.replace(resolved)
        if resolved:
            target = resolved[-1]
            self.contexts.select_name(target.context_name)
            self.contexts.tree.memory_visibility_overrides[target.context_name] = True
            rows = self.preview.memory_cache[target.context_name]
            self.preview.memory_anchor = (
                target.context_name,
                next(
                    index
                    for index, row in enumerate(rows)
                    if row.selector == target.memory_uid
                ),
            )
        return changed

    def expand(self) -> None:
        self.preview.expand_selected()

    def collapse(self) -> None:
        self.preview.collapse_selected()

    def toggle_expand_all(self) -> None:
        self.preview.toggle_expand_all()


__all__ = ["DirectMemorySelectorControl", "DirectMemorySelectorView"]
