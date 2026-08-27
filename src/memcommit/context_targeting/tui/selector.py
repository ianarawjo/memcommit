"""Embeddable single- or multiple-Context selector presentation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout import Dimension, FormattedTextControl, Window
from prompt_toolkit.layout.margins import ScrollbarMargin

from memcommit.adapters.interfaces.tui.components.frame import (
    build_focused_frame,
)
from memcommit.adapters.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.context_targeting.model import ContextSelectionMode
from memcommit.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.context_targeting.tui.selection import ContextSelectionState
from memcommit.context_targeting.tui.tree import (
    ContextTreeState,
    build_context_tree,
    context_ancestors,
)
from memcommit.context_targeting.tui.tree import ContextTreeRow
from memcommit.adapters.interfaces.console.selection.tui import tree_choice_marker, tree_choice_styles
from memcommit.source_projection.model import SourceDisplayFacts, SourceState
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    combine_source_display_tokens,
    normalize_source_display_tokens,
)


@dataclass(frozen=True)
class ContextSelectorView:
    """Caller-owned catalog and labels for one common Context selector."""

    names: tuple[str, ...]
    selected: tuple[str, ...]
    mode: ContextSelectionMode = "SINGLE"
    label: str = "CONTEXT"
    current_context: str | None = None
    selectable_names: frozenset[str] | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Context selector requires a distinct nonempty catalog.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Context selector label must be nonempty text.")
        selectable = self.selectable
        if not selectable <= set(self.names):
            raise ValueError("Selectable Context names are outside the catalog.")
        if any(name not in selectable for name in self.selected):
            raise ValueError("Initial Context selection is unavailable.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Context selector annotations are invalid.")
        try:
            for annotation in labels.values():
                normalize_source_display_tokens(annotation)
        except (TypeError, ValueError) as error:
            raise ValueError("Context selector annotations are invalid.") from error

    @property
    def selectable(self) -> frozenset[str]:
        return (
            frozenset(self.names)
            if self.selectable_names is None
            else self.selectable_names
        )


@dataclass(frozen=True)
class ContextSelectorRowProjection:
    """Optional nested presentation composed into one common Context row."""

    branch: str | None = None
    nested_fragments: tuple[tuple[str, str], ...] = ()
    show_context_cursor: bool = True


class ContextSelectorControl:
    """Common framed Context tree with independent cursor and checked state."""

    def __init__(
        self,
        view: ContextSelectorView,
        *,
        height: int = 5,
        row_projector: Callable[
            [ContextTreeRow, bool], ContextSelectorRowProjection
        ]
        | None = None,
    ) -> None:
        if height < 1:
            raise ValueError("Context selector height must be positive.")
        self.view = view
        self.selectable = view.selectable
        self.annotations: Mapping[str, SourceDisplayValue] = dict(view.annotations)
        self.row_projector = row_projector
        tree = build_context_tree(view.names, materialized_names=self.selectable)
        initial_cursor = view.selected[-1] if view.selected else view.names[0]
        self.tree = ContextTreeState.create(tree, selected=initial_cursor)
        self.selection = ContextSelectionState.create(
            view.names,
            selected=view.selected,
            mode=view.mode,
        )
        self.control = FormattedTextControl(
            self._render,
            focusable=True,
            show_cursor=False,
        )
        self.frame = build_focused_frame(
            Window(
                self.control,
                wrap_lines=False,
                right_margins=[ScrollbarMargin(display_arrows=True)],
            ),
            title=safe_terminal_text(view.label),
            is_focused=lambda: get_app().layout.has_focus(self.control),
            height=Dimension.exact(height + 2),
        )

    def _render(self) -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(self.control)

        def decorate(row, cursor: bool) -> ContextTreeRowDecoration:
            projection = (
                self.row_projector(row, focused)
                if self.row_projector is not None
                else ContextSelectorRowProjection()
            )
            available = row.name in self.selectable
            selected = row.name in self.selection.selected_set
            annotation: SourceDisplayValue | None = self.annotations.get(row.name)
            if not available:
                annotation = combine_source_display_tokens(
                    annotation,
                    SourceDisplayFacts(states=(SourceState.UNAVAILABLE,)),
                )
            cursor_style, value_style = tree_choice_styles(
                cursor=cursor and projection.show_context_cursor,
                selected=selected,
                focused=focused,
            )
            return ContextTreeRowDecoration(
                marker=tree_choice_marker(selected=selected, available=available),
                active="*" if row.name == self.view.current_context else " ",
                annotation=annotation,
                cursor_style=cursor_style,
                value_style=value_style,
                branch=projection.branch,
                nested_fragments=projection.nested_fragments,
                anchor_cursor=projection.show_context_cursor,
                show_cursor=projection.show_context_cursor,
            )

        return render_context_tree_rows(self.tree, decorate)

    def move(self, delta: int) -> None:
        self.tree.move(delta)

    def expand(self) -> None:
        self.tree.expand_selected()

    def collapse(self) -> None:
        self.tree.collapse_selected()

    def toggle_expand_all(self) -> None:
        self.tree.toggle_expand_all()

    def choose_cursor(self, *, group: Sequence[str] | None = None) -> bool:
        name = self.tree.selected_name
        if name not in self.selectable:
            raise ValueError("That Context is unavailable for this role.")
        if group is None:
            return self.selection.choose(name)
        return self.selection.toggle_group(group, anchor_name=name)

    def select_name(self, name: str) -> bool:
        """Stage one exact catalog name and reveal its lexical tree row.

        Command-form synchronization uses the same checked-selection state as
        keyboard interaction.  Revealing ancestors is presentation-only and
        does not widen the selected or authorized namespace.
        """

        if name not in self.selectable:
            raise ValueError("That Context is unavailable for this role.")
        self.tree.expanded.update(context_ancestors(self.tree.tree, name))
        self.tree.selected_name = name
        return self.selection.replace((name,))
