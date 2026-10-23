"""Frozen display inputs and exact results for the Profile picker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ProfilePickerEntry:
    """Display-only summary of one already validated visible Profile."""

    name: str
    context_count: int
    current_context: str | None
    memory_count: int = 0
    uid: str | None = None
    study_uid: str | None = None
    study_name: str | None = None
    study_created_at: str | None = None
    study_role: str | None = None
    study_profile_count: int = 0
    removal_block: str | None = None
    rename_block: str | None = None
    root_dir: str | None = None


@dataclass(frozen=True)
class ProfilePickerAction:
    """One exact selector action returned only after its required key path."""

    kind: Literal[
        "USE",
        "CREATE_PROFILE",
        "RENAME_PROFILE",
        "RENAME_STUDY",
        "REMOVE_PROFILE",
        "REMOVE_STUDY",
    ]
    name: str
    uid: str | None
    registry_generation: int | None
    new_name: str | None = None
    row_index: int | None = None
    root_dir: str | None = None
    import_project_files: bool = False
    imported_file_count: int = 0
    skipped_file_count: int = 0
    import_digest: str | None = None
    select_created: bool = False


@dataclass(frozen=True)
class ProfilePickerRefresh:
    """A completed picker mutation that requires a fresh Profile catalog."""

    status: str
    error: Exception | None = None
    close_requested: bool = False
    preferred_row_index: int | None = None


@dataclass(frozen=True)
class ProfilePickerRow:
    kind: Literal["PROFILE", "STUDY"]
    name: str
    uid: str | None
    entry: ProfilePickerEntry | None = None
    created_at: str | None = None
    profile_count: int = 1
