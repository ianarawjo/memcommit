"""Validate one frozen inventory and project its Profile/Study keyboard rows."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerEntry,
    ProfilePickerRow,
)


def _validate_entries(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
) -> tuple[ProfilePickerEntry, ...]:
    options = tuple(entries)
    if not options:
        raise ValueError("No profiles are available to select.")
    names = [entry.name for entry in options]
    if any(
        not isinstance(entry.name, str)
        or not entry.name
        or entry.context_count < 0
        or entry.memory_count < 0
        or entry.granted_context_count < 0
        or entry.granted_memory_count < 0
        or entry.query_source_count < 0
        or len(entry.query_source_names) > entry.query_source_count
        or any(not name for name in entry.query_source_names)
        or len(set(entry.query_source_names)) != len(entry.query_source_names)
        or (entry.uid is not None and not entry.uid)
        or (entry.removal_block is not None and not entry.removal_block.strip())
        or (entry.rename_block is not None and not entry.rename_block.strip())
        or (
            any(
                value is not None
                for value in (
                    entry.study_uid,
                    entry.study_name,
                    entry.study_created_at,
                    entry.study_task,
                    entry.study_role,
                )
            )
            and not (
                isinstance(entry.study_uid, str)
                and bool(entry.study_uid)
                and isinstance(entry.study_name, str)
                and bool(entry.study_name)
                and isinstance(entry.study_created_at, str)
                and bool(entry.study_created_at)
                and entry.study_profile_count > 0
                and 0 <= entry.study_removed_count < entry.study_profile_count
                and (
                    (
                        type(entry.study_task) is int
                        and entry.study_task in {1, 2, 3}
                        and entry.study_role in {None, "TASK", "AUTHORITY"}
                    )
                    or (
                        entry.study_task is None
                        and entry.study_role in {"PARTICIPANT", "GRANTED_MEMORY"}
                    )
                )
            )
        )
        or (
            entry.study_name is None
            and (entry.study_profile_count != 0 or entry.study_removed_count != 0)
        )
        for entry in options
    ) or len(set(names)) != len(names):
        raise ValueError("Profile selection received invalid entries.")
    study_metadata: dict[
        str,
        tuple[str, str, int, int, set[tuple[str, int | None]]],
    ] = {}
    finished_studies: set[str] = set()
    previous_study: str | None = None
    for entry in options:
        study_name = entry.study_name
        if study_name is None:
            if previous_study is not None:
                finished_studies.add(previous_study)
            previous_study = None
            continue
        if previous_study is not None and study_name != previous_study:
            finished_studies.add(previous_study)
        if study_name in finished_studies:
            raise ValueError("Study Profile entries must remain contiguous.")
        created_at = entry.study_created_at
        study_uid = entry.study_uid
        task = entry.study_task
        assert isinstance(created_at, str)
        assert isinstance(study_uid, str)
        member = (entry.study_role or "TASK", task)
        existing = study_metadata.get(study_name)
        metadata = (
            study_uid,
            created_at,
            entry.study_profile_count,
            entry.study_removed_count,
        )
        if existing is None:
            study_metadata[study_name] = (*metadata, {member})
        elif existing[:4] != metadata or member in existing[4]:
            raise ValueError("Study Profile entries are inconsistent.")
        else:
            existing[4].add(member)
        previous_study = study_name
    if current not in names:
        raise ValueError("The current profile is not available to select.")
    return options


def build_picker_rows(
    entries: Sequence[ProfilePickerEntry],
    *,
    current: str,
) -> tuple[ProfilePickerRow, ...]:
    options = _validate_entries(entries, current=current)
    rows: list[ProfilePickerRow] = []
    previous_study: str | None = None
    for entry in options:
        if entry.study_name is not None and entry.study_name != previous_study:
            rows.append(
                ProfilePickerRow(
                    kind="STUDY",
                    name=entry.study_name,
                    uid=entry.study_uid,
                    created_at=entry.study_created_at,
                    profile_count=entry.study_profile_count,
                    removed_count=entry.study_removed_count,
                    renames_member_profiles=entry.study_role in {"TASK", "AUTHORITY"},
                )
            )
        rows.append(
            ProfilePickerRow(
                kind="PROFILE",
                name=entry.name,
                uid=entry.uid,
                entry=entry,
            )
        )
        previous_study = entry.study_name
    return tuple(rows)
