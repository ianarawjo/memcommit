"""Process-local cursor and checked value for a fixed flat option set."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.selection.model import SelectionOption


@dataclass
class FlatSelectionState:
    """Separate keyboard cursor from one staged single selection.

    Callers decide whether movement immediately selects, whether Enter toggles,
    and what an unselected special row means. This state owns only the shared
    ordered cursor and checked-value invariants.
    """

    options: tuple[SelectionOption, ...]
    cursor_uid: str
    selected_uid: str | None = None
    allow_empty: bool = True

    def __post_init__(self) -> None:
        uids = tuple(option.uid for option in self.options)
        if not uids or len(set(uids)) != len(uids):
            raise ValueError("Flat selection requires distinct options.")
        if self.cursor_uid not in uids:
            raise ValueError("Flat selection cursor is unavailable.")
        if self.selected_uid is not None and self.selected_uid not in uids:
            raise ValueError("Flat selection value is unavailable.")
        if not isinstance(self.allow_empty, bool):
            raise ValueError("Flat selection allow-empty state must be boolean.")
        if not self.allow_empty and self.selected_uid is None:
            raise ValueError("This flat selection requires one checked value.")

    @property
    def cursor_index(self) -> int:
        return next(
            index
            for index, option in enumerate(self.options)
            if option.uid == self.cursor_uid
        )

    def move(self, delta: int) -> bool:
        """Move without wrapping and report whether the cursor changed."""

        if isinstance(delta, bool) or not isinstance(delta, int):
            raise ValueError("Flat selection movement must be an integer.")
        index = max(0, min(self.cursor_index + delta, len(self.options) - 1))
        cursor_uid = self.options[index].uid
        changed = cursor_uid != self.cursor_uid
        self.cursor_uid = cursor_uid
        return changed

    def set_selected(self, uid: str | None) -> bool:
        """Set an exact staged value without moving the keyboard cursor."""

        if uid is None and not self.allow_empty:
            raise ValueError("This flat selection requires one checked value.")
        if uid is not None and all(option.uid != uid for option in self.options):
            raise ValueError("Flat selection value is unavailable.")
        changed = uid != self.selected_uid
        self.selected_uid = uid
        return changed

    def select_cursor(self, *, toggle: bool) -> str | None:
        """Stage the cursor value, optionally clearing an already checked row."""

        selected = (
            None
            if toggle and self.allow_empty and self.selected_uid == self.cursor_uid
            else self.cursor_uid
        )
        self.set_selected(selected)
        return self.selected_uid

    def reset_cursor_to_selection(self) -> None:
        """Align reopening with the checked row when one exists."""

        if self.selected_uid is not None:
            self.cursor_uid = self.selected_uid
