"""Shared presentation contract for exact local materialization locations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.context_targeting.tui.selection import ContextSelectionState
from memcommit.context_targeting.tui.tree import (
    ContextTreeState,
    build_context_tree,
)
from memcommit.selection.tui import tree_choice_marker, tree_choice_styles
from memcommit.commands.tui_primitives import (
    boxed_lines,
    display_escape_text,
    focused_control_style,
    safe_terminal_text,
)
from memcommit.commands.tui_text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
)


@dataclass(frozen=True)
class SaveLocationView:
    """One exact operation-owned location that remains editable before Apply."""

    value: str
    label: str = "SAVE LOCATION"
    state: str = ""
    detail: str = "Enter to change this exact local Context name."
    validate: Callable[[str], None] | None = None
    context_names: tuple[str, ...] = ()
    current_context: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.value, "Save location"),
            (self.label, "Save-location label"),
            (self.detail, "Save-location detail"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")
        if any(character in self.value for character in "\r\n"):
            raise ValueError("Save location must stay on one line.")
        if any(character in self.label for character in "\r\n"):
            raise ValueError("Save-location label must stay on one line.")
        if not isinstance(self.state, str) or any(
            character in self.state for character in "\r\n"
        ):
            raise ValueError("Save-location state must be one-line text.")
        if self.validate is not None and not callable(self.validate):
            raise TypeError("Save-location validation must be callable.")
        if not isinstance(self.context_names, tuple) or any(
            not isinstance(name, str)
            or not name
            or any(character in name for character in "\r\n")
            for name in self.context_names
        ):
            raise ValueError("Save-location Context names must be distinct lines.")
        if len(set(self.context_names)) != len(self.context_names):
            raise ValueError("Save-location Context names must be distinct lines.")
        if self.current_context is not None and (
            not isinstance(self.current_context, str)
            or not self.current_context
            or any(character in self.current_context for character in "\r\n")
        ):
            raise ValueError("Current Context must be one nonempty line.")

    def validate_value(self, value: str) -> str:
        """Validate an exact edited name without deciding how it is persisted."""

        if not isinstance(value, str) or not value.strip():
            raise ValueError("Save location must be nonempty text.")
        if any(character in value for character in "\r\n"):
            raise ValueError("Save location must stay on one line.")
        if self.validate is not None:
            self.validate(value)
        return value


@dataclass
class SaveLocationEditorState:
    """Process-local parent selection composed from shared Context controls."""

    tree: ContextTreeState
    selection: ContextSelectionState
    current_context: str | None = None

    @classmethod
    def create(cls, view: SaveLocationView) -> "SaveLocationEditorState | None":
        """Create a browser when the operation supplied a frozen local catalog."""

        if not view.context_names:
            return None
        selected = _initial_parent_context(view)
        tree = build_context_tree(view.context_names)
        return cls(
            tree=ContextTreeState.create(tree, selected=selected),
            selection=ContextSelectionState.create(
                view.context_names,
                selected=(selected,),
            ),
            current_context=view.current_context,
        )

    @property
    def selected_parent(self) -> str:
        return self.selection.selected_name

    def choose_cursor_as_parent(self, exact_value: str) -> str:
        """Select the cursor row and re-parent the exact value's final segment."""

        value = exact_value.strip()
        if not value:
            raise ValueError("Save location must be nonempty text.")
        leaf = value.rsplit("/", 1)[-1]
        if not leaf:
            raise ValueError("Save location must end with an exact Context name.")
        parent = self.tree.selected_name
        self.selection.choose(parent)
        # Selecting the exact existing row is a no-op. This matters for a
        # symmetric Meld whose current target is itself present in the catalog.
        if parent == value:
            return value
        return f"{parent}/{leaf}"


def _initial_parent_context(view: SaveLocationView) -> str:
    """Prefer the nearest real ancestor without inventing namespace rows."""

    ancestors = tuple(
        name for name in view.context_names if view.value.startswith(name + "/")
    )
    if ancestors:
        return max(ancestors, key=lambda name: (name.count("/"), len(name)))
    if view.current_context in view.context_names:
        assert view.current_context is not None
        return view.current_context
    if view.value in view.context_names:
        return view.value
    return view.context_names[0]


def save_location_tree_fragments(
    state: SaveLocationEditorState,
    *,
    focused: bool,
) -> list[tuple[str, str]]:
    """Render parent choice through the common Context-tree row grammar."""

    def decorate(row, cursor: bool) -> ContextTreeRowDecoration:
        selected = row.name == state.selected_parent
        cursor_style, value_style = tree_choice_styles(
            cursor=cursor,
            selected=selected,
            focused=focused,
        )
        return ContextTreeRowDecoration(
            marker=tree_choice_marker(selected=selected),
            active="*" if row.name == state.current_context else " ",
            cursor_style=cursor_style,
            value_style=value_style,
        )

    return render_context_tree_rows(state.tree, decorate)


def save_location_row_fragments(
    view: SaveLocationView,
    *,
    focused: bool,
    content_width: int,
) -> list[tuple[str, str]]:
    """Render the compact current-value row used by a workbench frame."""

    action = "Enter to change"
    state = (
        f" · {single_line_terminal_text(safe_terminal_text(view.state))}"
        if view.state.strip()
        else ""
    )
    action_suffix = f"    {action}"
    full_suffix = f"{state}{action_suffix}"
    suffix = (
        full_suffix
        if content_width - terminal_cell_width(full_suffix) >= 4
        else action_suffix
    )
    safe_value = single_line_terminal_text(safe_terminal_text(view.value))
    available = content_width - terminal_cell_width(suffix)
    if available <= 0:
        row = elide_terminal_text(action, max(1, content_width))
        fragments: list[tuple[str, str]] = []
        if focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append((focused_control_style(focused=focused), row))
        return fragments
    value = elide_terminal_text(safe_value, available, position="middle")
    row = f"{value}{suffix}"
    fragments: list[tuple[str, str]] = []
    if focused:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.append((focused_control_style(focused=focused), row))
    return fragments


def save_location_card_lines(
    view: SaveLocationView,
    *,
    width: int = 72,
) -> list[str]:
    """Render the same location contract in a non-full-screen apply review."""

    state = f" · {view.state}" if view.state.strip() else ""
    return boxed_lines(
        view.label,
        f"{display_escape_text(view.value)}{state}\n{view.detail}",
        width=width,
    )
