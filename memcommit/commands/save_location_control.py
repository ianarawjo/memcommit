"""Shared presentation contract for exact local materialization locations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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

    def validate_value(self, value: str) -> str:
        """Validate an exact edited name without deciding how it is persisted."""

        if not isinstance(value, str) or not value.strip():
            raise ValueError("Save location must be nonempty text.")
        if any(character in value for character in "\r\n"):
            raise ValueError("Save location must stay on one line.")
        if self.validate is not None:
            self.validate(value)
        return value


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
