"""Process-local Profile picker transitions, independent of a running terminal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerAction,
    ProfilePickerRow,
)
from memcommit.adapters.console.commands.profile.picker.review import removal_action
from memcommit.adapters.console.terminal.components.selection.model import (
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    FlatSelectionState,
)
from memcommit.application.operations.profile.config import validate_profile_name


@dataclass(frozen=True)
class NameEdit:
    """An input destination and its initial text, before exact approval."""

    kind: Literal["CREATE_PROFILE", "RENAME_PROFILE", "RENAME_STUDY"]
    value: str
    row_index: int


@dataclass
class ProfilePickerState:
    rows: tuple[ProfilePickerRow, ...]
    current: str
    registry_generation: int | None
    selection: FlatSelectionState
    # Exactly one layer is active: browse, name input, or an exact review.
    # Executor busy/close state stays solely in BackgroundExecutorTurn.
    stage: NameEdit | ProfilePickerAction | None = None
    status: str = ""
    status_is_error: bool = False

    @classmethod
    def create(
        cls,
        rows: tuple[ProfilePickerRow, ...],
        *,
        current: str,
        registry_generation: int | None = None,
        initial_status: str = "",
        initial_row_index: int | None = None,
    ) -> ProfilePickerState:
        if not isinstance(initial_status, str):
            raise ValueError("Profile selection status must be text.")
        if initial_row_index is not None and (
            not isinstance(initial_row_index, int)
            or isinstance(initial_row_index, bool)
            or initial_row_index < 0
        ):
            raise ValueError("Profile selection row must be a nonnegative integer.")
        current_index = next(
            index
            for index, row in enumerate(rows)
            if row.kind == "PROFILE" and row.name == current
        )
        # After deletion, retain the visual position or the preceding last row.
        index = (
            min(initial_row_index, len(rows) - 1)
            if initial_row_index is not None
            else current_index
        )
        return cls(
            rows=rows,
            current=current,
            registry_generation=registry_generation,
            selection=FlatSelectionState(
                # Cursor keys live only within this frozen row set. Durable
                # actions always carry the row's raw name and Profile/Study UID.
                options=tuple(
                    SelectionOption(uid=str(i), label=row.kind)
                    for i, row in enumerate(rows)
                ),
                cursor_uid=str(index),
            ),
            status=initial_status,
        )

    @property
    def index(self) -> int:
        return self.selection.cursor_index

    @property
    def current_row(self) -> ProfilePickerRow:
        return self.rows[self.index]

    @property
    def edit(self) -> NameEdit | None:
        return self.stage if isinstance(self.stage, NameEdit) else None

    @property
    def action(self) -> ProfilePickerAction | None:
        return self.stage if isinstance(self.stage, ProfilePickerAction) else None

    def notify(self, message: str = "", *, error: bool = False) -> None:
        self.status = message
        self.status_is_error = error

    def move(self, delta: int) -> None:
        if self.stage is None:
            self.selection.move(delta)
            self.notify()

    def use_profile(self) -> ProfilePickerAction | None:
        if self.stage is not None:
            return None
        row = self.current_row
        if row.kind == "STUDY":
            self.notify("Study header selected · D reviews whole-Study removal")
            return None
        return ProfilePickerAction(
            kind="USE",
            name=row.name,
            uid=row.uid,
            registry_generation=self.registry_generation,
        )

    def begin_create(self) -> None:
        if self.stage is None:
            # New ordinary Profiles append after all frozen Profile/Study rows.
            self.stage = NameEdit("CREATE_PROFILE", "", len(self.rows))
            self.notify()

    def begin_rename(self) -> None:
        if self.stage is not None:
            return
        row = self.current_row
        if row.entry is not None and row.entry.rename_block is not None:
            self.notify(row.entry.rename_block, error=True)
            return
        self.stage = NameEdit(
            "RENAME_STUDY" if row.kind == "STUDY" else "RENAME_PROFILE",
            row.name,
            self.index,
        )
        self.notify()

    def review_name(self, name: str) -> None:
        edit = self.edit
        if edit is None:
            raise ValueError("Profile name review requires an active name input.")
        validate_profile_name(name)
        if edit.kind == "CREATE_PROFILE":
            action = ProfilePickerAction(
                kind=edit.kind,
                name=name,
                uid=None,
                registry_generation=self.registry_generation,
                row_index=edit.row_index,
            )
        else:
            row = self.rows[edit.row_index]
            action = ProfilePickerAction(
                kind=edit.kind,
                name=row.name,
                uid=row.uid,
                registry_generation=self.registry_generation,
                new_name=name,
                row_index=edit.row_index,
            )
        self.stage = action
        self.notify()

    def review_removal(self) -> None:
        if self.stage is not None:
            return
        row = self.current_row
        if row.kind == "PROFILE":
            entry = row.entry
            assert entry is not None
            if row.name == self.current:
                self.notify(
                    "CURRENT Profile cannot be removed · switch first", error=True
                )
                return
            if entry.removal_block is not None:
                self.notify(entry.removal_block, error=True)
                return
        elif any(
            item.entry is not None
            and item.entry.study_name == row.name
            and item.name == self.current
            for item in self.rows
        ):
            self.notify("Study contains CURRENT Profile · switch first", error=True)
            return
        self.stage = removal_action(row, registry_generation=self.registry_generation)
        self.notify()

    def back(self) -> bool:
        """Retreat one visible layer; false delegates root close to the app."""

        action = self.action
        if action is not None:
            if action.kind == "CREATE_PROFILE":
                assert action.row_index is not None
                self.stage = NameEdit(action.kind, action.name, action.row_index)
                self.notify("Create review cancelled")
            elif action.kind in {"RENAME_PROFILE", "RENAME_STUDY"}:
                assert action.row_index is not None and action.new_name is not None
                self.stage = NameEdit(action.kind, action.new_name, action.row_index)
                self.notify("Rename review cancelled")
            else:
                self.stage = None
                self.notify("Removal review cancelled")
            return True
        edit = self.edit
        if edit is not None:
            self.stage = None
            self.notify(
                "Profile creation cancelled"
                if edit.kind == "CREATE_PROFILE"
                else "Rename cancelled"
            )
            return True
        return False
