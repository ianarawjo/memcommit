"""Process-local cursor and checked value for a fixed flat option set."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.adapters.console.terminal.components.selection.model import SelectionOption


@dataclass
class SingleSelectionState:
    """Separate keyboard cursor from one staged single selection.

    Callers decide whether movement immediately selects, whether Enter toggles,
    and what an unselected special row means. This state owns only the shared
    ordered cursor and checked-value invariants.
    """

    options: tuple[SelectionOption, ...]
    cursor_value: str
    selected_value: str | None = None
    allow_empty: bool = True

    def __post_init__(self) -> None:
        values = tuple(option.value for option in self.options)
        if not values or len(set(values)) != len(values):
            raise ValueError("Flat selection requires distinct options.")
        if self.cursor_value not in values:
            raise ValueError("Flat selection cursor is unavailable.")
        if self.selected_value is not None and self.selected_value not in values:
            raise ValueError("Flat selection value is unavailable.")
        if not isinstance(self.allow_empty, bool):
            raise ValueError("Flat selection allow-empty state must be boolean.")
        if not self.allow_empty and self.selected_value is None:
            raise ValueError("This flat selection requires one checked value.")

    @property
    def cursor_index(self) -> int:
        return next(
            index
            for index, option in enumerate(self.options)
            if option.value == self.cursor_value
        )

    def move(self, delta: int) -> bool:
        """Move without wrapping and report whether the cursor changed."""

        if isinstance(delta, bool) or not isinstance(delta, int):
            raise ValueError("Flat selection movement must be an integer.")
        index = max(0, min(self.cursor_index + delta, len(self.options) - 1))
        cursor_value = self.options[index].value
        changed = cursor_value != self.cursor_value
        self.cursor_value = cursor_value
        return changed

    def set_selected(self, value: str | None) -> bool:
        """Set an exact staged value without moving the keyboard cursor."""

        if value is None and not self.allow_empty:
            raise ValueError("This flat selection requires one checked value.")
        if value is not None and all(option.value != value for option in self.options):
            raise ValueError("Flat selection value is unavailable.")
        changed = value != self.selected_value
        self.selected_value = value
        return changed

    def select_cursor(self, *, toggle: bool) -> str | None:
        """Stage the cursor value, optionally clearing an already checked row."""

        selected = (
            None
            if toggle and self.allow_empty and self.selected_value == self.cursor_value
            else self.cursor_value
        )
        self.set_selected(selected)
        return self.selected_value

    def reset_cursor_to_selection(self) -> None:
        """Align reopening with the checked row when one exists."""

        if self.selected_value is not None:
            self.cursor_value = self.selected_value
